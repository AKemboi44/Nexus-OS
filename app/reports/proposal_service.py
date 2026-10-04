"""Proposal generation: model synthesis with one repair attempt, falling back to deterministic templates."""

import logging
import re
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.analytics.context import current_request_id
from app.reports.evidence_preparation import EvidencePacket, prepare_proposal_evidence
from app.reports.metadata_extractor import extract_research_metadata
from app.reports.proposal_builder import build_proposal_from_research
from app.reports.proposal_renderer import render_proposal_docx
from app.reports.proposal_schema import ProposalDraftV2
from app.reports.proposal_synthesis import synthesize_proposal
from app.reports.proposal_validation import (
    cited_source_count,
    gate_error_codes,
    integrative_paragraph_count,
    validate_proposal_draft,
    validate_synthesized_draft,
)
from app.synthesis.call_ledger import QUALITY_GATE, RequestLedger
from app.synthesis.providers import SynthesisUnavailableError

logger = logging.getLogger(__name__)

MAX_SYNTHESIS_ATTEMPTS = 2
AI_SYNTHESIZED = "ai_synthesized"
TEMPLATE_FALLBACK = "template_fallback"
_TEMPLATE_SUFFIX = "so a structured template draft was produced from the source metadata instead."
FALLBACK_NOTES = {
    "not_configured": f"AI writing is not configured on the server, {_TEMPLATE_SUFFIX}",
    "provider_error": f"The AI writing service returned an error, {_TEMPLATE_SUFFIX}",
    "invalid_output": f"The AI response could not be used, {_TEMPLATE_SUFFIX}",
    "quality_gate": f"The AI draft did not pass the citation, originality or length checks, {_TEMPLATE_SUFFIX}",
}


@dataclass
class ProposalDocument:
    """Generated proposal document ready for download, with the telemetry of how it was made."""
    document_bytes: bytes
    word_count: int
    document_name: str = "proposal.docx"
    generation_mode: str = TEMPLATE_FALLBACK
    synthesis_note: Optional[str] = None
    synthesis_failure: Optional[str] = None
    ledger: Optional[RequestLedger] = None
    quality: Dict[str, Any] = field(default_factory=dict)
    timings_ms: Dict[str, int] = field(default_factory=dict)


@dataclass
class _Synthesis:
    draft: Optional[ProposalDraftV2] = None
    word_count: int = 0
    failure: Optional[str] = None
    gate_codes: List[str] = field(default_factory=list)


_ILLEGAL_FILENAME_CHARACTERS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def document_filename(topic: str) -> str:
    """Filesystem-safe .docx name that matches the research topic."""
    name = _ILLEGAL_FILENAME_CHARACTERS.sub(" ", str(topic or ""))
    name = re.sub(r"\s+", " ", name).strip(" .")[:80].rstrip(" .")
    return f"{name or 'proposal'}.docx"


class ProposalValidationError(Exception):
    """Proposal draft failed validation."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Proposal validation failed: {errors}")


def _default_provider():
    from app.synthesis.providers import ClaudeSynthesisProvider
    return ClaudeSynthesisProvider()


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def generate_proposal_docx(
    topic: str,
    domain: str,
    included_sources: List[Dict[str, Any]],
    provider=None,
    ledger: Optional[RequestLedger] = None,
) -> ProposalDocument:
    """
    Generate an APA-styled proposal and render it to DOCX.

    Makes at most two model calls (the second only to repair a draft that failed the quality
    gate). Any synthesis failure (not configured, provider error, unparsable output, failed
    quality gate) falls back to the deterministic template so a download is always produced;
    `generation_mode` says which path was used, and `ledger`/`quality`/`timings_ms` describe how.
    Pass `ledger` to keep the model calls even if generation later raises.

    Raises:
        ProposalValidationError: even the template draft failed validation
        RuntimeError: evidence preparation, drafting or rendering failed
        ValueError: invalid input
    """
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty")
    if not included_sources:
        raise ValueError("At least one source is required")

    logger.info("ProposalService: start (topic=%s, domain=%s, sources=%d)", topic, domain, len(included_sources))

    try:
        packet = prepare_proposal_evidence(topic, domain, included_sources)
    except Exception as error:
        logger.exception("ProposalService: evidence preparation failed")
        raise RuntimeError(f"Could not prepare evidence: {error}")

    if ledger is None:
        ledger = RequestLedger(request_id=current_request_id() or str(uuid.uuid4()))
    timings: Dict[str, int] = {}

    started = time.monotonic()
    synthesis = _synthesize(packet, topic, domain, provider, ledger)
    timings["synthesis_ms"] = _elapsed_ms(started)

    if synthesis.draft is not None:
        draft, word_count, mode = synthesis.draft, synthesis.word_count, AI_SYNTHESIZED
    else:
        draft, word_count = _template_draft(packet, topic, domain, included_sources)
        mode = TEMPLATE_FALLBACK

    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="nexus-proposal-") as tmpdir:
            doc_path = Path(tmpdir) / "proposal.docx"
            render_proposal_docx(draft, packet, doc_path)
            document_bytes = doc_path.read_bytes()
    except Exception as error:
        logger.exception("ProposalService: DOCX rendering failed")
        raise RuntimeError(f"Could not render proposal to DOCX: {error}")
    if not document_bytes:
        raise RuntimeError("DOCX file is empty")
    timings["render_ms"] = _elapsed_ms(started)

    quality = {
        "generation_mode": mode,
        "synthesis_failure": synthesis.failure,
        "attempts": len(ledger.calls),
        "repair_used": mode == AI_SYNTHESIZED and len(ledger.calls) > 1,
        "word_count": word_count,
        "source_count": len(packet.sources),
        "cited_source_count": cited_source_count(draft),
        "integrative_paragraphs": integrative_paragraph_count(draft),
        "gate_errors": ",".join(synthesis.gate_codes),
    }
    logger.info("ProposalService: done (mode=%s, words=%d, bytes=%d, calls=%d, timings=%s)",
                mode, word_count, len(document_bytes), len(ledger.calls), timings)
    return ProposalDocument(
        document_bytes=document_bytes,
        word_count=word_count,
        document_name=document_filename(topic),
        generation_mode=mode,
        synthesis_note=FALLBACK_NOTES.get(synthesis.failure) if mode == TEMPLATE_FALLBACK else None,
        synthesis_failure=synthesis.failure,
        ledger=ledger,
        quality=quality,
        timings_ms=timings,
    )


def _failure_reason(error: Exception) -> str:
    if isinstance(error, SynthesisUnavailableError):
        return "not_configured"
    if isinstance(error, ProposalValidationError):
        return "quality_gate"
    if isinstance(error, (ValueError, TypeError)):  # includes JSON and pydantic validation errors
        return "invalid_output"
    return "provider_error"


def _synthesize(packet: EvidencePacket, topic: str, domain: str, provider, ledger: RequestLedger) -> _Synthesis:
    """Try synthesis; `draft` is None when it is unusable.

    A draft that fails the quality gate gets one repair attempt with the specific problems
    fed back; provider errors and a missing key are not retried.
    """
    result = _Synthesis()
    provider = provider or _default_provider()
    feedback: Optional[List[str]] = None
    for attempt in range(1, MAX_SYNTHESIS_ATTEMPTS + 1):
        try:
            draft = synthesize_proposal(packet, topic, domain, provider, feedback, ledger, attempt)
            validation = validate_synthesized_draft(draft, packet)
            if not validation.passed:
                ledger.calls[-1].outcome = QUALITY_GATE
                raise ProposalValidationError(validation.errors)
            result.draft, result.word_count, result.failure = draft, validation.word_count, None
            return result
        except Exception as error:
            reason = _failure_reason(error)
            if isinstance(error, ProposalValidationError):
                for code in gate_error_codes(error.errors):
                    if code not in result.gate_codes:
                        result.gate_codes.append(code)
            logger.warning("ProposalService: synthesis attempt %d/%d failed (reason=%s, %s: %s)",
                           attempt, MAX_SYNTHESIS_ATTEMPTS, reason, type(error).__name__, error)
            result.failure = reason
            if reason != "quality_gate" or attempt == MAX_SYNTHESIS_ATTEMPTS:
                return result
            feedback = error.errors
    return result


def _template_draft(
    packet: EvidencePacket, topic: str, domain: str, included_sources: List[Dict[str, Any]]
) -> Tuple[ProposalDraftV2, int]:
    try:
        metadata = extract_research_metadata(included_sources, topic)
    except Exception as error:
        logger.warning("ProposalService: metadata extraction failed, using empty metadata: %s", error)
        metadata = {"abstract": "", "themes": [], "research_gaps": [], "opportunity_areas": [], "research_areas": []}

    try:
        draft: ProposalDraftV2 = build_proposal_from_research(
            topic=topic, domain=domain, dossier=metadata, packet=packet,
        )
    except Exception as error:
        logger.exception("ProposalService: template drafting failed")
        raise RuntimeError(f"Could not build proposal: {error}")

    validation = validate_proposal_draft(draft, packet)
    if not validation.passed:
        logger.warning("ProposalService: template validation failed: %s", validation.errors)
        raise ProposalValidationError(validation.errors)
    return draft, validation.word_count
