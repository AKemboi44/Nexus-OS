"""Metric engine and V1 catalog, checked against hand-computed values."""

import json
from datetime import datetime, timedelta, timezone

import pytest

import cloud_app
from app.analytics import catalog, metrics_engine
from app.analytics.event_store import AnalyticsEventStore
from app.analytics.health import instrumentation_health
from app.analytics.metrics_engine import MetricSpec, Measurement, scorecard, status_for

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def row(name, user="u1", minutes_ago=0, source="server", **props):
    return {
        "event_name": name,
        "user_key": user,
        "session_id": "backend" if source == "server" else "client-session",
        "occurred_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "properties": {"source": source, **props},
    }


def measure(rows, metric_id, days=7):
    card = scorecard(rows, days, now=NOW, only=metric_id)
    return card["categories"][0]["metrics"][0]


# --- registry ---------------------------------------------------------------------------

def test_every_metric_is_well_formed_and_survives_empty_data():
    card = scorecard([], 30, now=NOW)
    metrics = [m for category in card["categories"] for m in category["metrics"]]
    assert len(metrics) == len(metrics_engine.REGISTRY) >= 30
    for item in metrics:
        spec = metrics_engine.REGISTRY[item["id"]]
        assert spec.description and spec.name
        assert item["value"] is None, f"{item['id']} must report no data, not a number, with no events"
        assert item["status"] == "no_data"
    assert {c["id"] for c in card["categories"]} == {c for c, _ in metrics_engine.CATEGORIES}


def test_a_failing_metric_does_not_break_the_scorecard(monkeypatch):
    def boom(ctx):
        raise RuntimeError("bad metric")

    monkeypatch.setitem(metrics_engine.REGISTRY, "boom",
                        MetricSpec("boom", "Boom", "quality", "count", None, None, "always fails", boom))
    card = scorecard([row("scan_started", run_id="r1")], 7, now=NOW)
    flat = {m["id"]: m for c in card["categories"] for m in c["metrics"]}
    assert flat["boom"]["value"] is None and flat["boom"]["breakdown"] == {"error": "metric failed to compute"}
    assert flat["scan_success_rate"]["value"] == 0.0


def test_status_thresholds():
    up = MetricSpec("u", "u", "quality", "rate", "up", 0.9, "d", lambda c: None)
    down = MetricSpec("d", "d", "quality", "ms", "down", 1000, "d", lambda c: None)
    info = MetricSpec("i", "i", "quality", "rate", None, None, "d", lambda c: None)
    assert status_for(up, None, 50) == "no_data"
    assert status_for(up, 0.95, 5) == "low_sample"
    assert [status_for(up, v, 50) for v in (0.95, 0.85, 0.5)] == ["good", "warn", "bad"]
    assert [status_for(down, v, 50) for v in (900, 1100, 5000)] == ["good", "warn", "bad"]
    assert status_for(info, 0.4, 50) == "info"


def test_window_previous_window_delta_and_sparkline():
    rows = [row("scan_started", run_id=f"n{i}", minutes_ago=60 * 24 * 2) for i in range(4)]
    rows += [row("scan_completed", run_id=f"n{i}", minutes_ago=60 * 24 * 2) for i in range(4)]
    rows += [row("scan_started", run_id=f"p{i}", minutes_ago=60 * 24 * 9) for i in range(4)]
    rows += [row("scan_completed", run_id=f"p{i}", minutes_ago=60 * 24 * 9) for i in range(2)]
    rows += [row("scan_started", run_id="old", minutes_ago=60 * 24 * 40)]

    result = measure(rows, "scan_success_rate", days=7)

    assert result["value"] == 1.0 and result["denominator"] == 4  # the 40-day-old event is outside both
    assert result["previous"] == 0.5 and result["delta"] == 0.5
    assert [point["value"] for point in result["series"]] == [1.0]


# --- customer experience ------------------------------------------------------------------

def test_scan_success_ignores_client_copies_of_server_events():
    rows = [row("scan_started", run_id=f"r{i}") for i in range(10)]
    rows += [row("scan_completed", run_id=f"r{i}") for i in range(9)]
    rows += [row("scan_completed", run_id=f"r{i}", source="extension") for i in range(10)]  # legacy duplicates
    result = measure(rows, "scan_success_rate")
    assert result["value"] == 0.9 and result["numerator"] == 9 and result["status"] == "warn"


def test_latency_percentiles_are_interpolated():
    rows = [row("scan_completed", run_id=f"r{i}", duration_ms=(i + 1) * 100) for i in range(10)]
    result = measure(rows, "scan_latency_p95")
    assert result["value"] == pytest.approx(955) and result["breakdown"]["p50"] == pytest.approx(550)


def test_report_delivered_rate_is_capped_and_split_by_type():
    rows = [row("report_started", report_type="proposal") for _ in range(2)]
    rows += [row("report_completed", report_type="proposal") for _ in range(3)]
    result = measure(rows, "report_delivered_rate")
    assert result["value"] == 1.0
    assert result["breakdown"]["proposal"] == {"requested": 2, "delivered": 3}


def test_report_latency_excludes_cache_hits():
    rows = [row("report_completed", duration_ms=1000, cache_hit=False),
            row("report_completed", duration_ms=50, cache_hit=True)]
    assert measure(rows, "report_latency_p95")["value"] == 1000


def test_time_to_first_deliverable_uses_the_first_deliverable_after_the_scan():
    rows = [
        row("excel_download_completed", user="a", minutes_ago=600),  # an earlier session, ignored
        row("scan_started", user="a", minutes_ago=100),
        row("excel_download_completed", user="a", minutes_ago=95),
        row("report_completed", user="a", minutes_ago=50),
        row("scan_started", user="b", minutes_ago=100),  # never got anything
    ]
    result = measure(rows, "time_to_first_deliverable")
    assert result["value"] == 300 and result["n"] == 1


def test_error_exposure_breaks_down_by_kind():
    rows = [row("scan_started", run_id="r1"), row("report_started"),
            row("report_failed", error_kind="proposal_generation_failed"),
            row("scan_failed", run_id="r1", error_category="internal_error")]
    result = measure(rows, "error_exposure_rate")
    assert result["value"] == 1.0 and result["denominator"] == 2
    assert result["breakdown"] == {"proposal_generation_failed": 1, "internal_error": 1}


def test_rating_counts_each_user_report_once_and_collects_reasons():
    rows = [
        row("feedback_submitted", user="a", reference_id="rep-00000001", rating="down", reasons="citations", minutes_ago=5),
        row("feedback_submitted", user="a", reference_id="rep-00000001", rating="up", minutes_ago=1),  # changed mind
        row("feedback_submitted", user="b", reference_id="rep-00000002", rating="down", reasons="citations,too_long"),
        row("feedback_submitted", user="c", reference_id="rep-00000003", rating="up"),
    ]
    result = measure(rows, "rating_positive_rate")
    assert result["numerator"] == 2 and result["denominator"] == 3
    assert result["breakdown"]["down_reasons"] == {"citations": 1, "too_long": 1}


def test_rating_response_rate_uses_fresh_reports_only():
    rows = [row("report_completed", cache_hit=False) for _ in range(4)]
    rows += [row("report_completed", cache_hit=True)]
    rows += [row("feedback_submitted", user="a", reference_id="rep-00000001", rating="up")]
    assert measure(rows, "rating_response_rate")["value"] == 0.25


# --- product effectiveness -------------------------------------------------------------------

def test_activation_counts_deliverables_within_24_hours():
    rows = [
        row("scan_completed", user="a", minutes_ago=300), row("excel_download_completed", user="a", minutes_ago=290),
        row("scan_completed", user="b", minutes_ago=60 * 40), row("report_completed", user="b", minutes_ago=60 * 5),
        row("scan_completed", user="c", minutes_ago=100),
    ]
    result = measure(rows, "activation_rate", days=7)
    assert result["numerator"] == 1 and result["denominator"] == 3


def test_funnel_steps_are_nested_and_never_exceed_the_previous_step():
    rows = []
    for user in ("a", "b", "c", "d"):
        rows += [row("scan_started", user=user), row("scan_completed", user=user)]
    rows += [row("report_started", user="a"), row("report_started", user="b"), row("report_completed", user="a")]
    rows += [row("report_started", user="stranger"), row("report_completed", user="stranger")]  # never scanned
    result = measure(rows, "funnel_scan_to_report")
    steps = {s["stage"]: s for s in result["breakdown"]}
    assert [steps[k]["users"] for k in ("scan_started", "scan_completed", "report_started", "report_completed")] == [4, 4, 2, 1]
    assert steps["report_started"]["step_rate"] == 0.5 and steps["report_completed"]["step_rate"] == 0.5
    assert all(s["step_rate"] is None or s["step_rate"] <= 1 for s in result["breakdown"])
    assert result["value"] == 0.25


def test_repeat_use_needs_two_different_days():
    rows = [row("scan_started", user="a", minutes_ago=0), row("scan_started", user="a", minutes_ago=60 * 24 * 30),
            row("scan_started", user="b", minutes_ago=0), row("scan_started", user="b", minutes_ago=10)]
    assert measure(rows, "repeat_use_rate", days=7)["value"] == 0.0
    assert measure(rows, "repeat_use_rate", days=60)["value"] == 0.5


def test_zero_results_and_metadata_completeness():
    rows = [row("scan_completed", run_id="a", included_count=0, excluded_count=10, reviewed_count=10, metadata_complete_count=4),
            row("scan_completed", run_id="b", included_count=6, excluded_count=4, reviewed_count=10, metadata_complete_count=8)]
    zero = measure(rows, "zero_result_rate")
    assert zero["value"] == 0.5 and zero["breakdown"]["inclusion_rate"] == pytest.approx(6 / 20)
    assert measure(rows, "metadata_completeness")["value"] == 0.6


# --- quality ----------------------------------------------------------------------------------

def proposal(mode="ai_synthesized", attempts=1, failure=None, request_id=None, **extra):
    return row("proposal_quality", generation_mode=mode, attempts=attempts, synthesis_failure=failure,
               source_count=4, cited_source_count=3, request_id=request_id, **extra)


def test_ai_rate_first_pass_and_repair_outcomes():
    rows = [proposal(), proposal(), proposal(attempts=2),
            proposal("template_fallback", 2, "quality_gate", gate_errors="verbatim_copy"),
            proposal("template_fallback", 0, "not_configured")]
    ai = measure(rows, "ai_synthesis_rate")
    assert ai["numerator"] == 3 and ai["denominator"] == 5
    assert ai["breakdown"]["fallback_reasons"] == {"quality_gate": 1, "not_configured": 1}
    first = measure(rows, "first_pass_gate_rate")  # attempts >= 1: four proposals, two accepted first time
    assert first["numerator"] == 2 and first["denominator"] == 4
    assert first["breakdown"] == {"repair_attempts": 2, "repair_successes": 1}


def test_citation_coverage_uses_ai_proposals_only():
    rows = [proposal(), proposal(), proposal("template_fallback", 0, "not_configured")]
    assert measure(rows, "citation_coverage")["value"] == 0.75


def test_gate_rejections_and_their_codes():
    rows = [row("llm_call", outcome="ok"), row("llm_call", outcome="quality_gate"),
            row("llm_call", outcome="provider_error"),
            proposal("template_fallback", 2, "quality_gate", gate_errors="verbatim_copy,too_long")]
    result = measure(rows, "gate_rejection_rate")
    assert result["value"] == 0.5 and result["denominator"] == 2  # provider errors never produced a draft
    assert result["breakdown"]["gate_error_codes"] == {"verbatim_copy": 1, "too_long": 1}


def test_rating_by_mode_joins_feedback_to_the_proposal():
    rows = [proposal(request_id="rep-aaaaaaaa"), proposal("template_fallback", 0, "not_configured", request_id="rep-bbbbbbbb"),
            row("feedback_submitted", user="a", reference_id="rep-aaaaaaaa", rating="up"),
            row("feedback_submitted", user="b", reference_id="rep-bbbbbbbb", rating="down"),
            row("feedback_submitted", user="c", reference_id="rep-unknown1", rating="up")]
    result = measure(rows, "rating_by_mode")
    assert result["value"] == 1.0
    assert result["breakdown"]["template_fallback"] == {"helpful": 0, "rated": 1, "rate": 0.0}


def test_topic_correction_rate_ignores_scans_without_the_flag():
    rows = [row("scan_started", run_id="a", topic_corrected=True), row("scan_started", run_id="b", topic_corrected=False),
            row("scan_started", run_id="c")]
    assert measure(rows, "topic_correction_rate")["value"] == 0.5


def test_regenerate_rate_matches_same_topic_within_an_hour():
    rows = [row("report_started", user="a", topic_hash="t1", report_type="proposal", minutes_ago=30),
            row("report_started", user="a", topic_hash="t1", report_type="proposal", minutes_ago=10),
            row("report_started", user="b", topic_hash="t2", report_type="proposal", minutes_ago=300),
            row("report_started", user="b", topic_hash="t2", report_type="proposal", minutes_ago=10)]
    assert measure(rows, "regenerate_rate")["value"] == 0.5


# --- reliability and cost -----------------------------------------------------------------------

def test_llm_latency_per_model_and_error_rate():
    rows = [row("llm_call", provider="anthropic", model="m1", latency_ms=1000, outcome="ok"),
            row("llm_call", provider="anthropic", model="m1", latency_ms=3000, outcome="ok"),
            row("llm_call", provider="gemini", model="m2", latency_ms=500, outcome="provider_error", error_kind="unavailable")]
    latency = measure(rows, "llm_latency_p95")
    assert latency["breakdown"]["anthropic/m1"]["p50"] == 2000 and latency["breakdown"]["gemini/m2"]["n"] == 1
    errors = measure(rows, "llm_error_rate")
    assert errors["numerator"] == 1 and errors["breakdown"] == {"unavailable": 1}


def test_tokens_and_cost_per_proposal(monkeypatch):
    monkeypatch.setenv("LLM_PRICES_JSON", json.dumps({"priced": {"input": 1.0, "output": 5.0}}))
    rows = [
        row("llm_call", model="priced", input_tokens=1_000_000, output_tokens=1_000_000, request_id="rep-00000001"),
        row("llm_call", model="priced", input_tokens=0, output_tokens=200_000, request_id="rep-00000001"),
        row("llm_call", model="mystery", input_tokens=10, output_tokens=10, request_id="rep-00000002"),
    ]
    tokens = measure(rows, "tokens_per_proposal")
    assert tokens["n"] == 2 and tokens["value"] == pytest.approx((2_200_000 + 20) / 2)
    cost = measure(rows, "cost_per_proposal")
    assert cost["value"] == pytest.approx(7.0) and cost["n"] == 1
    assert cost["breakdown"]["requests_unpriced"] == 1


def test_bad_price_table_falls_back_to_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PRICES_JSON", "{not json")
    assert catalog.price_table() == catalog.DEFAULT_PRICES


def test_cache_hit_rate():
    rows = [row("report_completed", cache_hit=True), row("report_completed", cache_hit=False)]
    assert measure(rows, "cache_hit_rate")["value"] == 0.5


# --- monetization ---------------------------------------------------------------------------------

def test_paywall_funnel_and_revenue():
    rows = [row("second_query_attempted", user="a"), row("paywall_shown", user="a"),
            row("second_query_attempted", user="b"), row("paywall_shown", user="b"),
            row("query_submitted", user="c"),
            row("checkout_started", user="a"), row("bundle_purchased", user="a", price=29.0)]
    assert measure(rows, "paywall_exposure_rate")["value"] == pytest.approx(2 / 3)
    assert measure(rows, "paywall_to_checkout")["value"] == 0.5
    assert measure(rows, "checkout_to_purchase")["value"] == 1.0
    assert measure(rows, "revenue_total")["value"] == 29.0


# --- data quality ------------------------------------------------------------------------------------

def test_orphan_reports_ignore_recent_and_resolved_requests():
    rows = [
        row("report_started", request_id="rep-resolved", minutes_ago=30), row("report_completed", request_id="rep-resolved"),
        row("report_started", request_id="rep-orphan01", minutes_ago=30),
        row("report_started", request_id="rep-recent01", minutes_ago=2),
        row("report_started", minutes_ago=30),  # no request id: cannot be judged
    ]
    result = measure(rows, "orphan_report_rate")
    assert result["numerator"] == 1 and result["denominator"] == 2


def test_schema_conformance_counts_tagged_events():
    rows = [row("scan_started"), row("scan_started"), row("scan_started", _schema_problems=["unknown_prop:x"]),
            row("mystery", _unregistered=True)]
    result = measure(rows, "schema_conformance")
    assert result["value"] == 0.5 and "unknown_prop:x" in result["breakdown"]["top_problems"]


def test_client_coverage_by_source():
    rows = [row("scan_completed", run_id="a"), row("scan_completed", run_id="b"), row("scan_completed", run_id="c"),
            row("results_viewed", run_id="a", source="web"), row("results_viewed", run_id="b", source="extension")]
    result = measure(rows, "client_coverage")
    assert result["value"] == pytest.approx(2 / 3) and result["breakdown"] == {"web": 1, "extension": 1}


# --- admin API -----------------------------------------------------------------------------------

def _client(monkeypatch, rows=None, store=None):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("NEXUS_ADMIN_TOKEN", "admin-secret")
    if store is not None:
        monkeypatch.setattr(cloud_app, "analytics", store)
    elif rows is not None:
        monkeypatch.setattr(cloud_app.analytics, "fetch_events", lambda *a, **k: rows)
    return TestClient(cloud_app.app)


ADMIN = {"X-Admin-Token": "admin-secret"}


@pytest.mark.parametrize("path", ["/v1/admin/metrics", "/v1/admin/metrics/scan_success_rate",
                                  "/v1/admin/health", "/v1/admin/trace/abcdefgh1234"])
def test_admin_endpoints_require_the_token(monkeypatch, path):
    client = _client(monkeypatch, rows=[])
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_scorecard_endpoint_returns_categories(monkeypatch):
    rows = [row("scan_started", run_id="r1", minutes_ago=5), row("scan_completed", run_id="r1", minutes_ago=4)]
    body = _client(monkeypatch, rows=rows).get("/v1/admin/metrics?days=7", headers=ADMIN).json()

    assert body["window_days"] == 7 and body["data_truncated"] is False
    by_id = {m["id"]: m for c in body["categories"] for m in c["metrics"]}
    assert by_id["scan_success_rate"]["value"] == 1.0 and "series" in by_id["scan_success_rate"]


def test_metric_detail_endpoint_and_unknown_metric(monkeypatch):
    client = _client(monkeypatch, rows=[row("scan_started", run_id="r1", minutes_ago=5)])
    detail = client.get("/v1/admin/metrics/scan_success_rate", headers=ADMIN).json()
    assert detail["id"] == "scan_success_rate" and detail["window_days"] == 30 and detail["description"]
    assert client.get("/v1/admin/metrics/nope", headers=ADMIN).status_code == 404


def test_trace_endpoint_returns_one_requests_events(monkeypatch, tmp_path):
    store = AnalyticsEventStore(str(tmp_path / "trace.sqlite3"))
    for name, extra in (("report_started", {}), ("llm_call", {"input_tokens": 900, "output_tokens": 2500}),
                        ("span", {"name": "report.render", "duration_ms": 120}),
                        ("report_completed", {"duration_ms": 9000})):
        store.record(name, "user-1", "backend", {"request_id": "rep-trace0001", "source": "server", **extra})
    store.record("report_started", "user-2", "backend", {"request_id": "rep-other0002", "source": "server"})
    client = _client(monkeypatch, store=store)

    body = client.get("/v1/admin/trace/rep-trace0001", headers=ADMIN).json()

    assert [item["event"] for item in body["timeline"]] == ["report_started", "llm_call", "span", "report_completed"]
    assert body["summary"] == {"events": 4, "llm_calls": 1, "input_tokens": 900, "output_tokens": 2500,
                               "spans": {"report.render": 120}}
    assert client.get("/v1/admin/trace/rep-missing01", headers=ADMIN).status_code == 404
    assert client.get("/v1/admin/trace/bad id!", headers=ADMIN).status_code == 400


def test_health_lists_unseen_and_unregistered_events(monkeypatch):
    rows = [row("scan_started", run_id="r1"), row("mystery_event", _unregistered=True)]
    body = _client(monkeypatch, rows=rows).get("/v1/admin/health", headers=ADMIN).json()
    assert body["unregistered"] == ["mystery_event"]
    seen = {e["event"]: e for e in body["events"]}
    assert seen["mystery_event"]["schema_problems"] == 1 and seen["scan_started"]["sources"] == {"server": 1}
    assert any(item["event"] == "llm_call" for item in body["never_seen"])
    assert all(item["event"] != "scan_started" for item in body["never_seen"])


def test_fetch_events_can_filter_by_request_id(tmp_path):
    store = AnalyticsEventStore(str(tmp_path / "f.sqlite3"))
    store.record("a", "u", "backend", {"request_id": "rep-wanted001"})
    store.record("b", "u", "backend", {"request_id": "rep-another01"})
    assert [e["event_name"] for e in store.fetch_events(30, request_id="rep-wanted001")] == ["a"]
    with pytest.raises(ValueError):
        store.fetch_events(30, request_id="x'; --")


def test_health_function_handles_no_events():
    body = instrumentation_health([], 7, now=NOW)
    assert body["events"] == [] and len(body["never_seen"]) >= 25
