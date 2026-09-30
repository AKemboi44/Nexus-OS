from app.research.publication_quality import PublicationQualityGate
from app.agents.reviewer_agent import ReviewerAgent


class DummyDossier:
    def __init__(self):
        self.abstract = "This review synthesizes evidence from peer-reviewed sources about the topic."
        self.themes = ["Theme one"]
        self.contradictions = ["Contradiction one"]
        self.research_gaps = ["Gap one"]
        self.opportunity_areas = ["Opportunity one"]
        self.problems_to_solve = ["Problem one"]


def test_quality_gate_accepts_quality_source_set():
    gate = PublicationQualityGate()
    dossier = DummyDossier()
    sources = [
        {
            "title": "High quality evidence on research methods",
            "abstract": "This study examines a rigorous research method and summarizes outcomes across cases with strong methodological detail.",
            "year": 2024,
            "authors": ["Smith, J.", "Jones, A."],
            "is_peer_reviewed": True,
            "url": "https://example.com/1",
        },
        {
            "title": "Comparative findings in applied synthesis",
            "abstract": "A comparative study of implementation outcomes provides evidence relevant to the reviewed research problem and its settings.",
            "year": 2023,
            "authors": ["Brown, R."],
            "is_peer_reviewed": True,
            "url": "https://example.com/2",
        },
    ]

    report = gate.validate_dossier(dossier, sources)

    assert report["passed"] is True
    assert report["score"] >= 0.85


def test_generation_contract_requires_publication_sections():
    gate = PublicationQualityGate()
    prompt = gate.build_generation_contract("AI-assisted peer review")

    assert "ABSTRACT" in prompt
    assert "KEY THEMES" in prompt
    assert "RESEARCH GAPS" in prompt
    assert "PUBLICATION-QUALITY" in prompt.upper()


def test_quality_thresholds_are_report_specific(monkeypatch):
    gate = PublicationQualityGate()

    assert gate.threshold_for("proposal") == 0.85
    assert gate.threshold_for("full_starter") == 0.90

    monkeypatch.setenv("NEXUS_QUALITY_THRESHOLD_FULL_STARTER", "0.97")
    assert gate.threshold_for("full_starter") == 0.97


def test_doi_title_conflict_fails_citation_validation():
    gate = PublicationQualityGate()
    sources = [
        {
            "title": "A study of research quality",
            "abstract": "This abstract contains enough evidence description to satisfy the source metadata quality check.",
            "year": 2024,
            "authors": ["Smith"],
            "doi": "10.1000/example",
        },
        {
            "title": "A completely different study",
            "abstract": "This abstract contains enough evidence description to satisfy the source metadata quality check.",
            "year": 2024,
            "authors": ["Smith"],
            "doi": "https://doi.org/10.1000/example",
        },
    ]

    report = gate.validate_citations(sources)

    assert report["score"] < 1.0
    assert report["issues"]


def test_reviewer_reports_editorial_issues_without_llm():
    reviewer = ReviewerAgent()
    reviewer.client = None
    reviewer.has_llm = False

    result = reviewer.execute(
        insight="This is a short claim that clearly proves everything.",
        evidence_items=[],
    )

    assert result["status"] == "reviewed"
    assert result["editorial_issues"]
    assert result["score"] < 0.85
