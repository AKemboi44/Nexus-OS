"""Render validated proposal drafts to APA-styled Word documents."""

from pathlib import Path
from typing import Iterable, List

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from app.reports.apa import append_citation
from app.reports.evidence_preparation import EvidencePacket
from app.reports.proposal_schema import ParagraphBlock, ProposalDraftV2
from app.reports.proposal_validation import _collect_cited_ids
from app.synthesis.citation_engine import CitationEngine

FONT_NAME = "Times New Roman"
THEME_FONT_ATTRIBUTES = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")


def render_proposal_docx(
    draft: ProposalDraftV2,
    packet: EvidencePacket,
    output_path: Path,
) -> Path:
    """Render a validated proposal draft to an APA-styled Word document."""
    doc = Document()
    _apply_page_and_styles(doc)

    title = doc.add_paragraph()
    _format(title, WD_ALIGN_PARAGRAPH.CENTER)
    title.add_run(packet.topic).bold = True

    def body(blocks: Iterable[ParagraphBlock]) -> None:
        for block in blocks:
            _add_body(doc, packet, block.text, block.evidence_ids)

    doc.add_heading("Research Overview", level=1)
    body(draft.overview)

    doc.add_heading("Literature Review", level=1)
    for theme in draft.literature_insights:
        doc.add_heading(theme.title, level=2)
        body(theme.blocks)

    if draft.contradictions_and_limitations:
        doc.add_heading("Contradictions and Limitations in the Literature", level=2)
        body(draft.contradictions_and_limitations)

    doc.add_heading("Research Gap", level=1)
    body(draft.research_gap)

    doc.add_heading("Research Problem", level=1)
    body(draft.research_problem)

    doc.add_heading("Research Questions", level=1)
    for question in draft.research_questions:
        label = f"{question.question_id}: " if question.question_id else ""
        _add_body(doc, packet, f"{label}{question.text}", question.evidence_ids)

    doc.add_heading("Research Objectives", level=1)
    for number, objective in enumerate(draft.research_objectives, start=1):
        linked = f" (addresses {', '.join(objective.question_ids)})" if objective.question_ids else ""
        _add_body(doc, packet, f"Objective {number}{linked}: {objective.text}", objective.evidence_ids)

    doc.add_heading("Methodology", level=1)
    methodology_parts = (
        ("Research Design", draft.methodology.research_design),
        ("Data Collection", draft.methodology.data_collection),
        ("Analysis", draft.methodology.analysis),
        ("Quality Assurance and Limitations", draft.methodology.limitations),
    )
    for heading, blocks in methodology_parts:
        if blocks:
            doc.add_heading(heading, level=2)
            body(blocks)

    if draft.conclusion:
        doc.add_heading("Conclusion", level=1)
        body(draft.conclusion)

    if draft.evidence_limitations:
        doc.add_heading("Limitations of the Evidence", level=2)
        body(draft.evidence_limitations)

    _add_references(doc, draft, packet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


def _apply_page_and_styles(doc) -> None:
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Inches(1)
        section.left_margin = section.right_margin = Inches(1)

    _style_font(doc.styles["Normal"], bold=False)
    for name, level_bold, alignment in (
        ("Heading 1", True, WD_ALIGN_PARAGRAPH.CENTER),
        ("Heading 2", True, WD_ALIGN_PARAGRAPH.LEFT),
    ):
        style = doc.styles[name]
        _style_font(style, bold=level_bold)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.alignment = alignment
        style.paragraph_format.line_spacing = 2.0
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.keep_with_next = True


def _style_font(style, bold: bool) -> None:
    style.font.name = FONT_NAME
    style.font.size = Pt(12)
    style.font.bold = bold
    fonts = style.element.rPr.rFonts
    for attribute in THEME_FONT_ATTRIBUTES:
        fonts.attrib.pop(qn(attribute), None)
    for attribute in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attribute), FONT_NAME)


def _format(paragraph, alignment, first_line_indent=Inches(0)) -> None:
    paragraph.alignment = alignment
    paragraph_format = paragraph.paragraph_format
    paragraph_format.line_spacing = 2.0
    paragraph_format.space_before = Pt(0)
    paragraph_format.space_after = Pt(0)
    paragraph_format.first_line_indent = first_line_indent


def _add_body(doc, packet: EvidencePacket, text: str, evidence_ids: List[str]) -> None:
    sources = [packet.source_dicts[source_id] for source_id in evidence_ids if source_id in packet.source_dicts]
    paragraph = doc.add_paragraph(append_citation(text, sources))
    _format(paragraph, WD_ALIGN_PARAGRAPH.JUSTIFY)


def _add_references(doc, draft: ProposalDraftV2, packet: EvidencePacket) -> None:
    from app.agents.scribe_agent import ScribeResearchAgent

    cited_ids = _collect_cited_ids(draft) or set(packet.sent_source_ids)
    sources = [
        packet.source_dicts[source_id]
        for source_id in packet.sent_source_ids
        if source_id in cited_ids
        and source_id in packet.source_dicts
        and CitationEngine.is_referenceable(packet.source_dicts[source_id])
    ]

    doc.add_page_break()
    doc.add_heading("References", level=1)
    for source in sorted(sources, key=ScribeResearchAgent._apa_reference_sort_key):
        paragraph = doc.add_paragraph()
        _format(paragraph, WD_ALIGN_PARAGRAPH.LEFT, Inches(-0.5))
        paragraph.paragraph_format.left_indent = Inches(0.5)
        ScribeResearchAgent._add_apa_reference(paragraph, source)
