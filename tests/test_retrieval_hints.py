"""Selected criteria shape the search itself: providers are asked for recent, open-access, cited or review papers,
and the thresholds for closest matches and relevance come from environment variables."""

import pytest

from app.research import criteria, relevance
from app.research.criteria import (
    LABEL_HIGHLY, LABEL_OPEN, LABEL_RECENT, LABEL_REVIEW, describe_hints, hint_variants, resolve, retrieval_hints,
)
from app.research.providers.crossref_provider import CrossrefProvider
from app.research.providers.openalex_provider import OpenAlexProvider, build_filter
from app.research.providers.semantic_scholar_provider import SemanticScholarProvider
from app.research.research_pipeline import ResearchPipeline

NOW = 2026


def test_hints_follow_the_selected_criteria():
    hints = retrieval_hints(resolve([LABEL_RECENT, LABEL_OPEN, LABEL_HIGHLY], None, True), NOW)
    assert hints == {"year_from": NOW - 5, "open_access": True, "min_citations": 10}
    assert retrieval_hints(resolve([], "journal", True), NOW)["work_types"] == ["journal-article", "review"]


def test_the_rarest_ask_is_also_searched_on_its_own():
    hints = retrieval_hints(resolve([LABEL_RECENT, LABEL_REVIEW], None, True), NOW)
    assert hint_variants(hints) == [hints, {"review": True}]
    assert hint_variants({}) == []
    assert "reviews" in describe_hints(hints)


def test_openalex_filter():
    assert build_filter({"year_from": 2021, "open_access": True, "min_citations": 10}) == (
        "from_publication_date:2021-01-01,is_oa:true,cited_by_count:>9")
    assert build_filter({"review": True}) == "type:review"
    assert build_filter(None) == ""


def test_crossref_filters_only_what_it_can():
    assert CrossrefProvider.build_filter({"year_from": 2021, "open_access": True}) == "from-pub-date:2021-01-01"
    assert CrossrefProvider.build_filter({"review": True}) == ""
    assert not CrossrefProvider().supports_hints({"open_access": True})


def test_semantic_scholar_sends_no_filters_without_an_api_key(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    hints = {"year_from": 2021, "min_citations": 10}
    assert SemanticScholarProvider(api_key=None)._filter_params(hints) == {}
    keyed = SemanticScholarProvider(api_key="k")
    assert keyed._filter_params(hints) == {"year": "2021-", "minCitationCount": "10"}


@pytest.mark.parametrize("raw, expected", [(None, 0.2), ("", 0.2), ("50", 0.5), ("abc", 0.2), ("250", 1.0), ("-5", 0.0), ("nan", 0.2)])
def test_closest_match_share_comes_from_the_environment(monkeypatch, raw, expected):
    monkeypatch.delenv(criteria.MIN_MATCH_ENV, raising=False)
    if raw is not None:
        monkeypatch.setenv(criteria.MIN_MATCH_ENV, raw)
    assert criteria.min_match_share() == expected


@pytest.mark.parametrize("raw, expected", [(None, 2), ("3", 3), ("9", 3), ("-1", 0), ("x", 2)])
def test_relevance_floor_comes_from_the_environment(monkeypatch, raw, expected):
    monkeypatch.delenv(relevance.MIN_SCORE_ENV, raising=False)
    if raw is not None:
        monkeypatch.setenv(relevance.MIN_SCORE_ENV, raw)
    assert relevance.min_score() == expected


def test_the_pipeline_runs_a_targeted_search_and_drops_repeats(monkeypatch):
    pipeline = ResearchPipeline()
    calls = []
    paper = {"id": "w1", "title": "Reasoning evaluation", "doi": "10.1/x"}

    def openalex(query, limit, hints=None):
        calls.append(hints)
        return [dict(paper)]

    monkeypatch.setattr(pipeline.openalex, "fetch_raw_sources", openalex)
    monkeypatch.setattr(pipeline.semantic_scholar, "fetch_raw_sources", lambda *a: [])
    monkeypatch.setattr(pipeline.crossref, "fetch_raw_sources", lambda *a: [])
    monkeypatch.setattr(pipeline.openalex, "normalize_schema", lambda raw: {"title": raw["title"], "doi": raw["doi"]})
    result = pipeline._discover_sources_real("reasoning evaluation", 3, criteria=resolve([LABEL_RECENT], None, True))
    assert calls[0] is None and calls[1]["year_from"] == criteria.current_year() - 5
    assert result["audit"]["candidates_retrieved"] == 1
    assert not any("Duplicate" in str(s.get("exclusion_reason")) for s in result["excluded"])
