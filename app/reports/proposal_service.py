"""Clean proposal generation: templates + deterministic metadata extraction."""

import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any

from app.reports.proposal_builder import build_proposal_from_research
from app.reports.proposal_validation import validate_proposal_draft, ValidationResult
from app.reports.proposal_renderer import render_proposal_docx
from app.reports.evidence_preparation import prepare_proposal_evidence
from app.reports.metadata_extractor import extract_research_metadata

logger = logging.getLogger(__name__)


@dataclass
class ProposalDocument:
    """Generated proposal document ready for download."""
    document_bytes: bytes
    word_count: int
    generation_mode: str = "template"


class ProposalValidationError(Exception):
    """Proposal draft failed validation."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Proposal validation failed: {errors}")


def generate_proposal_docx(
    topic: str,
    domain: str,
    included_sources: List[Dict[str, Any]],
) -> ProposalDocument:
    """
    Generate a research proposal and render it to DOCX.

    Pure function with no side effects except temp file creation.
    Raises ProposalValidationError if validation fails; other exceptions are real failures.

    Args:
        topic: Research topic/question
        domain: Research domain (e.g., "technology", "health", "scholarly")
        included_sources: List of source dicts with title, authors, year, publication, abstract, etc.

    Returns:
        ProposalDocument with bytes, word_count, generation_mode

    Raises:
        ProposalValidationError: Draft failed validation (fixable by user/prompt)
        RuntimeError: Rendering or file I/O failed
        ValueError: Invalid input
    """

    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty")
    if not included_sources:
        raise ValueError("At least one source is required")

    logger.info("ProposalService: Starting proposal generation (topic=%s, domain=%s, sources=%d)",
               topic, domain, len(included_sources))

    # Step 1: Prepare evidence packet (deterministic, no LLM)
    try:
        packet = prepare_proposal_evidence(topic, domain, included_sources)
        logger.info("ProposalService: Evidence packet prepared, %d sources included",
                   len(packet.sources))
    except Exception as e:
        logger.exception("ProposalService: Evidence preparation failed")
        raise RuntimeError(f"Could not prepare evidence: {str(e)}")

    # Step 2: Extract research metadata (deterministic, no LLM)
    try:
        metadata = extract_research_metadata(included_sources, topic)
        logger.info("ProposalService: Metadata extracted (themes=%d, gaps=%d, opportunities=%d)",
                   len(metadata.get("themes", [])),
                   len(metadata.get("research_gaps", [])),
                   len(metadata.get("opportunity_areas", [])))
    except Exception as e:
        logger.warning("ProposalService: Metadata extraction failed, using empty metadata: %s", str(e))
        metadata = {
            "abstract": "",
            "themes": [],
            "research_gaps": [],
            "opportunity_areas": [],
            "research_areas": [],
        }

    # Step 3: Build proposal draft (deterministic, no LLM)
    try:
        draft = build_proposal_from_research(
            topic=topic,
            domain=domain,
            dossier=metadata,
            packet=packet,
        )
        logger.info("ProposalService: Draft built")
    except Exception as e:
        logger.exception("ProposalService: Draft building failed")
        raise RuntimeError(f"Could not build proposal: {str(e)}")

    # Step 4: Validate draft
    try:
        validation = validate_proposal_draft(draft, packet)
        logger.info("ProposalService: Validation complete (passed=%s, word_count=%d)",
                   validation.passed, validation.word_count)

        if not validation.passed:
            logger.warning("ProposalService: Validation failed: %s", validation.errors)
            raise ProposalValidationError(validation.errors)

        word_count = validation.word_count
    except ProposalValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.exception("ProposalService: Validation error")
        raise RuntimeError(f"Validation failed: {str(e)}")

    # Step 5: Render to DOCX
    try:
        with tempfile.TemporaryDirectory(prefix="nexus-proposal-") as tmpdir:
            doc_path = Path(tmpdir) / "proposal.docx"
            render_proposal_docx(draft, packet, doc_path)

            if not doc_path.exists():
                raise RuntimeError("DOCX file was not created")

            document_bytes = doc_path.read_bytes()
            if not document_bytes:
                raise RuntimeError("DOCX file is empty")

            logger.info("ProposalService: DOCX rendered and loaded (%d bytes)", len(document_bytes))

            return ProposalDocument(
                document_bytes=document_bytes,
                word_count=word_count,
                generation_mode="template",
            )
    except Exception as e:
        logger.exception("ProposalService: DOCX rendering failed")
        raise RuntimeError(f"Could not render proposal to DOCX: {str(e)}")
