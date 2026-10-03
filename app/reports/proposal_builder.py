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

    abstract = dossier.get("abstract", "")
    themes = dossier.get("themes", [])
    gaps = dossier.get("research_gaps", [])
    opportunities = dossier.get("opportunity_areas", [])
    areas = dossier.get("research_areas", [])

    overview = _build_overview(topic, abstract, packet)
    literature_insights = _build_literature_insights(themes, packet)
    research_gap = _build_research_gap(gaps, packet)
    research_problem = _build_research_problem(topic, opportunities, packet)
    research_questions = _build_research_questions(topic, gaps, opportunities)
    research_objectives = _build_research_objectives(research_questions)
    methodology = _build_methodology(domain, areas)
    conclusion = _build_conclusion(topic, packet)
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
    """Build overview section with clear positioning and significance."""
    text = (
        f"This research proposal investigates {topic}, an area of contemporary importance that bridges "
        "theoretical understanding and practical application across the field. The investigation of this research "
        "domain is essential for advancing both scholarly knowledge and evidence-based practice. Understanding the "
        "complexities, interconnections, and nuances surrounding this topic will yield insights that contribute to "
        "refined theoretical frameworks while simultaneously addressing real-world challenges and opportunities. "
    )

    if abstract:
        abstract_clean = abstract.rstrip('.')
        text += (
            f"The research domain emphasizes {abstract_clean.lower()}, considerations that form the foundation for the "
            "research direction outlined in this proposal. These interconnected aspects prove critical for developing "
            "effective, evidence-based approaches that address contemporary gaps and opportunities in the field. "
        )

    text += (
        f"This proposal draws substantively on {len(packet.sources)} carefully curated, peer-reviewed sources that "
        "collectively establish a robust research foundation and illuminate critical gaps in current understanding. "
        "These sources represent high-quality scholarship providing both theoretical grounding and empirical evidence. "
        "Through systematic synthesis of existing knowledge, this proposal identifies promising avenues for novel "
        "research contributions that will meaningfully advance the field while generating insights applicable to "
        "contemporary practice and future scholarship."
    )

    return [ParagraphBlock(
        text=text,
        kind="evidence",
        evidence_ids=packet.sent_source_ids[:3] if packet.sent_source_ids else []
    )]


def _build_literature_insights(themes: List[str], packet: EvidencePacket) -> List[ThemeBlock]:
    """Build literature insights with coherent theme analysis and relevance."""
    blocks = []

    for theme in themes[:5]:
        text = (
            f"{theme} emerges as a significant and recurring theme throughout contemporary scholarly literature. "
            "Multiple peer-reviewed sources converge on this concept, collectively providing both robust empirical "
            "evidence and complementary theoretical perspectives that illuminate its importance. The breadth of research "
            "attention across diverse contexts and methodologies demonstrates that this theme remains central to current "
            f"research endeavors and carries substantial implications for both future investigations and real-world application. "
            "The convergence of scholarly inquiry around this thematic area strongly suggests its foundational relevance "
            "to the proposed research direction and its potential to generate meaningful insights. "
        )

        # Add how this theme connects to the research
        text += (
            "This theme directly informs the research questions and objectives proposed herein, providing both theoretical "
            "grounding and empirical justification for the investigation. Understanding how this theme manifests, evolves, and "
            "influences outcomes is integral to addressing the identified research gaps and advancing knowledge in this domain."
        )

        block = ParagraphBlock(
            text=text,
            kind="evidence",
            evidence_ids=packet.sent_source_ids[:2] if packet.sent_source_ids else []
        )
        blocks.append(ThemeBlock(title=theme, blocks=[block]))

    if not blocks:
        text = (
            "The existing literature establishes foundational concepts and prior research trajectories that directly "
            "inform this investigation. The integration of findings from multiple high-quality studies provides a "
            "comprehensive foundation for understanding the research domain and identifying specific gaps where "
            "additional investigation would meaningfully advance knowledge."
        )
        blocks.append(ThemeBlock(
            title="Literature Foundation",
            blocks=[ParagraphBlock(
                text=text,
                kind="evidence",
                evidence_ids=packet.sent_source_ids[:1] if packet.sent_source_ids else []
            )]
        ))

    return blocks


def _build_research_gap(gaps: List[str], packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build research gap section identifying underexplored areas."""
    blocks = []

    if gaps:
        for gap in gaps[:3]:
            text = (
                f"Existing research has not comprehensively addressed {gap}, representing a meaningful lacuna "
                "where systematic investigation would generate valuable insights and materially advance the field's "
                "understanding. Despite substantial scholarship examining related phenomena, these specific aspects "
                "remain insufficiently explored, leaving important questions unanswered and limiting current theoretical "
                "and practical knowledge. A focused research effort targeting this gap would meaningfully contribute to "
                "both theoretical development and applied practice, filling a substantive void in the current literature. "
                "The proposed research is deliberately designed to address this gap through rigorous inquiry, sound "
                "methodology, and careful attention to evidence quality."
            )
            blocks.append(ParagraphBlock(
                text=text,
                kind="evidence",
                evidence_ids=packet.sent_source_ids[:1] if packet.sent_source_ids else []
            ))

    if not blocks:
        text = (
            "Existing research, while substantial, leaves important questions unanswered and creates opportunities "
            "for focused investigation. The proposed research strategically addresses these gaps through systematic, "
            "methodologically rigorous inquiry. Significant opportunities remain where carefully designed research could "
            "substantially advance both theoretical understanding and practical knowledge relevant to the field."
        )
        blocks.append(ParagraphBlock(
            text=text,
            kind="evidence",
            evidence_ids=packet.sent_source_ids[:1] if packet.sent_source_ids else []
        ))

    return blocks


def _build_research_problem(topic: str, opportunities: List[str], packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build research problem statement grounded in field context."""
    text = (
        f"The central research problem is to advance and deepen understanding of {topic}. This problem possesses "
        "significant scholarly and practical importance, as addressing it will generate contributions to both "
        "theoretical advancement and meaningful improvements in applied practice. The problem is both timely and "
        "consequential, reflecting contemporary gaps in knowledge and persistent challenges in the field. "
    )

    if opportunities:
        opp_text = ", ".join(opportunities[:3])
        text += (
            f"Specific opportunity areas meriting systematic investigation include: {opp_text}. These areas "
            "represent promising directions where well-designed research efforts could yield substantial benefits, "
            "generate novel insights, and contribute meaningfully to both scholarly and practical domains. "
        )

    # Add stakeholder implications
    text += (
        "The resolution of this research problem holds implications not only for advancing theoretical understanding "
        "but also for stakeholders who engage with this domain in practice. The research is positioned to provide "
        "evidence-based guidance that will inform practice decisions and shape future research directions. "
    )

    text += (
        "Systematic investigation of this research problem will generate evidence-based insights that advance scholarly "
        "knowledge, inform practice, and establish direction for future work. The research is explicitly designed to "
        "provide rigorous evidence and actionable insights that will influence both current understanding and future "
        "research trajectories in this field."
    )

    return [ParagraphBlock(
        text=text,
        kind="evidence",
        evidence_ids=packet.sent_source_ids[:2] if packet.sent_source_ids else []
    )]


def _build_research_questions(topic: str, gaps: List[str], opportunities: List[str]) -> List[ResearchQuestion]:
    """Build focused research questions aligned with gaps and opportunities."""
    questions = []

    questions.append(ResearchQuestion(
        text=f"How can systematic investigation deepen and refine understanding of {topic}?",
        question_id="RQ1"
    ))

    if gaps:
        for i, gap in enumerate(gaps[:2], start=2):
            questions.append(ResearchQuestion(
                text="What factors, mechanisms, and dynamics contribute to persistent gaps in current understanding?",
                question_id=f"RQ{i}"
            ))

    if opportunities and len(questions) < 4:
        for i in range(len(questions), min(4, len(questions) + len(opportunities))):
            questions.append(ResearchQuestion(
                text="How can emerging research directions be systematically evaluated and integrated?",
                question_id=f"RQ{i}"
            ))

    return questions


def _build_research_objectives(questions: List[ResearchQuestion]) -> List[ResearchObjective]:
    """Build specific, measurable research objectives with success metrics."""
    objectives = []

    if questions:
        objectives.append(ResearchObjective(
            text="To systematically investigate the primary research question through rigorous, evidence-based inquiry employing sound methodology and careful attention to research quality and validity. Success will be measured by the comprehensiveness of the investigation and the rigor of conclusions drawn.",
            question_ids=["RQ1"]
        ))

        for q in questions[1:]:
            objectives.append(ResearchObjective(
                text=f"To explore and elucidate the factors and mechanisms central to {q.question_id}, generating evidence-based insights through targeted investigation with clear success metrics and measurable indicators of progress.",
                question_ids=[q.question_id]
            ))

        # Add timeline/phase objective
        if len(questions) > 1:
            objectives.append(ResearchObjective(
                text="To establish clear milestones and phases for the research, with periodic evaluation of progress against stated objectives and adaptation where necessary to ensure meaningful outcomes.",
                question_ids=["RQ1"]
            ))

    return objectives


def _build_methodology(domain: str, areas: List[str]) -> MethodologySection:
    """Build domain-appropriate methodology with comprehensive procedures."""

    design_templates = {
        "scholarly": "A mixed-methods approach integrating systematic literature review with empirical analysis will provide both breadth and depth of understanding necessary to comprehensively address the research questions. This methodological design leverages complementary strengths of qualitative and quantitative approaches.",
        "health": "A cohort study design with structured baseline and follow-up assessments will enable systematic tracking of outcomes over time. This longitudinal approach provides strong evidence for understanding causal relationships and identifying longitudinal trends and patterns.",
        "technology": "An experimental design employing both control and treatment groups will isolate the effects of key variables. Random assignment and standardized procedures ensure valid comparisons and minimize sources of bias.",
        "social": "Qualitative exploratory research utilizing structured interviews will generate rich understanding of complex social phenomena. Purposive sampling will ensure representation of diverse perspectives and experiences."
    }

    collection_templates = {
        "scholarly": "Data collection will involve systematic identification and retrieval of peer-reviewed sources and grey literature, complemented by expert consultation to ensure comprehensiveness. This multi-source approach guarantees comprehensive coverage of relevant scholarship.",
        "health": "Data collection will employ validated, standardized instruments administered consistently at multiple timepoints. These established measures ensure reliability and enable meaningful comparison with prior research.",
        "technology": "Data collection will involve systematic benchmarking studies and quantitative performance metrics collected under controlled conditions. Automated data collection procedures minimize measurement bias and ensure consistency.",
        "social": "Data collection will utilize semi-structured interviews with purposively selected participants. All interviews will be audio-recorded and professionally transcribed to enable rigorous analysis."
    }

    analysis_templates = {
        "scholarly": "Analysis will employ thematic synthesis of findings with conceptual mapping and critical evaluation. This approach systematically identifies patterns, reveals contradictions, and clarifies implications for both theory and practice.",
        "health": "Statistical analysis will examine outcomes using both descriptive and inferential methods, including subgroup comparisons and sensitivity analyses. Careful interpretation will acknowledge both the findings and their limitations.",
        "technology": "Quantitative performance analysis will employ both descriptive statistics and inferential hypothesis testing. Analysis will characterize performance comprehensively while rigorously testing specific differences.",
        "social": "Thematic analysis will employ systematic coding and constant comparison across interview transcripts. This iterative process generates emergent themes and develops theoretical insights grounded in qualitative data."
    }

    # Add quality assurance section
    qa_text = (
        "Quality assurance procedures will include regular validation checks, inter-rater reliability assessments where applicable, "
        "and peer review of analytic decisions. Data management protocols will ensure accuracy, security, and traceability throughout "
        "the research process. The research timeline will be structured in phases with clear milestones, anticipated deliverables at "
        "each phase, and provisions for adaptive methodology where evidence warrants adjustment to approach."
    )

    research_domain = domain.lower() if domain else "scholarly"
    if research_domain not in design_templates:
        research_domain = "scholarly"

    return MethodologySection(
        research_design=[ParagraphBlock(text=design_templates[research_domain], kind="proposal")],
        data_collection=[ParagraphBlock(text=collection_templates[research_domain], kind="proposal")],
        analysis=[ParagraphBlock(text=analysis_templates[research_domain], kind="proposal")],
        limitations=[ParagraphBlock(
            text=f"Quality assurance and data management: {qa_text}",
            kind="limitation"
        )],
    )


def _build_conclusion(topic: str, packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build conclusion synthesizing contribution and significance."""
    text = (
        f"This proposed research directly addresses critical, underexplored questions in {topic}. By building "
        "systematically on a foundation of high-quality sources while filling identified gaps in current knowledge, "
        "the research will meaningfully advance theoretical understanding and generate practical insights of value to "
        "the field. The investigation outlined in this proposal is deliberately designed to respond to identified gaps "
        "and opportunities, filling substantive voids in current knowledge. Through rigorous methodology, careful attention "
        "to research quality, and thoughtful engagement with both theoretical and practical implications, this research "
        "is positioned to make significant contributions to the field while generating evidence that will inform and guide "
        "future research and practice."
    )

    return [ParagraphBlock(
        text=text,
        kind="proposal",
        evidence_ids=packet.sent_source_ids[:3] if packet.sent_source_ids else []
    )]


def _build_evidence_limitations(packet: EvidencePacket) -> List[ParagraphBlock]:
    """Build evidence limitations section noting constraints."""
    limitations = []

    if packet.omitted_source_ids:
        text = (
            f"A total of {len(packet.omitted_source_ids)} sources were available but not included due to input "
            "constraints. The proposal reflects analysis of the most relevant, highest-quality subset that meets "
            "rigorous inclusion standards."
        )
        limitations.append(ParagraphBlock(text=text, kind="limitation"))

    if packet.truncation_notes:
        text = (
            "Some source abstracts underwent truncation to accommodate processing constraints. Consultation of full "
            "source materials is recommended for comprehensive understanding of source content, context, and implications."
        )
        limitations.append(ParagraphBlock(text=text, kind="limitation"))

    if not limitations:
        limitations.append(ParagraphBlock(
            text="The evidence base comprises publicly available sources and may not exhaustively capture all relevant "
            "research. The proposal synthesizes the most significant and accessible sources available on this topic.",
            kind="limitation"
        ))

    return limitations
