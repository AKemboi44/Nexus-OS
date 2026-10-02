from openpyxl import load_workbook
from app.research.spelling import normalize_topic_spelling, correct_word
from app.research.research_pipeline import ResearchPipeline
from app.reports.dossier_generator import DossierGenerator
from app.synthesis.insight_engine import ResearchInsight


def test_correct_word_common_typos():
    assert correct_word("oken") == "token"
    assert correct_word("Oken") == "Token"
    assert correct_word("OKEN") == "TOKEN"
    assert correct_word("ptimization") == "optimization"
    assert correct_word("echniques") == "techniques"
    assert correct_word("esilient") == "resilient"
    assert correct_word("eployment") == "deployment"


def test_normalize_topic_spelling_full_phrase():
    raw_topic = "Oken optimization techniques for resilient cost control and ai deployment"
    normalized = normalize_topic_spelling(raw_topic)
    assert normalized == "Token optimization techniques for resilient cost control and ai deployment"


def test_normalize_topic_spelling_preserves_valid():
    valid = "Token optimization techniques for resilient cost control and ai deployment"
    assert normalize_topic_spelling(valid) == valid


def test_research_pipeline_normalizes_misspelled_query(monkeypatch, tmp_path):
    pipeline = ResearchPipeline()

    test_sources = [
        {
            "uid": "test_src_1",
            "title": "Token optimization for compilers",
            "abstract": "An evaluation of token optimization techniques in compiler pipelines.",
            "year": 2024,
            "doi": "10.1000/token1",
            "url": "https://example.org/token1",
            "venue": "ACM Transactions",
            "citation_count": 12,
            "is_peer_reviewed": True,
            "authors": ["A. Smith"],
        }
    ]

    monkeypatch.setattr(pipeline, "_discover_sources_real", lambda query, max_sources=5, selected_reasons=None: {
        "included": [test_sources[0].copy()],
        "excluded": [],
        "audit": {
            "candidates_retrieved": 1,
            "unique_candidates_reviewed": 1,
            "active_criteria": ["Topic relevance"],
        }
    })
    monkeypatch.setattr(
        pipeline.insight_engine,
        "generate_insight",
        lambda *args: ResearchInsight("Token optimization", "A concise synthesis.", []),
    )

    result = pipeline.run_research(
        "Oken optimization techniques for resilient cost control and ai deployment",
        max_sources=1,
        output_directory=str(tmp_path),
    )

    # Dossier and workbook should have corrected topic
    assert result.query == "Token optimization techniques for resilient cost control and ai deployment"
    
    excel_path = result.report_data["excel_report_saved_at"]
    workbook = load_workbook(excel_path)
    summary_rows = dict(list(workbook["Executive Summary"].values)[1:])
    assert summary_rows["Research topic"] == "Token optimization techniques for resilient cost control and ai deployment"

    config_rows = dict(list(workbook["Run Audit Configuration"].values)[1:])
    assert config_rows["Target Topic Criteria Input"] == "Token optimization techniques for resilient cost control and ai deployment"
