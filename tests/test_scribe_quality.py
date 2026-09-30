from app.agents.scribe_agent import ScribeResearchAgent


def test_scribe_deduplicates_section_items():
    agent = ScribeResearchAgent()

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


def test_scribe_paragraph_has_centered_citation_and_required_length():
    agent = ScribeResearchAgent()
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

    assert len(words) >= 75
    assert len([s for s in before.split(".") if s.strip()]) >= 3
    assert len([s for s in after.split(".") if s.strip()]) >= 3
    assert paragraph.count("(Abdar, 2021)") == 1


def test_scribe_compacts_long_claims_without_losing_six_sentence_structure():
    agent = ScribeResearchAgent()
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

    assert len(paragraph.split()) >= 75
    assert paragraph.count(".") >= 6


def test_scribe_formats_publication_style_abstract_with_keywords():
    agent = ScribeResearchAgent()
    abstract = agent._format_abstract(
        "This review examines token optimization and compares prompt compression with dynamic pruning.",
        "token optimization",
        [],
    )

    assert "Keywords:" in abstract
    assert len(abstract.split()) >= 80
    assert "This review examines" in abstract


def test_complete_literature_review_contains_paper_components():
    agent = ScribeResearchAgent()
    sections = []

    class FakeDoc:
        def add_paragraph(self):
            class Paragraph:
                alignment = None
                paragraph_format = type("Format", (), {})()

                def add_run(self, text=""):
                    sections.append(str(text))
                    return type("Run", (), {})()

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
    )

    output = " ".join(sections)
    for heading in (
        "Research Objectives",
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
