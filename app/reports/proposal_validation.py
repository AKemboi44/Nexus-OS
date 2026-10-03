"""Deterministic validation for proposal v2 drafts."""

from dataclasses import dataclass
from typing import List, Set, Optional
from app.reports.proposal_schema import ProposalDraftV2
from app.reports.evidence_preparation import EvidencePacket


@dataclass
class ValidationResult:
    """Result of proposal validation."""
    passed: bool
    errors: List[str]
    warnings: List[str]
    word_count: int = 0


def validate_proposal_draft(
    draft: ProposalDraftV2,
    packet: EvidencePacket,
    min_words: int = 1000,
    max_words: int = 1800,
) -> ValidationResult:
    """
    Validate a proposal draft against schema, citations, and content requirements.

    Hard failures: invalid JSON, unknown citations, structural errors.
    No model-based repair.
    """
    errors = []
    warnings = []

    try:
        # Schema validation was already done by Pydantic in parsing
        if draft.schema_version != "proposal.v2":
            errors.append(f"Invalid schema_version: {draft.schema_version}")
    except Exception as e:
        errors.append(f"Schema error: {str(e)}")
        return ValidationResult(passed=False, errors=errors, warnings=warnings)

    # Collect all supplied source IDs
    supplied_ids = set(packet.sent_source_ids)

    # Validate all citations are known
    cited_ids = _collect_cited_ids(draft)
    unknown_citations = cited_ids - supplied_ids
    if unknown_citations:
        errors.append(f"Unknown source citations: {sorted(unknown_citations)}")

    # Check for orphaned citations (cited but not in packet)
    for cit_id in cited_ids:
        if cit_id not in supplied_ids:
            errors.append(f"Citation {cit_id} not in evidence packet")

    # Validate required sections are non-empty
    required_sections = [
        ("overview", draft.overview),
        ("literature_insights", draft.literature_insights),
        ("research_gap", draft.research_gap),
        ("research_problem", draft.research_problem),
        ("research_questions", draft.research_questions),
        ("research_objectives", draft.research_objectives),
        ("methodology", draft.methodology),
        ("conclusion", draft.conclusion),
    ]

    for section_name, section_content in required_sections:
        if not section_content:
            errors.append(f"Required section empty: {section_name}")

    # Validate research questions and objectives are linked
    question_ids = set(q.question_id or f"q{i}" for i, q in enumerate(draft.research_questions))
    for obj in draft.research_objectives:
        if obj.question_ids:
            unknown_questions = set(obj.question_ids) - question_ids
            if unknown_questions:
                warnings.append(
                    f"Objective references unknown question IDs: {unknown_questions}"
                )

    # Count words (excluding citations, metadata, headings)
    word_count = _count_narrative_words(draft)
    if word_count < min_words:
        errors.append(
            f"Content too brief: {word_count} words (minimum {min_words})"
        )
    if word_count > max_words:
        errors.append(
            f"Content too long: {word_count} words (maximum {max_words})"
        )

    # Check for leaked instructions or square brackets
    full_text = _extract_all_text(draft)
    if "[" in full_text or "]" in full_text:
        warnings.append("Square brackets found in content (may be placeholder or instruction)")
    if "instruction" in full_text.lower() or "placeholder" in full_text.lower():
        warnings.append("Possible leaked instructions or placeholders")

    passed = len(errors) == 0
    return ValidationResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        word_count=word_count,
    )


def _collect_cited_ids(draft: ProposalDraftV2) -> Set[str]:
    """Collect all evidence_ids referenced in the draft."""
    cited = set()

    def collect_from_blocks(blocks):
        for block in blocks:
            cited.update(block.evidence_ids)

    collect_from_blocks(draft.overview)
    collect_from_blocks(draft.contradictions_and_limitations)
    collect_from_blocks(draft.research_gap)
    collect_from_blocks(draft.research_problem)
    collect_from_blocks(draft.conclusion)
    collect_from_blocks(draft.evidence_limitations)

    for theme in draft.literature_insights:
        collect_from_blocks(theme.blocks)

    for q in draft.research_questions:
        cited.update(q.evidence_ids)

    for obj in draft.research_objectives:
        cited.update(obj.evidence_ids)

    for para in draft.methodology.research_design:
        cited.update(para.evidence_ids)
    for para in draft.methodology.data_collection:
        cited.update(para.evidence_ids)
    for para in draft.methodology.analysis:
        cited.update(para.evidence_ids)
    for para in draft.methodology.limitations:
        cited.update(para.evidence_ids)

    return cited


def _count_narrative_words(draft: ProposalDraftV2) -> int:
    """Count narrative words (excluding citations, metadata)."""
    text = _extract_all_text(draft)
    return len(text.split())


def _extract_all_text(draft: ProposalDraftV2) -> str:
    """Extract all narrative text for inspection."""
    parts = []

    def extract_from_blocks(blocks):
        for block in blocks:
            parts.append(block.text)

    extract_from_blocks(draft.overview)
    extract_from_blocks(draft.contradictions_and_limitations)
    extract_from_blocks(draft.research_gap)
    extract_from_blocks(draft.research_problem)
    extract_from_blocks(draft.conclusion)
    extract_from_blocks(draft.evidence_limitations)

    for theme in draft.literature_insights:
        parts.append(theme.title)
        extract_from_blocks(theme.blocks)

    for q in draft.research_questions:
        parts.append(q.text)

    for obj in draft.research_objectives:
        parts.append(obj.text)

    for para in draft.methodology.research_design:
        parts.append(para.text)
    for para in draft.methodology.data_collection:
        parts.append(para.text)
    for para in draft.methodology.analysis:
        parts.append(para.text)
    for para in draft.methodology.limitations:
        parts.append(para.text)

    return " ".join(parts)
