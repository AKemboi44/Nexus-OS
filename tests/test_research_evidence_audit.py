from openpyxl import load_workbook

from app.research.providers.crossref_provider import CrossrefProvider
from app.research.research_pipeline import ResearchPipeline
from models.research_dossier import ResearchDossier
from models.research_insight import ResearchInsight


def _source(title, abstract, year=2024, doi="10.1000/example"):
    return {
        "uid": f"source-{title}",
        "title": title,
        "authors": ["A. Researcher"],
        "venue": "Evidence Journal",
        "year": year,
        "doi": doi,
        "url": f"https://doi.org/{doi}",
        "abstract": abstract,
        "citation_count": 5,
        "domain": "scholarly",
    }


def test_crossref_normalization_uses_real_metadata_and_cleans_jats_abstract():
    normalized = CrossrefProvider().normalize_schema({
        "DOI": "10.5555/Real.DOI",
        "title": ["A truthful Crossref record"],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "container-title": ["Journal of Evidence"],
        "published-online": {"date-parts": [[2019, 6, 1]]},
        "abstract": "<jats:title>Background</jats:title><jats:p>Useful &amp; specific evidence.</jats:p>",
        "is-referenced-by-count": 8,
        "type": "journal-article",
    })

    assert normalized["year"] == "2019"
    assert normalized["venue"] == "Journal of Evidence"
    assert normalized["url"] == "https://doi.org/10.5555/Real.DOI"
    assert normalized["doi"] == "10.5555/Real.DOI"
    assert normalized["abstract"] == "Background Useful & specific evidence."
    assert normalized["is_peer_reviewed"] is False


def test_pipeline_ranks_topic_matches_before_selection_and_audits_overflow(monkeypatch):
    pipeline = ResearchPipeline()
    matching = _source(
        "Token optimization for compilers",
        "An evaluation of token optimization techniques in compiler pipelines.",
        doi="10.1000/match",
    )
    weaker_match = _source(
        "Optimization methods",
        "A short note mentioning token optimization once.",
        year=2012,
        doi="10.1000/weaker",
    )
    unrelated = _source(
        "Crop rotation outcomes",
        "Field evidence about agricultural yield.",
        doi="10.1000/unrelated",
    )
    duplicate = _source(
        "Token optimization for compilers",
        "Duplicated provider metadata.",
        doi="10.1000/match",
    )

    monkeypatch.setattr(pipeline.openalex, "fetch_raw_sources", lambda *args: [unrelated, matching])
    monkeypatch.setattr(pipeline.semantic_scholar, "fetch_raw_sources", lambda *args: [weaker_match])
    monkeypatch.setattr(pipeline.crossref, "fetch_raw_sources", lambda *args: [duplicate])
    monkeypatch.setattr(pipeline.openalex, "normalize_schema", lambda source: source.copy())
    monkeypatch.setattr(pipeline.semantic_scholar, "normalize_schema", lambda source: source.copy())
    monkeypatch.setattr(pipeline.crossref, "normalize_schema", lambda source: source.copy())

    result = pipeline._discover_sources_real("Token optimization", max_sources=1)

    assert [source["title"] for source in result["included"]] == ["Token optimization for compilers"]
    reason = result["included"][0]["inclusion_reason"]
    assert all(label in reason for label in ("Relevant:", "Recency:", "Quality:", "Evidence:"))
    assert result["included"][0]["source_contribution"].startswith("An evaluation")
    exclusion_reasons = [source["exclusion_reason"] for source in result["excluded"]]
    assert any("No meaningful topical match" in reason for reason in exclusion_reasons)
    assert any("Duplicate record" in reason for reason in exclusion_reasons)
    overflow = next(reason for reason in exclusion_reasons if "Lower topical match" in reason)
    assert "quota" not in overflow.casefold()


def test_excel_audit_includes_contribution_and_honest_selection_scope(monkeypatch, tmp_path):
    pipeline = ResearchPipeline()
    included = _source(
        "Token optimization for compilers",
        "This abstract explains the selected source contribution.",
        doi="10.1000/included",
    )
    excluded = _source("Token optimization survey", "", doi="10.1000/excluded")
    excluded["exclusion_reason"] = "Lower topical match than selected evidence after deterministic ranking."
    excluded["source_contribution"] = "Metadata contribution: Token optimization survey; Evidence Journal; 2024."
    included["inclusion_reason"] = "Relevant: matched token. Recency: Published 2024. Quality: traceable metadata. Evidence: abstract available."
    included["source_contribution"] = included["abstract"]
    monkeypatch.setattr(pipeline, "_discover_sources_real", lambda *args: {
        "included": [included.copy()],
        "excluded": [excluded.copy()],
        "audit": {"candidates_retrieved": 7, "unique_candidates_reviewed": 6, "active_criteria": ["Topic relevance"]},
    })
    monkeypatch.setattr(
        pipeline.insight_engine, "generate_insight",
        lambda *args: ResearchInsight("Token optimization", "A concise synthesis.", []),
    )

    class Generator:
        def generate_comprehensive_dossier(self, **kwargs):
            dossier = ResearchDossier(kwargs["query"])
            dossier.included_sources = kwargs["included_sources"]
            dossier.themes = ["A theme"]
            return dossier

    monkeypatch.setattr("app.research.research_pipeline.DossierGenerator", Generator)
    result = pipeline.run_research("Token optimization", max_sources=1, output_directory=str(tmp_path))
    workbook = load_workbook(tmp_path / result.report_data["discovery_report_name"], read_only=True)

    assert "Source Contribution" in [cell.value for cell in workbook["Included Evidence"][1]]
    assert "Source Contribution" in [cell.value for cell in workbook["Excluded Candidates"][1]]
    summary = {
        str(metric).casefold(): value
        for metric, value in list(workbook["Executive Summary"].values)[1:]
    }
    assert summary["requested source cap"] == 1
    assert summary["provider candidates retrieved"] == 7
    assert "starting evidence sample" in summary["selection scope"].casefold()
    workbook.close()
