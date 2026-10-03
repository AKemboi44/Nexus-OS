"""Non-AI proposal synthesis using research data and deterministic templates."""

from app.reports.proposal_schema import (
    ProposalDraftV2, ParagraphBlock, ThemeBlock, ResearchQuestion,
    ResearchObjective, MethodologySection
)
from app.reports.evidence_preparation import EvidencePacket
from typing import List, Dict, Any


def build_proposal_from_research(
    topic: str,
    domain: str,
    dossier: Dict[str, Any],
    packet: EvidencePacket,
) -> ProposalDraftV2:
    """
    Build a research proposal deterministically from research data.
    No LLM calls - uses dossier, sources, and smart templates.
    """

    # Extract dossier data
    abstract = dossier.get("abstract", "")
    themes = dossier.get("themes", [])
    gaps = dossier.get("research_gaps", [])
    opportunities = dossier.get("opportunity_areas", [])
    areas = dossier.get("research_areas", [])

    # Build sections
    overview = _build_overview(topic, abstract, packet)
    literature_insights = _build_literature_insights(themes, packet)
    research_gap = _build_research_gap(gaps, packet)
    research_problem = _build_research_problem(topic, opportunities, packet)
    research_questions = _build_research_questions(topic, gaps, opportunities)
    research_objectives = _build_research_objectives(research_questions)
    methodology = _build_methodology(domain, areas)
    conclusion = _build_conclusion(topic, gaps, packet)
    evidence_limitations = _build_evidence_limitations(packet)

    return ProposalDraftV2(
        schema_version="proposal.v2",
        overview=overview,
        literature_insights=literature_insights,
        contradictions_and_limitations=[],
        research_gap=research_gap,
        research_problem=research_problem,
        research_questions=research_questions,
        research_objectives=research_objectives,
        methodology=methodology,
        conclusion=conclusion,
        evidence_limitations=evidence_limitations,
    )


def _build_overview(topic: str, abstract: str, packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build overview section from topic and abstract."""
    text = f"This research proposal investigates {topic}. "

    if abstract:
        text += f"The research domain emphasizes {abstract}. "

    text += f"This proposal draws on {len(packet.sources)} key sources to establish the research foundation and identify critical gaps in current understanding."

    return [ParagraphBlock(
        text=text,
        kind="evidence",
        evidence_ids=packet.sent_source_ids[:3] if packet.sent_source_ids else []
    )]


def _build_literature_insights(themes: List[str], packet: EvidencePacket) -> List[ThemeBlock]:
    """Build literature insights from dossier themes."""
    blocks = []

    # Use up to 5 themes
    for theme in themes[:5]:
        text = f"{theme} emerges as a significant theme in the literature. "
        text += f"Multiple sources contribute to this understanding, providing empirical grounding and theoretical context."

        block = ParagraphBlock(
            text=text,
            kind="evidence",
            evidence_ids=packet.sent_source_ids[:2] if packet.sent_source_ids else []
        )
        blocks.append(ThemeBlock(title=theme, blocks=[block]))

    if not blocks:
        # Fallback if no themes
        blocks.append(ThemeBlock(
            title="Literature Foundation",
            blocks=[ParagraphBlock(
                text="The literature base establishes key concepts and prior research that inform this investigation.",
                kind="evidence",
                evidence_ids=packet.sent_source_ids[:1] if packet.sent_source_ids else []
            )]
        ))

    return blocks


def _build_research_gap(gaps: List[str], packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build research gap section from identified gaps."""
    blocks = []

    if gaps:
        for gap in gaps[:3]:
            text = f"Current research has not fully addressed {gap}. "
            text += "This represents a meaningful gap where additional investigation could provide valuable insights."
            blocks.append(ParagraphBlock(
                text=text,
                kind="evidence",
                evidence_ids=packet.sent_source_ids[:1] if packet.sent_source_ids else []
            ))

    if not blocks:
        blocks.append(ParagraphBlock(
            text="Existing research leaves open questions that warrant further investigation. This proposal addresses those gaps through focused inquiry.",
            kind="evidence",
            evidence_ids=packet.sent_source_ids[:1] if packet.sent_source_ids else []
        ))

    return blocks


def _build_research_problem(topic: str, opportunities: List[str], packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build research problem section."""
    text = f"The central research problem is to advance understanding of {topic}. "

    if opportunities:
        text += f"Specific opportunity areas include: {', '.join(opportunities[:3])}. "

    text += "Addressing this problem will contribute to both theoretical and practical understanding."

    return [ParagraphBlock(
        text=text,
        kind="evidence",
        evidence_ids=packet.sent_source_ids[:2] if packet.sent_source_ids else []
    )]


def _build_research_questions(topic: str, gaps: List[str], opportunities: List[str]) -> List[ResearchQuestion]:
    """Build research questions from gaps and opportunities."""
    questions = []

    # Primary question
    questions.append(ResearchQuestion(
        text=f"How can we deepen understanding of {topic}?",
        question_id="RQ1"
    ))

    # Secondary questions from gaps
    if gaps:
        for i, gap in enumerate(gaps[:2], start=2):
            questions.append(ResearchQuestion(
                text=f"What factors influence {gap.lower()}?",
                question_id=f"RQ{i}"
            ))

    # Additional questions from opportunities
    if opportunities and len(questions) < 4:
        for i, opp in enumerate(opportunities[:1], start=len(questions)+1):
            questions.append(ResearchQuestion(
                text=f"How can we explore {opp.lower()} more thoroughly?",
                question_id=f"RQ{i}"
            ))

    return questions


def _build_research_objectives(questions: List[ResearchQuestion]) -> List[ResearchObjective]:
    """Build research objectives from questions."""
    objectives = []

    if questions:
        # General objective
        objectives.append(ResearchObjective(
            text="To systematically investigate the research questions through evidence-based inquiry",
            question_ids=["RQ1"]
        ))

        # Specific objectives for other questions
        for q in questions[1:]:
            objectives.append(ResearchObjective(
                text=f"To explore the specific aspects raised in {q.question_id}",
                question_ids=[q.question_id]
            ))

    return objectives


def _build_methodology(domain: str, areas: List[str]) -> MethodologySection:
    """Build methodology section with domain-aware templates."""

    design_template = {
        "scholarly": "Mixed-methods approach combining systematic literature review with empirical analysis",
        "health": "Cohort study design with baseline and follow-up assessments",
        "technology": "Experimental design with control and treatment groups",
        "social": "Qualitative exploratory research with structured interviews",
    }

    collection_template = {
        "scholarly": "Systematic collection of peer-reviewed sources and grey literature, complemented by expert consultation",
        "health": "Standardized instruments for data collection at multiple timepoints",
        "technology": "Benchmarking studies and performance metrics collected in controlled environments",
        "social": "Semi-structured interviews with purposive sampling to ensure diverse perspectives",
    }

    analysis_template = {
        "scholarly": "Thematic synthesis of findings with conceptual mapping and critical evaluation",
        "health": "Statistical analysis of outcomes with subgroup comparisons and sensitivity analyses",
        "technology": "Quantitative performance analysis with statistical significance testing",
        "social": "Thematic coding and constant comparison across interview transcripts",
    }

    # Get domain or default to "scholarly"
    research_domain = domain.lower() if domain else "scholarly"
    if research_domain not in design_template:
        research_domain = "scholarly"

    design = design_template[research_domain]
    collection = collection_template[research_domain]
    analysis = analysis_template[research_domain]

    return MethodologySection(
        research_design=[ParagraphBlock(text=design, kind="proposal")],
        data_collection=[ParagraphBlock(text=collection, kind="proposal")],
        analysis=[ParagraphBlock(text=analysis, kind="proposal")],
        limitations=[ParagraphBlock(
            text="This research acknowledges inherent limitations in scope, timeframe, and generalizability. Findings should be interpreted within these constraints.",
            kind="limitation"
        )],
    )


def _build_conclusion(topic: str, gaps: List[str], packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build conclusion section."""
    text = f"This proposed research addresses critical questions in {topic}. "
    text += f"By building on the foundation of {len(packet.sources)} key sources and filling identified gaps, "
    text += "the research will advance theoretical understanding and provide practical insights for future work."

    return [ParagraphBlock(
        text=text,
        kind="proposal",
        evidence_ids=packet.sent_source_ids[:3] if packet.sent_source_ids else []
    )]


def _build_evidence_limitations(packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build evidence limitations section."""
    limitations = []

    if packet.omitted_source_ids:
        text = f"A total of {len(packet.omitted_source_ids)} sources were available but not included due to input constraints. "
        text += "The proposal reflects analysis of the most relevant subset."
        limitations.append(ParagraphBlock(text=text))

    if packet.truncation_notes:
        text = "Some source abstracts were truncated to fit within processing limits. "
        text += "Full abstracts should be consulted for complete understanding of source content."
        limitations.append(ParagraphBlock(text=text))

    if not limitations:
        limitations.append(ParagraphBlock(
            text="The evidence base is limited to publicly available sources and may not capture all relevant research. "
        ))

    return limitations
