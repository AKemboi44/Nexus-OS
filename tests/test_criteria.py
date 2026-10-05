"""Evidence criteria: the rules, the plan limits, the defaults, and that the scan really applies them."""

import asyncio
from pathlib import Path

import pytest

import cloud_app
from app.research import criteria
from app.research.criteria import (
    DEFAULT_LABELS, FREE_LIMIT, LABEL_CITED, LABEL_HIGHLY, LABEL_OPEN, LABEL_PEER, LABEL_RECENT, LABEL_REVIEW,
    LABEL_UNIQUE, PAID_LIMIT, failures, resolve,
)
from app.research.providers.crossref_provider import CrossrefProvider
from app.research.providers.openalex_provider import OpenAlexProvider
from app.research.providers.semantic_scholar_provider import SemanticScholarProvider
from app.research.research_pipeline import ResearchPipeline
from tests.test_free_tier_exposure import World, sources

NOW = 2026


def src(**overrides):
    base = {
        "uid": "u1", "title": "A study of reasoning evaluation", "authors": ["A. Author"], "year": 2024,
        "venue": "Journal of Evaluation", "doi": "10.1/x", "url": "https://doi.org/10.1/x", "abstract": "Text.",
        "citation_count": 12, "is_peer_reviewed": True, "work_type": "journal-article", "is_open_access": True,
    }
    base.update(overrides)
    return base


def met(label, source, source_type=None):
    return failures(source, resolve([label], source_type, paid=True), now=NOW) == []


# --- each rule ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("label, passing, failing", [
    (LABEL_PEER, {"is_peer_reviewed": True}, {"is_peer_reviewed": False, "work_type": "preprint"}),
    (LABEL_PEER, {"is_peer_reviewed": False, "work_type": "journal-article"}, {"is_peer_reviewed": False, "work_type": None}),
    (LABEL_CITED, {"citation_count": 1}, {"citation_count": 0}),
    (LABEL_CITED, {}, {"authors": [], "citation_count": 5}),
    (LABEL_RECENT, {"year": 2021}, {"year": 2020}),
    (LABEL_RECENT, {"year": "2026"}, {"year": None}),
    (LABEL_OPEN, {"is_open_access": True}, {"is_open_access": False}),
    (LABEL_OPEN, {}, {"is_open_access": None}),
    (LABEL_HIGHLY, {"citation_count": 10}, {"citation_count": 9}),
    (LABEL_REVIEW, {"work_type": "review"}, {"work_type": "journal-article"}),
    (LABEL_REVIEW, {"title": "A systematic review of reasoning evaluation"}, {}),
    (LABEL_REVIEW, {"abstract": "We conduct a meta-analysis of benchmark results."}, {}),
    (LABEL_UNIQUE, {}, None),
])
def test_each_criterion_passes_and_fails_as_defined(label, passing, failing):
    assert met(label, src(**passing))
    if failing is not None:
        assert not met(label, src(**failing))


@pytest.mark.parametrize("source_type, work_type, expected", [
    ("journal", "journal-article", True), ("journal", "review", True), ("journal", "preprint", False),
    ("conference", "conference-paper", True), ("conference", "journal-article", False),
    ("preprint", "preprint", True), ("preprint", "journal-article", False),
    ("book", "book", True), ("book", "book-chapter", True), ("book", "dataset", False),
    ("journal", None, False),
])
def test_the_type_selector_filters_by_work_type(source_type, work_type, expected):
    assert failures(src(work_type=work_type), resolve([], source_type, paid=True), now=NOW) == [] if expected else \
        failures(src(work_type=work_type), resolve([], source_type, paid=True), now=NOW) != []


def test_every_failure_names_the_criterion_and_the_fact():
    missed = failures(src(citation_count=3, year=2015, is_open_access=False),
                      resolve([LABEL_OPEN, LABEL_HIGHLY, LABEL_RECENT], None, paid=True), now=NOW)
    assert missed == [
        f"{LABEL_RECENT} (published in 2015, before 2021)",
        f"{LABEL_OPEN} (not open access)",
        f"{LABEL_HIGHLY} (3 citations)",
    ]


def test_missing_metadata_counts_as_not_met_and_says_so():
    assert "not reported" in failures(src(is_open_access=None), resolve([LABEL_OPEN], None, True), now=NOW)[0]
    assert "not reported" in failures(src(year=None), resolve([LABEL_RECENT], None, True), now=NOW)[0]


# --- resolving what a client sent ----------------------------------------------------------------------------------------------

def test_nothing_selected_applies_the_defaults_cited_recent_unique():
    resolved = resolve([], None, paid=False)
    assert resolved.defaults_applied is True and resolved.limited is False
    assert set(resolved.labels) == set(DEFAULT_LABELS) == {LABEL_CITED, LABEL_RECENT, LABEL_UNIQUE}


def test_defaults_fit_inside_the_free_limit():
    assert len(DEFAULT_LABELS) <= FREE_LIMIT


def test_free_accounts_are_limited_to_three_in_a_fixed_order():
    everything = [c.label for c in criteria.REGISTRY]
    resolved = resolve(list(reversed(everything)), "journal", paid=False)
    assert len(resolved.applied) == FREE_LIMIT == 3 and resolved.limited is True and resolved.limit == 3
    assert resolved.labels == everything[:3], "canonical order, whatever order the client sent"


def test_paid_accounts_get_up_to_eight_including_the_type():
    everything = [c.label for c in criteria.REGISTRY]
    resolved = resolve(everything, "journal", paid=True)
    assert len(resolved.applied) == PAID_LIMIT == 8 and resolved.limited is False
    assert resolved.labels[-1] == "Publication type: Journal article"


def test_the_type_counts_toward_the_free_limit():
    resolved = resolve([LABEL_CITED, LABEL_RECENT, LABEL_OPEN], "journal", paid=False)
    assert resolved.limited is True and "Publication type: Journal article" not in resolved.labels


def test_unknown_labels_and_types_are_ignored_and_any_means_no_type():
    resolved = resolve(["Made up criterion", "  ", LABEL_OPEN], "spaceship", paid=True)
    assert resolved.labels == [LABEL_OPEN]
    assert resolve([LABEL_OPEN], "any", paid=True).labels == [LABEL_OPEN]
    assert resolve(["Made up criterion"], None, paid=True).defaults_applied is True


def test_the_summary_is_what_the_clients_receive():
    assert resolve([LABEL_OPEN], None, paid=False).summary() == {
        "applied": [LABEL_OPEN], "defaults_applied": False, "limited": False, "limit": 3, "strict": False}


# --- provider metadata -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw_type, source_type, expected", [
    ("article", "journal", "journal-article"), ("article", "repository", "other"), ("review", "journal", "review"),
    ("preprint", "repository", "preprint"), ("conference-paper", "book series", "conference-paper"),
    ("book-chapter", None, "book-chapter"), ("book", None, "book"), ("dataset", None, "dataset"), ("editorial", "journal", "other"),
])
def test_openalex_work_types_are_normalized(raw_type, source_type, expected):
    work = {"id": "W1", "title": "T", "type": raw_type, "open_access": {"is_oa": True}, "language": "en",
            "primary_location": {"source": {"type": source_type, "display_name": "V"}}}
    normalized = OpenAlexProvider().normalize_schema(work)
    assert (normalized["work_type"], normalized["is_open_access"], normalized["language"]) == (expected, True, "en")


def test_semantic_scholar_work_types_and_the_open_access_fix():
    base = {"paperId": "p1", "title": "T", "authors": [{"name": "A"}], "year": 2024, "isOpenAccess": True}
    journal = SemanticScholarProvider().normalize_schema({**base, "publicationTypes": ["JournalArticle"],
                                                          "publicationVenue": {"name": "J", "type": "journal"}})
    preprint = SemanticScholarProvider().normalize_schema({**base, "publicationTypes": ["JournalArticle"],
                                                           "publicationVenue": {"name": "arXiv", "type": "repository"}})
    review = SemanticScholarProvider().normalize_schema({**base, "publicationTypes": ["Review", "JournalArticle"]})
    assert journal["work_type"] == "journal-article" and journal["is_peer_reviewed"] is True
    assert preprint["work_type"] == "preprint" and preprint["is_peer_reviewed"] is False, "open access is not peer review"
    assert review["work_type"] == "review" and review["is_open_access"] is True


@pytest.mark.parametrize("raw_type, expected", [
    ("journal-article", "journal-article"), ("posted-content", "preprint"), ("proceedings-article", "conference-paper"),
    ("book-chapter", "book-chapter"), ("monograph", "book"), ("report", "other"),
])
def test_crossref_work_types_are_normalized_and_its_peer_review_flag_is_unchanged(raw_type, expected):
    normalized = CrossrefProvider().normalize_schema({
        "DOI": "10.1/x", "title": ["T"], "author": [{"given": "A", "family": "B"}], "type": raw_type,
        "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}], "language": "en"})
    assert (normalized["work_type"], normalized["is_open_access"], normalized["language"]) == (expected, True, "en")
    assert normalized["is_peer_reviewed"] is False


def test_crossref_open_access_is_unknown_without_a_declared_licence():
    assert CrossrefProvider().normalize_schema({"DOI": "10.1/x", "title": ["T"]})["is_open_access"] is None


# --- the scan applies them -------------------------------------------------------------------------------------------------------------

def candidates():
    return [
        src(uid="a", title="Reasoning evaluation in language models", doi="10.1/a", year=2024, citation_count=40),
        src(uid="b", title="Reasoning evaluation benchmarks", doi="10.1/b", year=2018, citation_count=300),
        src(uid="c", title="Reasoning evaluation brand new", doi="10.1/c", year=2026, citation_count=0),
        src(uid="d", title="Reasoning evaluation of closed models", doi="10.1/d", year=2023, citation_count=15, is_open_access=False),
    ]


def discover(monkeypatch, resolved, max_sources=10):
    pipeline = ResearchPipeline()
    for provider in (pipeline.openalex, pipeline.semantic_scholar, pipeline.crossref):
        monkeypatch.setattr(provider, "normalize_schema", lambda source: source.copy())
        monkeypatch.setattr(provider, "fetch_raw_sources", lambda *args: [])
    monkeypatch.setattr(pipeline.openalex, "fetch_raw_sources", lambda *args: candidates())
    return pipeline._discover_sources_real("Reasoning evaluation", max_sources, None, resolved)


def test_strict_defaults_exclude_old_and_uncited_papers_and_say_why(monkeypatch):
    result = discover(monkeypatch, resolve([], None, paid=True, strict=True))
    assert {s["uid"] for s in result["included"]} == {"a", "d"}
    reasons = {s["uid"]: s["exclusion_reason"] for s in result["excluded"]}
    assert "published in 2018" in reasons["b"] and "Recent publication" in reasons["b"]
    assert "no citations recorded" in reasons["c"] and "strict matching" in reasons["c"]
    assert result["audit"]["criteria"]["defaults_applied"] is True and result["audit"]["criteria"]["strict"] is True
    assert result["audit"]["candidates_meeting_criteria"] == 2


def test_a_strict_selection_returns_fewer_sources_with_reasons(monkeypatch):
    result = discover(monkeypatch, resolve([LABEL_OPEN, LABEL_HIGHLY, LABEL_RECENT], None, paid=True, strict=True))
    assert [s["uid"] for s in result["included"]] == ["a"]
    d_reason = next(s["exclusion_reason"] for s in result["excluded"] if s["uid"] == "d")
    assert "not open access" in d_reason and "strict matching" in d_reason
    assert result["audit"]["active_criteria"] == [LABEL_RECENT, LABEL_OPEN, LABEL_HIGHLY]


def test_uploaded_sources_are_never_filtered_by_criteria(monkeypatch, tmp_path):
    pipeline = ResearchPipeline()
    monkeypatch.setattr(pipeline, "_discover_sources_real", lambda *args: {
        "included": [], "excluded": [], "audit": {"active_criteria": ["x"], "candidates_meeting_criteria": 0}})
    upload = src(uid="mine", year=1999, citation_count=0, include=True)
    pipeline.insight_engine.registry = type("R", (), {"generate_with_failover": lambda *a, **k: ("Summary text.", "fake")})()
    result = pipeline.run_research("Reasoning evaluation", max_sources=3, additional_sources=[upload],
                                   output_directory=str(tmp_path), criteria=resolve([LABEL_RECENT], None, True))
    assert [s["uid"] for s in result.report_data["included"]] == ["mine"]


def test_the_result_carries_the_criteria_the_user_got(monkeypatch, tmp_path):
    pipeline = ResearchPipeline()
    pipeline.insight_engine.registry = type("R", (), {"generate_with_failover": lambda *a, **k: ("Summary.", "fake")})()
    for provider in (pipeline.openalex, pipeline.semantic_scholar, pipeline.crossref):
        monkeypatch.setattr(provider, "normalize_schema", lambda source: source.copy())
        monkeypatch.setattr(provider, "fetch_raw_sources", lambda *args: [])
    monkeypatch.setattr(pipeline.openalex, "fetch_raw_sources", lambda *args: candidates())
    result = pipeline.run_research("Reasoning evaluation", max_sources=5, output_directory=str(tmp_path),
                                   selected_inclusion_reasons=[LABEL_OPEN, LABEL_RECENT])
    data = result.report_data["criteria"]
    assert data["applied"] == [LABEL_RECENT, LABEL_OPEN] and data["defaults_applied"] is False
    assert data["candidates_meeting_all"] == 2 and data["candidates_checked"] == 4


# --- plan limits are enforced by the endpoint ----------------------------------------------------------------------------------------

@pytest.fixture
def world(monkeypatch, tmp_path, fake_provider, synthesized_draft_json):
    return World(monkeypatch, tmp_path, fake_provider, synthesized_draft_json)


class RecordingPipeline:
    def __init__(self):
        self.criteria = None

    def run_research(self, **kwargs):
        self.criteria = kwargs["criteria"]
        Path(kwargs["output_directory"], "research_audit_x_20261001_120000.xlsx").write_bytes(b"workbook")
        return {"status": "success", "included": sources(2), "excluded": [], "criteria": kwargs["criteria"].summary(),
                "discovery_report_name": "research_audit_x_20261001_120000.xlsx"}


def run_scan(world, monkeypatch, **request):
    pipeline = RecordingPipeline()
    monkeypatch.setattr(cloud_app, "pipeline", pipeline)
    everything = [c.label for c in criteria.REGISTRY]
    response = asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(topic="AI evidence", selected_inclusion_reasons=everything, **request), authorization="Bearer t"))
    return pipeline, response


def test_a_free_scan_is_limited_to_three_criteria_by_the_server(world, monkeypatch):
    pipeline, response = run_scan(world, monkeypatch, source_type="journal")
    assert len(pipeline.criteria.applied) == 3 and pipeline.criteria.limited is True
    assert response["criteria"]["limited"] is True and response["criteria"]["limit"] == 3, "free users can see their limit"


def test_a_paid_scan_gets_all_eight(world, monkeypatch):
    world.paid = True
    pipeline, response = run_scan(world, monkeypatch, source_type="journal")
    assert len(pipeline.criteria.applied) == 8 and pipeline.criteria.limited is False
    assert response["criteria"]["limit"] == 8


def test_a_scan_with_nothing_selected_uses_the_defaults(world, monkeypatch):
    pipeline = RecordingPipeline()
    monkeypatch.setattr(cloud_app, "pipeline", pipeline)
    asyncio.run(cloud_app.execute_cloud_scan(cloud_app.ScanRequest(topic="AI evidence"), authorization="Bearer t"))
    assert pipeline.criteria.defaults_applied is True and set(pipeline.criteria.labels) == set(DEFAULT_LABELS)


# --- the page and the extension agree with the server's registry ----------------------------------------------------------------------------

import re

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "website" / "styles.css").read_text(encoding="utf-8")
EXT_HTML = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")


def fieldset():
    block = HTML[HTML.index('<fieldset class="criteria-fieldset">'):]
    return block[:block.index("</fieldset>")]


def test_the_page_offers_exactly_the_criteria_the_server_knows_in_the_same_order():
    values = re.findall(r'<input type="checkbox" value="([^"]+)"', fieldset())
    assert values == [c.label for c in criteria.REGISTRY]
    assert len(values) == 7


def test_the_type_selector_offers_any_plus_the_servers_types():
    options = re.findall(r'<option value="([^"]+)"', fieldset())
    assert options == ["any", *criteria.SOURCE_TYPES.keys()]
    assert 'id="sourceType"' in fieldset()


def test_seven_checkboxes_and_the_selector_fill_a_two_column_grid():
    block = fieldset()
    assert block.count('class="check-label"') + block.count('class="check-type"') == 8
    assert '<div class="criteria-grid">' in block
    assert ".criteria-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr))" in CSS
    assert "@media (max-width: 520px) { .criteria-grid { grid-template-columns: minmax(0, 1fr); } }" in CSS


def test_the_page_uses_the_same_limits_as_the_server():
    assert f"FREE_MAX_CRITERIA = {criteria.FREE_LIMIT};" in JS and f"PAID_MAX_CRITERIA = {criteria.PAID_LIMIT};" in JS


def test_the_selector_counts_toward_the_limit_and_is_sent_with_the_scan():
    body = JS[JS.index("function criteriaCount()"):JS.index("function sendContactEmail") if "function sendContactEmail" in JS else None]
    assert "byId('sourceType').value !== 'any'" in body
    assert "event.target instanceof HTMLSelectElement) event.target.value = 'any'" in JS
    assert "source_type: byId('sourceType').value === 'any' ? null : byId('sourceType').value" in JS


def test_the_page_tells_users_what_applies_when_they_choose_nothing():
    assert "If you choose none, we apply: cited, recent, and unique and topic-relevant." in JS


def test_the_result_message_says_how_many_candidates_met_the_criteria():
    body = JS[JS.index("function criteriaNote(data)"):]
    body = body[:body.index("\n    }\n")]
    assert "candidates met" in body and "Try selecting fewer criteria" in body and "Your plan applies up to" in body
    assert "criteriaNote(data)" in JS[JS.index("async function runScan"):]


def test_the_extension_keeps_working_with_the_labels_it_sends():
    labels = re.findall(r'<input type="checkbox" value="([^"]+)"', EXT_HTML[EXT_HTML.index('id="inclusionReasons"'):][:1500])
    known = [label for label in labels if label in {c.label for c in criteria.REGISTRY}]
    assert len(known) == 4, "its four original labels are understood"
    unknown = set(labels) - set(known)
    assert unknown == {"Accessible abstract or full-text evidence"}
    assert resolve(labels, None, paid=True).labels == [c.label for c in criteria.REGISTRY if c.label in known], \
        "a label the server does not know is ignored, not an error"


def test_every_class_the_criteria_markup_uses_is_styled():
    for name in set(re.findall(r'class="([a-z-]+)"', fieldset())):
        assert f".{name}" in CSS, f"{name} has no CSS (the type selector once rendered unstyled because of a class-name mismatch)"
