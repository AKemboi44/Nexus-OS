from app.agents.scribe_agent import ScribeResearchAgent
import json
from types import SimpleNamespace
from docx import Document
from docx.shared import Inches


def test_scribe_deduplicates_section_items():
    agent = ScribeResearchAgent()
    agent.client = None

    items = agent._unique_items([
        "Evidence supports careful evaluation.",
        "Evidence supports careful evaluation.",
        "Different wording should remain.",
    ])

    assert items == [
        "Evidence supports careful evaluation.",
        "Different wording should remain.",
    ]


def test_scribe_does_not_append_repeated_citation_or_template_prose():
    agent = ScribeResearchAgent()
    agent.client = None
    sources = [
        {
            "title": "Research quality study",
            "authors": ["Abdar"],
            "year": 2021,
            "abstract": "This study provides enough evidence detail for a grounded paragraph about research quality and implementation.",
        }
    ]

    paragraph = agent._evidence_paragraph(
        "Evidence supports careful evaluation. (Abdar, 2021)",
        sources,
    )

    assert paragraph.count("Abdar, 2021") == 1
    assert "The selected studies report related findings" not in paragraph
    assert "This distinction matters" not in paragraph


def test_scribe_paragraph_is_concise_and_evidence_bounded():
    agent = ScribeResearchAgent()
    agent.client = None
    sources = [
        {
            "title": "Research quality study",
            "authors": ["Abdar"],
            "year": 2021,
            "abstract": "This study provides enough evidence detail for a grounded paragraph about research quality and implementation.",
        }
    ]

    paragraph = agent._evidence_paragraph(
        "Evidence supports careful evaluation of the research problem.",
        sources,
        topic="research quality",
        section="Key Themes",
        report_type="proposal",
    )
    words = paragraph.split()
    citation_index = paragraph.index("(Abdar, 2021)")
    before = paragraph[:citation_index]
    after = paragraph[citation_index + len("(Abdar, 2021)"):]

    assert len(words) < 60
    assert before.strip().endswith("Evidence supports careful evaluation of the research problem")
    assert after == "."
    assert paragraph.count("(Abdar, 2021)") == 1
    assert "(Abdar, 2021)." in paragraph
    assert ". (Abdar, 2021)" not in paragraph


def test_scribe_keeps_long_claims_focused_without_stock_padding():
    agent = ScribeResearchAgent()
    agent.client = None
    sources = [
        {
            "title": "A very long source title describing an extensive multi-dimensional investigation of research quality, implementation, measurement, and transferability",
            "authors": ["Abdar"],
            "year": 2021,
            "abstract": "This study provides enough evidence detail for a grounded paragraph about research quality and implementation.",
        }
    ]

    paragraph = agent._evidence_paragraph(
        "This is a deliberately long synthesized theme that contains many methodological, contextual, operational, and analytical dimensions which must remain focused on the same research question.",
        sources,
        topic="research quality",
        section="Key Themes",
        report_type="proposal",
    )

    assert len(paragraph.split()) < 80
    assert paragraph.count(".") <= 3


def test_scribe_replaces_garbled_repetitive_abstract_with_clean_fallback():
    agent = ScribeResearchAgent()
    abstract = agent._format_abstract(
        "There is is is is a a a failure failure mode in in large large models.",
        "language model reliability",
        [],
    )

    assert "is is" not in abstract
    assert "a a" not in abstract
    assert "failure failure" not in abstract
    assert "thatwe" not in abstract
    assert "Keywords:" in abstract
    assert len(abstract.split()) >= 100


def test_scribe_prose_cleanup_handles_long_repeated_input():
    repeated_dash = "claim" + ("--" * 10000) + "supported"
    repeated_words = ("evidence " * 10000).strip()

    cleaned = ScribeResearchAgent._clean_prose(
        f"{repeated_dash}; {repeated_words}"
    )

    assert "--" not in cleaned
    assert "evidence evidence" not in cleaned
    assert cleaned.endswith("evidence")


def test_scribe_uses_academic_first_line_indentation_for_body_prose():
    document = Document()
    ScribeResearchAgent._add_body_paragraph(document, "A developed research paragraph.")
    ScribeResearchAgent._add_body_paragraph(
        document,
        "An abstract paragraph.",
        first_line_indent=0,
    )

    assert document.paragraphs[0].paragraph_format.first_line_indent == Inches(0.5)
    assert document.paragraphs[1].paragraph_format.first_line_indent == 0


def test_scribe_formats_publication_style_abstract_with_keywords():
    agent = ScribeResearchAgent()
    agent.client = None
    abstract = agent._format_abstract(
        "This review examines token optimization and compares prompt compression with dynamic pruning.",
        "token optimization",
        [],
    )

    assert "Keywords:" in abstract
    assert len(abstract.split()) >= 80
    assert "This review examines" in abstract


def test_scribe_removes_parenthetical_year_citations_without_regex_backtracking():
    cleaned = ScribeResearchAgent._remove_parenthetical_years(
        "Evidence supports this claim (Author, 2021), but keeps this note (important context)."
    )

    assert cleaned == "Evidence supports this claim, but keeps this note (important context)."


def test_scribe_parses_keyword_label_with_optional_spacing():
    agent = ScribeResearchAgent()
    agent.client = None

    abstract = agent._format_abstract(
        "A sufficiently detailed review abstract discusses evidence across methods and settings. "
        "Keywords : research quality, validation",
        "research quality",
        [],
    )

    assert "Keywords: research quality, validation." in abstract


def test_synthesis_parser_reads_research_areas_and_inline_abstract_heading():
    from app.reports.dossier_generator import DossierGenerator
    from models.research_dossier import ResearchDossier

    dossier = ResearchDossier("research quality")
    DossierGenerator()._parse_synthesis_payload(
        "### ABSTRACT: This review evaluates research quality across study settings.\n"
        "### RESEARCH AREAS\n"
        "- Compare measurement approaches across the included study populations.\n"
        "### OPPORTUNITY AREAS\n"
        "- Test a practical quality-assessment workflow for research teams.\n",
        dossier,
    )

    assert dossier.abstract == "This review evaluates research quality across study settings."
    assert dossier.research_areas == [
        "Compare measurement approaches across the included study populations."
    ]
    assert dossier.opportunity_areas == [
        "Test a practical quality-assessment workflow for research teams."
    ]


def test_scribe_cleans_space_before_punctuation():
    cleaned = ScribeResearchAgent._remove_incomplete_fragments(
        "Evidence remains useful , despite limits ."
    )

    assert cleaned == "Evidence remains useful, despite limits."


def test_complete_literature_review_contains_paper_components():
    agent = ScribeResearchAgent()
    agent.client = None
    sections = []

    class FakeDoc:
        def add_paragraph(self):
            class Paragraph:
                alignment = None
                paragraph_format = type("Format", (), {})()

                def add_run(self, text=""):
                    sections.append(str(text))
                    return type(
                        "Run",
                        (),
                        {"font": type("Font", (), {})()},
                    )()

            return Paragraph()

    sources = [{
        "title": "Research quality study",
        "authors": ["Abdar"],
        "year": 2021,
        "abstract": "This study provides enough evidence detail for a grounded paragraph about research quality and implementation.",
    }]
    agent._write_full_starter_sections(
        FakeDoc(),
        "research quality",
        sources,
        ["A recurring evidence theme."],
        ["A contextual disagreement."],
        ["A methodological gap."],
        ["A practical opportunity."],
        ["A research problem."],
        "scholarly",
        research_areas=["Compare methods across the included studies."],
    )

    output = " ".join(sections)
    for heading in (
        "Research Objectives",
        "Recommended Research Areas",
        "Conceptual Framework",
        "Methodology",
        "Data Collection",
        "Synthesis Findings",
        "Discussion",
        "Proposed Research Direction",
        "Operationalization and Study Design",
        "Conclusion",
    ):
        assert heading in output


def test_report_editorial_synthesis_expands_each_theme_from_source_evidence():
    agent = ScribeResearchAgent()
    source = {
        "title": "Research quality study",
        "authors": ["Abdar"],
        "year": 2021,
        "abstract": "The study examines research quality and implementation across multiple settings.",
    }

    class FakeModels:
        calls = 0

        def generate_content(self, model, contents):
            self.calls += 1
            assert "Integrate concepts into an argument" in contents
            payload = json.loads(contents.split("Report sections:", 1)[1])
            paragraphs = []
            for entry in payload:
                claim = entry["claim"].rstrip(".")
                text = (
                    f"For the research topic, {claim} provides a focused way to interpret the evidence. "
                    "The supplied source records place this idea within a defined research context and "
                    "help distinguish it from an assumption that would apply to every setting. Read "
                    "together, the evidence supports considering how the relevant concepts relate, while "
                    "the available abstracts do not establish that the same relationship holds across "
                    "all populations or methods. This qualification matters because it keeps the synthesis "
                    "proportionate to the material reviewed. Future studies should specify the population, "
                    "measures, and contextual conditions needed to test the proposition and assess its "
                    "relevance before translating it into practice."
                )
                paragraphs.append({"id": entry["id"], "text": text})
            return SimpleNamespace(text=json.dumps({"paragraphs": paragraphs}))

    class FakeClient:
        models = FakeModels()

    agent.client = FakeClient()
    agent._prepare_editorial_synthesis(
        "research quality",
        [source],
        ["Quality measurement varies across research settings."],
        [],
        [],
        [],
        [],
        [],
        "proposal",
        "scholarly",
    )

    paragraph = agent._evidence_paragraph(
        "Quality measurement varies across research settings.",
        [source],
        topic="research quality",
        section="Key Themes",
    )
    assert agent.client.models.calls == 1
    assert agent._editorial_synthesis_complete is True
    assert len(paragraph.split()) >= 75
    assert paragraph.count("(Abdar, 2021)") == 1
    assert "Future studies should specify the population" in paragraph
