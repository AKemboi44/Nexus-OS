"""The AI summary must see the evidence, say honestly when it did not, and the scan must not invent quality scores."""

import pytest
from openpyxl import load_workbook

from app.research.research_pipeline import ResearchPipeline
from app.synthesis.insight_engine import InsightEngine
from app.synthesis.providers import SynthesisProviderError, SynthesisUnavailableError
from models.research_dossier import ResearchDossier

ABSTRACT = "Large language models were evaluated on reasoning benchmarks, showing uneven performance across tasks."


class FakeGenai:
    """Stands in for the provider registry and records every prompt."""

    def __init__(self, text="A grounded synthesis of the supplied abstracts.", error=None):
        self.prompts, self.text, self.error, self.kwargs = [], text, error, []

    def generate_with_failover(self, prompt, **kwargs):
        self.prompts.append(prompt)
        self.kwargs.append(kwargs)
        if self.error:
            raise SynthesisProviderError(str(self.error))
        return self.text, "fake"


class NoProviders:
    prompts = []

    def generate_with_failover(self, prompt, **kwargs):
        raise SynthesisUnavailableError("No synthesis provider configured or available")


def engine(client):
    return InsightEngine(registry=client if client is not None else NoProviders())


def pipeline_block(title="Evaluating reasoning in language models", abstract=ABSTRACT):
    """The exact shape research_pipeline hands to the summary step."""
    return {"id": "W1", "title": title, "abstract": abstract, "content": abstract}


# --- the summary prompt -------------------------------------------------------------------------------------------

def test_the_prompt_contains_the_real_title_and_abstract_of_every_source():
    client = FakeGenai()
    engine(client).generate_insight("Testing AI", [pipeline_block(), pipeline_block("Second study", "A second abstract.")])
    prompt = client.prompts[0]
    assert "Evaluating reasoning in language models" in prompt and ABSTRACT in prompt
    assert "Second study" in prompt and "A second abstract." in prompt
    assert "Unknown Title" not in prompt


def test_the_old_block_shape_without_a_title_still_reaches_the_model():
    client = FakeGenai()
    engine(client).generate_insight("Testing AI", [{"id": "W9", "content": ABSTRACT}])
    assert ABSTRACT in client.prompts[0] and "Unknown Title" not in client.prompts[0]


def test_a_successful_summary_is_marked_ai():
    result = engine(FakeGenai("Real synthesis.")).generate_insight("Testing AI", [pipeline_block()])
    assert result.insight == "Real synthesis." and result.status == "ai"


@pytest.mark.parametrize("blocks", [
    [], [{"id": "a", "title": "T", "abstract": "", "content": ""}], [pipeline_block(abstract="No description.")],
    [{"id": "a", "title": "Only a title"}], [pipeline_block(abstract="   ")],
])
def test_with_no_abstract_text_the_model_is_not_called_and_the_result_says_so(blocks):
    client = FakeGenai()
    result = engine(client).generate_insight("Testing AI", blocks)
    assert client.prompts == [] and result.status == "no_evidence"
    assert "Testing AI" in result.insight, "the text still names the topic"
    assert "evidence blocks" not in result.insight.lower() and "please provide" not in result.insight.lower()


def test_blocks_without_text_are_left_out_of_the_prompt_but_the_rest_are_used():
    client = FakeGenai()
    engine(client).generate_insight("Testing AI", [pipeline_block("Has text"), pipeline_block("Empty one", "")])
    assert "Has text" in client.prompts[0] and "Empty one" not in client.prompts[0]


def test_a_failing_model_gives_a_template_status_and_never_claims_findings():
    result = engine(FakeGenai(error=RuntimeError("503"))).generate_insight("Testing AI", [pipeline_block()])
    assert result.status == "template"
    for invented in ("critical performance trade-offs", "significant trend", "Analysis suggests"):
        assert invented not in result.insight


def test_no_client_gives_a_template_status_and_makes_no_call():
    result = engine(None).generate_insight("Testing AI", [pipeline_block()])
    assert result.status == "template" and "Testing AI" in result.insight and "Mock insight" not in result.insight


def test_an_empty_model_answer_is_treated_as_unavailable():
    assert engine(FakeGenai(text=None)).generate_insight("Testing AI", [pipeline_block()]).status == "template"
    assert engine(FakeGenai(text="   ")).generate_insight("Testing AI", [pipeline_block()]).status == "template"


def test_very_long_abstracts_are_capped_so_the_prompt_stays_bounded():
    client = FakeGenai()
    engine(client).generate_insight("T", [pipeline_block(abstract="word " * 5000)])
    assert len(client.prompts[0]) < 5000


# --- the pipeline and the workbook ----------------------------------------------------------------------------------

def source(title="Evaluating reasoning in language models", abstract=ABSTRACT):
    return {
        "uid": f"id-{title}", "title": title, "authors": ["A. Researcher"], "venue": "Evidence Journal", "year": 2025,
        "doi": "10.1000/x", "url": "https://doi.org/10.1000/x", "abstract": abstract, "citation_count": 5,
        "domain": "scholarly", "inclusion_reason": "Relevant: matched testing.", "source_contribution": abstract[:80],
    }


def run(monkeypatch, tmp_path, client, included, themes=None):
    pipeline = ResearchPipeline()
    pipeline.insight_engine.registry = client
    monkeypatch.setattr(pipeline, "_discover_sources_real", lambda *args: {
        "included": [dict(s) for s in included], "excluded": [],
        "audit": {"candidates_retrieved": len(included), "unique_candidates_reviewed": len(included),
                  "active_criteria": ["Topic relevance"]},
    })

    class Generator:
        def generate_comprehensive_dossier(self, **kwargs):
            dossier = ResearchDossier(kwargs["query"])
            dossier.included_sources = kwargs["included_sources"]
            dossier.themes = themes or []
            return dossier

    monkeypatch.setattr("app.research.research_pipeline.DossierGenerator", Generator)
    result = pipeline.run_research("Testing AI", max_sources=5, output_directory=str(tmp_path))
    workbook = load_workbook(tmp_path / result.report_data["discovery_report_name"], read_only=True)
    summary = {str(k): v for k, v in list(workbook["Executive Summary"].values)[1:]}
    themes_sheet = [row[0] for row in list(workbook["Core Themes"].values)[1:]]
    workbook.close()
    return result, summary, themes_sheet


def test_the_pipeline_gives_the_summary_the_abstracts_and_records_how_many(monkeypatch, tmp_path):
    client = FakeGenai("The studies agree performance is uneven.")
    result, summary, themes = run(monkeypatch, tmp_path, client, [source(), source("Second", "Another abstract text.")])

    assert ABSTRACT in client.prompts[0] and "Unknown Title" not in client.prompts[0]
    assert summary["Synthesis status"] == "AI-written from 2 sources"
    assert summary["Synthesis summary"] == "The studies agree performance is uneven."
    assert any("Cross-source synthesis" in str(theme) for theme in themes)
    assert result.report_data["synthesis"] == "The studies agree performance is uneven."
    assert result.report_data["synthesis_status"] == "ai"


def test_no_abstracts_means_no_model_call_and_an_honest_workbook(monkeypatch, tmp_path):
    client = FakeGenai()
    result, summary, themes = run(monkeypatch, tmp_path, client, [source(abstract="")])

    assert client.prompts == []
    assert summary["Synthesis status"] == "Not generated: none of the included sources had an abstract to summarize"
    assert summary["Synthesis summary"] == "Not generated"
    assert not any("Cross-source synthesis" in str(theme) for theme in themes)
    assert result.report_data["synthesis"] == "" and result.report_data["synthesis_status"] == "no_evidence"


def test_an_unavailable_ai_service_is_stated_and_no_filler_text_leaks_into_the_themes(monkeypatch, tmp_path):
    result, summary, themes = run(monkeypatch, tmp_path, FakeGenai(error=RuntimeError("down")), [source()])

    assert summary["Synthesis status"] == "Not generated: the AI service was unavailable"
    assert summary["Synthesis summary"] == "Not generated"
    joined = " ".join(str(theme) for theme in themes)
    assert "Cross-source synthesis" not in joined and "critical performance" not in joined
    assert result.report_data["synthesis_status"] == "template"


def test_a_scan_with_no_included_sources_says_so(monkeypatch, tmp_path):
    result, summary, _ = run(monkeypatch, tmp_path, FakeGenai(), [])
    assert summary["Synthesis status"] == "Not generated: no sources were included"
    assert result.report_data["synthesis_status"] == "no_sources"


# --- the fields nothing should be reading --------------------------------------------------------------------------------

def test_invented_quality_fields_and_placeholder_citations_are_gone(monkeypatch, tmp_path):
    result, _, _ = run(monkeypatch, tmp_path, FakeGenai(), [source()])
    for removed in ("grounding_fidelity_score", "topical_relevance_signal", "apa_format_citation",
                    "bluebook_format_citation", "pymupdf_fulltext_chunks_pushed"):
        assert removed not in result.report_data, removed
    assert "A. Kemboi" not in str(result.report_data)


def test_the_real_fields_the_clients_use_are_still_there(monkeypatch, tmp_path):
    result, _, _ = run(monkeypatch, tmp_path, FakeGenai(), [source()])
    for kept in ("status", "included", "excluded", "discovery_report_name", "inclusion_reasons", "quality_report", "domain_executed"):
        assert kept in result.report_data, kept
    assert result.report_data["included"][0]["abstract"] == ABSTRACT
