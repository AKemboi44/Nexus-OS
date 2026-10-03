"""Proposal generation: one model synthesis call, falling back to deterministic templates."""

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.reports.evidence_preparation import EvidencePacket, prepare_proposal_evidence
from app.reports.metadata_extractor import extract_research_metadata
from app.reports.proposal_builder import build_proposal_from_research
from app.reports.proposal_renderer import render_proposal_docx
from app.reports.proposal_schema import ProposalDraftV2
from app.reports.proposal_synthesis import synthesize_proposal
from app.reports.proposal_validation import validate_proposal_draft, validate_synthesized_draft

logger = logging.getLogger(__name__)

AI_SYNTHESIZED = "ai_synthesized"
TEMPLATE_FALLBACK = "template_fallback"
FALLBACK_NOTE = (
    "AI synthesis was unavailable for this request, so a structured template draft was produced "
    "from the source metadata instead."
)


@dataclass
class ProposalDocument:
    """Generated proposal document ready for download."""
    document_bytes: bytes
    word_count: int
    document_name: str = "proposal.docx"
    generation_mode: str = TEMPLATE_FALLBACK
    synthesis_note: Optional[str] = None


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


def generate_proposal_docx(
    topic: str,
    domain: str,
    included_sources: List[Dict[str, Any]],
    provider=None,
) -> ProposalDocument:
    """
    Generate an APA-styled proposal and render it to DOCX.

    Makes at most one model call. Any synthesis failure (not configured, provider error,
    unparsable output, failed quality gate) falls back to the deterministic template so a
    download is always produced; `generation_mode` says which path was used.

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

    draft, word_count, mode = _synthesized_draft(packet, topic, domain, provider)
    if draft is None:
        draft, word_count = _template_draft(packet, topic, domain, included_sources)
        mode = TEMPLATE_FALLBACK

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

    logger.info("ProposalService: done (mode=%s, words=%d, bytes=%d)", mode, word_count, len(document_bytes))
    return ProposalDocument(
        document_bytes=document_bytes,
        word_count=word_count,
        document_name=document_filename(topic),
        generation_mode=mode,
        synthesis_note=FALLBACK_NOTE if mode == TEMPLATE_FALLBACK else None,
    )


def _synthesized_draft(packet: EvidencePacket, topic: str, domain: str, provider):
    """Return (draft, word_count, mode), or (None, 0, None) when synthesis cannot be used."""
    try:
        draft = synthesize_proposal(packet, topic, domain, provider or _default_provider())
        validation = validate_synthesized_draft(draft, packet)
        if not validation.passed:
            raise ProposalValidationError(validation.errors)
        return draft, validation.word_count, AI_SYNTHESIZED
    except Exception as error:
        logger.warning("ProposalService: synthesis unavailable, using template (%s: %s)",
                       type(error).__name__, error)
        return None, 0, None


def _template_draft(packet: EvidencePacket, topic: str, domain: str, included_sources: List[Dict[str, Any]]):
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
