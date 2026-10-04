"""Event schema, correlation id, windowed event fetch and admin guard."""

import ast
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import cloud_app
from app.analytics import context, schema
from app.analytics.event_store import AnalyticsEventStore

ROOT = Path(__file__).resolve().parent.parent


# --- schema -----------------------------------------------------------------------------

def test_conforming_event_has_no_problems():
    assert schema.validate("scan_completed", {"run_id": "r1", "duration_ms": 1200, "variant": "variant_a"}) == []


def test_unknown_prop_wrong_type_and_missing_required_are_reported():
    assert "unknown_prop:message" in schema.validate("scan_completed", {"message": "boom"})
    assert "bad_type:duration_ms" in schema.validate("scan_completed", {"duration_ms": "fast"})
    assert "bad_type:cache_hit" in schema.validate("report_completed", {"cache_hit": 1})
    assert "missing_prop:error_code" in schema.validate("error_displayed", {"surface": "scan"}, schema.WEB)
    assert "bad_type:surface" in schema.validate(
        "error_displayed", {"surface": "nowhere", "error_code": "x"}, schema.WEB
    )


def test_bool_is_not_accepted_as_a_number():
    assert "bad_type:duration_ms" in schema.validate("scan_completed", {"duration_ms": True})


def test_unregistered_event_and_unexpected_source_are_reported():
    assert schema.validate("brand_new_event", {}) == ["unregistered_event"]
    assert "unexpected_source:web" in schema.validate("scan_completed", {}, schema.WEB)
    assert schema.validate("scan_completed", {}, schema.CLIENT) == []


def test_envelope_is_added_and_problems_are_tagged_not_rejected():
    token = context.set_request_id("req-12345678")
    try:
        conforming = schema.build_properties("scan_completed", {"run_id": "r1"}, schema.SERVER)
        tagged = schema.build_properties("scan_completed", {"bogus": 1}, schema.SERVER)
        unregistered = schema.build_properties("brand_new_event", {"a": 1}, schema.WEB)
    finally:
        context.reset_request_id(token)

    assert conforming["source"] == "server" and conforming["schema_v"] == schema.SCHEMA_VERSION
    assert conforming["request_id"] == "req-12345678"
    assert "_schema_problems" not in conforming and "_unregistered" not in conforming
    assert tagged["_schema_problems"] == ["unknown_prop:bogus"] and tagged["bogus"] == 1
    assert unregistered["_unregistered"] is True and unregistered["a"] == 1


def test_envelope_cannot_be_overridden_by_caller_properties():
    properties = schema.build_properties("scan_completed", {"source": "web", "schema_v": 99}, schema.SERVER)
    assert properties["source"] == "server" and properties["schema_v"] == schema.SCHEMA_VERSION


def test_legacy_rows_get_an_inferred_source():
    assert schema.event_source({}, "backend") == "server"
    assert schema.event_source({}, "abc123") == "client"
    assert schema.event_source({"source": "extension"}, "abc123") == "extension"


def test_experiment_snapshot_is_added_to_the_envelope():
    properties = schema.build_properties("paywall_shown", {}, schema.SERVER, experiments={"paywall_copy": "b"})
    assert properties["exp"] == {"paywall_copy": "b"}


def _server_event_emissions():
    """(event, literal property keys) for every record_backend_analytics call in cloud_app.py."""
    tree = ast.parse((ROOT / "cloud_app.py").read_text(encoding="utf-8"))
    emissions = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "record_backend_analytics"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant)):
            continue
        keys = emissions.setdefault(node.args[0].value, set())
        if len(node.args) > 2 and isinstance(node.args[2], ast.Dict):
            keys.update(key.value for key in node.args[2].keys if isinstance(key, ast.Constant))
    return emissions


def test_every_event_the_server_emits_is_registered_with_matching_props():
    problems = []
    for event, keys in _server_event_emissions().items():
        spec = schema.get(event)
        if spec is None:
            problems.append(f"{event}: not registered")
            continue
        unknown = keys - set(spec.props)
        if unknown:
            problems.append(f"{event}: props not in schema {sorted(unknown)}")
    assert not problems, problems


def test_registry_declares_no_free_text_props():
    forbidden = {"message", "prompt", "abstract", "content", "text", "detail", "title", "description"}
    for spec in schema.REGISTRY.values():
        assert not forbidden & set(spec.props), spec.name


# --- request id -------------------------------------------------------------------------

def test_request_id_accepts_well_formed_ids_and_replaces_bad_ones():
    assert context.accept_request_id("abc-12345678") == "abc-12345678"
    for bad in (None, "", "short", "has spaces in it!", "x" * 65, "bad\nid-12345678"):
        replaced = context.accept_request_id(bad)
        assert replaced != bad and re.fullmatch(r"[0-9a-f-]{36}", replaced)


def test_log_records_carry_the_request_id():
    cloud_app.configure_logging()
    factory = logging.getLogRecordFactory()
    token = context.set_request_id("req-abcdef12")
    try:
        record = factory("n", logging.INFO, "p", 1, "m", (), None)
    finally:
        context.reset_request_id(token)
    assert record.request_id == "req-abcdef12"
    assert factory("n", logging.INFO, "p", 1, "m", (), None).request_id == "-"


def _client():
    from fastapi.testclient import TestClient
    return TestClient(cloud_app.app)


def test_every_response_carries_a_request_id_header():
    response = _client().get("/v1/admin/analytics")
    assert response.status_code == 401
    assert re.fullmatch(r"[0-9a-f-]{36}", response.headers["x-request-id"])


def test_inbound_request_id_is_echoed_and_unsafe_ones_replaced():
    client = _client()
    assert client.get("/v1/admin/analytics", headers={"X-Request-ID": "trace-12345678"}).headers[
        "x-request-id"
    ] == "trace-12345678"
    assert client.get("/v1/admin/analytics", headers={"X-Request-ID": "bad id!"}).headers[
        "x-request-id"
    ] != "bad id!"


def test_backend_events_get_the_envelope_and_request_id(monkeypatch):
    captured = []
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: captured.append(event))
    token = context.set_request_id("req-98765432")
    try:
        cloud_app.record_backend_analytics("scan_completed", "user-1", {"run_id": "r1", "duration_ms": 5})
    finally:
        context.reset_request_id(token)

    properties = captured[0]["properties"]
    assert properties["source"] == "server" and properties["request_id"] == "req-98765432"
    assert properties["run_id"] == "r1" and "_schema_problems" not in properties
    assert captured[0]["session_id"] == "backend"


# --- client route -----------------------------------------------------------------------

def _post_client_event(monkeypatch, **fields):
    captured = []
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-1"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: captured.append(event))
    result = asyncio.run(cloud_app.log_telemetry_event(cloud_app.AnalyticsEvent(**fields), authorization="Bearer t"))
    return result, captured


def test_client_events_record_their_declared_source(monkeypatch):
    result, captured = _post_client_event(
        monkeypatch, event="error_displayed", source="extension",
        context={"surface": "scan", "error_code": "host_error"},
    )
    assert result == {"status": "logged"}
    assert captured[0]["properties"]["source"] == "extension"
    assert "_schema_problems" not in captured[0]["properties"]


def test_old_client_builds_without_source_are_recorded_as_client(monkeypatch):
    _, captured = _post_client_event(monkeypatch, event="workspace_opened")
    assert captured[0]["properties"]["source"] == "client"


def test_unknown_client_event_is_accepted_and_tagged(monkeypatch):
    result, captured = _post_client_event(monkeypatch, event="some_future_event", source="web")
    assert result == {"status": "logged"}
    assert captured[0]["properties"]["_unregistered"] is True


def test_client_free_text_is_still_rejected(monkeypatch):
    with pytest.raises(HTTPException) as error:
        _post_client_event(monkeypatch, event="error_displayed", source="web",
                           context={"surface": "scan", "error_code": "x", "message": "secret text"})
    assert error.value.status_code == 400


def test_extension_no_longer_sends_server_owned_or_rejected_events():
    js = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
    assert "source: 'extension'" in js
    for event in ("scan_started", "scan_completed", "report_started", "report_completed"):
        assert f"sendAnalytics('{event}'" not in js, f"{event} is emitted by the server"
    assert not re.search(r"sendAnalytics\([^;]*\bmessage\b[,:}]", js, re.DOTALL)
    assert "document_saved_at: data.document_saved_at" not in js


# --- fetch_events -----------------------------------------------------------------------

def _store(tmp_path):
    return AnalyticsEventStore(str(tmp_path / "events.sqlite3"))


def _record_at(store, name, days_ago, user="u1", props=None):
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    store.record(name, user, "backend", props or {}, occurred_at=when)


def test_fetch_events_honours_the_window_and_returns_oldest_first(tmp_path):
    store = _store(tmp_path)
    _record_at(store, "old_event", 40)
    _record_at(store, "scan_completed", 3)
    _record_at(store, "scan_started", 1)

    events = store.fetch_events(days=30)

    assert [event["event_name"] for event in events] == ["scan_completed", "scan_started"]


def test_fetch_events_filters_by_name_and_validates_names(tmp_path):
    store = _store(tmp_path)
    _record_at(store, "scan_completed", 1)
    _record_at(store, "scan_started", 1)

    assert [e["event_name"] for e in store.fetch_events(30, names=["scan_started"])] == ["scan_started"]
    with pytest.raises(ValueError):
        store.fetch_events(30, names=["x'; DROP TABLE analytics_events;--"])


def test_fetch_events_keeps_the_newest_when_over_the_cap(tmp_path):
    store = _store(tmp_path)
    for days_ago in (5, 4, 3, 2, 1):
        _record_at(store, f"e{days_ago}", days_ago)

    kept = [event["event_name"] for event in store.fetch_events(30, limit=2)]

    assert kept == ["e2", "e1"]


class FakeSupabase:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows or [], error, []

    def request(self, method, resource, params=None, **kwargs):
        self.calls.append(params)
        if self.error:
            raise self.error
        offset, limit = int(params["offset"]), int(params["limit"])
        return self.rows[offset:offset + limit]


def _supabase_store(monkeypatch, tmp_path, fake):
    monkeypatch.setattr("app.analytics.event_store.SupabaseRestClient.from_env", lambda: fake)
    return _store(tmp_path)


def _row(index):
    return {"event_name": "scan_completed", "user_id": f"u{index}", "session_id": "backend",
            "occurred_at": f"2026-10-02T10:00:{index:02d}+00:00", "properties": {"n": index}}


def test_supabase_fetch_sends_an_iso_cutoff_not_a_sql_expression(monkeypatch, tmp_path):
    fake = FakeSupabase([_row(1)])
    _supabase_store(monkeypatch, tmp_path, fake).fetch_events(7, names=["scan_completed", "scan_failed"])

    params = fake.calls[0]
    cutoff = datetime.fromisoformat(params["occurred_at"].removeprefix("gte."))
    assert abs((datetime.now(timezone.utc) - cutoff) - timedelta(days=7)) < timedelta(minutes=1)
    assert "make_interval" not in params["occurred_at"]
    assert params["event_name"] == "in.(scan_completed,scan_failed)"


def test_supabase_fetch_paginates(monkeypatch, tmp_path):
    monkeypatch.setattr("app.analytics.event_store.EVENT_PAGE_SIZE", 2)
    fake = FakeSupabase([_row(index) for index in range(5)])

    events = _supabase_store(monkeypatch, tmp_path, fake).fetch_events(30)

    assert len(events) == 5
    assert [call["offset"] for call in fake.calls] == ["0", "2", "4"]


def test_supabase_failure_is_not_swallowed_into_the_local_file(monkeypatch, tmp_path):
    store = _store(tmp_path)
    _record_at(store, "scan_completed", 1)  # would be silently served by the old fallback
    store.supabase = FakeSupabase(error=RuntimeError("Supabase database request failed."))

    with pytest.raises(RuntimeError):
        store.fetch_events(30)
    with pytest.raises(RuntimeError):
        store.ab_conversion_metrics(days=30)


# --- admin guard ------------------------------------------------------------------------

def test_ab_conversion_endpoint_requires_the_admin_token(monkeypatch):
    monkeypatch.setenv("NEXUS_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(cloud_app.analytics, "ab_conversion_metrics", lambda days: {"overall": {}})

    with pytest.raises(HTTPException) as denied:
        asyncio.run(cloud_app.get_ab_conversion_analytics(days=30, x_admin_token=None))
    assert denied.value.status_code == 401
    with pytest.raises(HTTPException):
        asyncio.run(cloud_app.get_ab_conversion_analytics(days=30, x_admin_token="wrong"))

    allowed = asyncio.run(cloud_app.get_ab_conversion_analytics(days=30, x_admin_token="admin-secret"))
    assert allowed == {"overall": {}}
