"""Render validated proposal drafts to Word documents."""

from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from app.reports.proposal_schema import ProposalDraftV2
from app.reports.evidence_preparation import EvidencePacket, SourceRecord


def render_proposal_docx(
    draft: ProposalDraftV2,
    packet: EvidencePacket,
    output_path: Path,
) -> Path:
    """
    Render a validated proposal draft to a Word document.

    Args:
        draft: Validated ProposalDraftV2
        packet: EvidencePacket with sources
        output_path: Where to save the .docx file

    Returns:
        Path to saved document
    """
    doc = Document()

    # Title block
    title = doc.add_paragraph()
    title_run = title.add_run(packet.topic)
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    domain_para = doc.add_paragraph(f"Domain: {packet.domain}")
    domain_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()  # Spacing

    # Research Overview
    doc.add_heading("1. Research Overview", level=1)
    for block in draft.overview:
        p = doc.add_paragraph(block.text)
        if block.evidence_ids:
            p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Literature Insights
    doc.add_heading("2. Literature Insights", level=1)
    for theme in draft.literature_insights:
        doc.add_heading(theme.title, level=2)
        for block in theme.blocks:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Contradictions and Limitations
    if draft.contradictions_and_limitations:
        doc.add_heading("3. Contradictions and Limitations", level=2)
        for block in draft.contradictions_and_limitations:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Research Gap
    doc.add_heading("3. Identified Research Gap", level=1)
    for block in draft.research_gap:
        p = doc.add_paragraph(block.text)
        if block.evidence_ids:
            p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Proposed Research Direction
    doc.add_heading("4. Proposed Research Direction", level=1)

    doc.add_heading("Problem Statement", level=2)
    for block in draft.research_problem:
        p = doc.add_paragraph(block.text)
        if block.evidence_ids:
            p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Research Questions
    doc.add_heading("Research Questions", level=2)
    for q in draft.research_questions:
        q_text = f"{q.text}"
        if q.question_id:
            q_text += f" ({q.question_id})"
        p = doc.add_paragraph(q_text, style="List Bullet")
        if q.evidence_ids:
            p.add_run(f" [{', '.join(q.evidence_ids)}]").font.italic = True

    # Research Objectives
    doc.add_heading("Research Objectives", level=2)
    for obj in draft.research_objectives:
        obj_text = obj.text
        if obj.question_ids:
            obj_text += f" [linked to: {', '.join(obj.question_ids)}]"
        p = doc.add_paragraph(obj_text, style="List Bullet")
        if obj.evidence_ids:
            p.add_run(f" [{', '.join(obj.evidence_ids)}]").font.italic = True

    # Suggested Methodology
    doc.add_heading("5. Suggested Methodology", level=1)

    if draft.methodology.research_design:
        doc.add_heading("Research Design", level=2)
        for block in draft.methodology.research_design:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    if draft.methodology.data_collection:
        doc.add_heading("Data Collection", level=2)
        for block in draft.methodology.data_collection:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    if draft.methodology.analysis:
        doc.add_heading("Analysis", level=2)
        for block in draft.methodology.analysis:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    if draft.methodology.limitations:
        doc.add_heading("Limitations", level=2)
        for block in draft.methodology.limitations:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Conclusion
    if draft.conclusion:
        doc.add_heading("6. Conclusion", level=1)
        for block in draft.conclusion:
            p = doc.add_paragraph(block.text)
            if block.evidence_ids:
                p.add_run(f" [{', '.join(block.evidence_ids)}]").font.italic = True

    # Evidence Limitations
    if draft.evidence_limitations:
        doc.add_heading("Evidence and Data Limitations", level=2)
        for block in draft.evidence_limitations:
            doc.add_paragraph(block.text, style="List Bullet")

    # References
    doc.add_page_break()
    doc.add_heading("References", level=1)

    # Build source map
    source_map = {src.source_id: src for src in packet.sources}

    # Render each cited source
    cited_ids = set()
    for src_id in packet.sent_source_ids:
        if src_id in source_map:
            cited_ids.add(src_id)

    for src_id in sorted(cited_ids):
        src = source_map[src_id]
        ref_text = _format_reference(src)
        p = doc.add_paragraph(ref_text, style="List Bullet")

    # Save document
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))

    return output_path


def _format_reference(source: SourceRecord) -> str:
    """Format a source as an APA-style reference."""
    parts = []

    if source.authors:
        parts.append(source.authors)

    if source.year:
        parts.append(f"({source.year})")

    if source.title:
        parts.append(f"\"{source.title}.\"")

    if source.publication:
        parts.append(f"*{source.publication}*")

    if source.doi_or_url:
        parts.append(source.doi_or_url)

    return " ".join(parts)
