"""Inference tracing, proposal quality events, feedback and scan telemetry."""

import asyncio
import base64
import json
from pathlib import Path

import pytest

import cloud_app
from app.analytics import context
from app.reports import proposal_validation
from app.reports.proposal_service import AI_SYNTHESIZED, TEMPLATE_FALLBACK, generate_proposal_docx
from app.synthesis.call_ledger import RequestLedger
from tests.test_proposal_apa_rendering import SOURCES


@pytest.fixture(autouse=True)
def isolated_entitlements(tmp_path, monkeypatch):
    import app.payments.entitlements
    store = app.payments.entitlements.EntitlementStore(database_path=str(tmp_path / "entitlements.sqlite3"))
    monkeypatch.setattr(cloud_app, "entitlements", store)


# --- ledger accuracy ---------------------------------------------------------------------

def _generate(provider, ledger=None, sources=SOURCES):
    return generate_proposal_docx("Ethical AI Evaluation Frameworks", "scholarly", sources, provider, ledger)


def test_successful_call_records_tokens_latency_and_model(fake_provider, synthesized_draft_json):
    document = _generate(fake_provider(content=synthesized_draft_json()))

    (call,) = document.ledger.calls
    assert (call.outcome, call.attempt, call.purpose) == ("ok", 1, "proposal_synthesis")
    assert call.input_tokens == 1 and call.output_tokens == 1
    assert call.model == "fake-model" and call.provider == "fake"
    assert isinstance(call.latency_ms, int) and call.latency_ms >= 0


def test_provider_error_is_classified_and_timed(fake_provider):
    ledger = RequestLedger()
    document = _generate(fake_provider(error=RuntimeError("401 invalid x-api-key")), ledger)

    (call,) = ledger.calls
    assert call.outcome == "provider_error" and call.error_kind and call.latency_ms is not None
    assert document.synthesis_failure == "provider_error"


def test_unparsable_output_still_records_the_billed_tokens(fake_provider):
    ledger = RequestLedger()
    _generate(fake_provider(content="Sorry, I cannot do that."), ledger)

    (call,) = ledger.calls
    assert call.outcome == "invalid_output"
    assert call.input_tokens == 1 and call.output_tokens == 1


def test_not_configured_makes_no_call_and_records_none():
    class Unconfigured:
        name = "unconfigured"

        def is_configured(self):
            return False

    document = _generate(Unconfigured())
    assert document.ledger.calls == []
    assert document.quality["attempts"] == 0 and document.quality["synthesis_failure"] == "not_configured"


def _copied(draft_json):
    draft = json.loads(draft_json)
    draft["overview"][0]["text"] += " " + SOURCES[0]["abstract"]
    return json.dumps(draft)


def test_repair_attempt_marks_the_rejected_call_and_counts_two(fake_provider, synthesized_draft_json):
    clean = synthesized_draft_json()
    document = _generate(fake_provider(content=[_copied(clean), clean]))

    assert [call.outcome for call in document.ledger.calls] == ["quality_gate", "ok"]
    assert [call.attempt for call in document.ledger.calls] == [1, 2]
    assert document.quality["attempts"] == 2 and document.quality["repair_used"] is True
    assert document.generation_mode == AI_SYNTHESIZED


def test_quality_block_describes_an_ai_draft(fake_provider, synthesized_draft_json):
    quality = _generate(fake_provider(content=synthesized_draft_json())).quality

    assert quality["generation_mode"] == AI_SYNTHESIZED and quality["synthesis_failure"] is None
    assert quality["attempts"] == 1 and quality["repair_used"] is False
    assert quality["word_count"] >= 1000 and quality["source_count"] == 3
    assert quality["cited_source_count"] == 3 and quality["integrative_paragraphs"] >= 2
    assert quality["gate_errors"] == ""


def test_quality_block_records_gate_codes_for_a_persistent_failure(fake_provider, synthesized_draft_json):
    document = _generate(fake_provider(content=_copied(synthesized_draft_json())))

    assert document.generation_mode == TEMPLATE_FALLBACK
    assert document.quality["synthesis_failure"] == "quality_gate"
    assert "verbatim_copy" in document.quality["gate_errors"].split(",")
    assert document.quality["attempts"] == 2


def test_stage_timings_are_reported(fake_provider, synthesized_draft_json):
    timings = _generate(fake_provider(content=synthesized_draft_json())).timings_ms
    assert set(timings) == {"synthesis_ms", "render_ms"} and all(v >= 0 for v in timings.values())


def test_gate_errors_map_to_stable_codes_without_text():
    codes = proposal_validation.gate_error_codes([
        "Content too brief: 700 words (minimum 1000)",
        "Content too long: 4000 words (maximum 3500)",
        "Unknown source citations: ['S9']",
        "3 evidence paragraph(s) have no source citation",
        "Fewer than 2 paragraphs integrate multiple sources",
        "Text reproduces 8+ consecutive words from a source: 'Agentic artificial'",
        "Square brackets found in synthesized text",
        "something unexpected",
    ])
    assert codes == ["too_brief", "too_long", "unknown_citation", "uncited_evidence",
                     "no_integration", "verbatim_copy", "brackets", "other"]


# --- endpoint telemetry ------------------------------------------------------------------

class Database:
    def __init__(self):
        self.objects = {}

    def download_storage_object(self, bucket, path):
        if path not in self.objects:
            raise cloud_app.SupabaseRequestError(404, "not found")
        return self.objects[path]

    def upload_storage_object(self, bucket, path, content, content_type):
        self.objects[path] = content


def _wire(monkeypatch, provider):
    events = []
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-1"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: Database())
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: events.append(event))
    # These tests trace the paid delivery path.
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id, user_email=None: True)
    monkeypatch.setattr("app.reports.proposal_service._default_provider", lambda: provider)
    return events


def _report_body():
    return {"topic": "Ethical AI: Evaluation Frameworks", "included_sources": [dict(s) for s in SOURCES]}


def _named(events, name):
    return [event for event in events if event["event_name"] == name]


def _client():
    from fastapi.testclient import TestClient
    return TestClient(cloud_app.app)


def test_proposal_request_emits_llm_call_quality_and_span_events(monkeypatch, fake_provider, synthesized_draft_json):
    provider = fake_provider(content=synthesized_draft_json())
    events = _wire(monkeypatch, provider)

    response = _client().post("/v1/reports", json=_report_body(), headers={"Authorization": "Bearer t"})

    assert response.status_code == 200
    body = response.json()
    request_id = response.headers["x-request-id"]
    assert body["reference"] == request_id, "the user's Reference ID is the request id"

    (llm_call,) = _named(events, "llm_call")
    assert llm_call["properties"]["input_tokens"] == 1 and llm_call["properties"]["outcome"] == "ok"
    (quality,) = _named(events, "proposal_quality")
    assert quality["properties"]["generation_mode"] == "ai_synthesized"
    span_names = {event["properties"]["name"] for event in _named(events, "span")}
    assert {"report.synthesis", "report.render", "report.storage_upload"} <= span_names
    assert {event["properties"]["request_id"] for event in events} == {request_id}
    assert all("_schema_problems" not in e["properties"] and "_unregistered" not in e["properties"] for e in events)


def test_no_source_or_draft_text_reaches_any_event(monkeypatch, fake_provider, synthesized_draft_json):
    events = _wire(monkeypatch, fake_provider(content=synthesized_draft_json()))
    _client().post("/v1/reports", json=_report_body(), headers={"Authorization": "Bearer t"})

    stored = json.dumps(events)
    for source in SOURCES:
        assert source["title"] not in stored and source["abstract"] not in stored
    assert "Ethical AI: Evaluation Frameworks" not in stored, "the topic text must not be stored either"


def test_billed_calls_are_recorded_even_when_generation_fails(monkeypatch):
    events = _wire(monkeypatch, None)

    def fail_after_a_billed_call(topic, domain, sources, provider=None, ledger=None):
        call = ledger.add_call("proposal_synthesis", "anthropic", "claude-test", 1)
        ledger.complete_call(call, "ok", input_tokens=900, output_tokens=2500, latency_ms=4100)
        raise RuntimeError("render exploded")

    monkeypatch.setattr(cloud_app, "generate_proposal_docx", fail_after_a_billed_call)
    response = _client().post("/v1/reports", json=_report_body(), headers={"Authorization": "Bearer t"})

    assert response.status_code == 500
    (llm_call,) = _named(events, "llm_call")
    assert llm_call["properties"]["output_tokens"] == 2500
    (failed,) = _named(events, "report_failed")  # exactly one: no double counting
    assert failed["properties"]["error_kind"] == "proposal_generation_failed"
    assert failed["properties"]["error_category"] == "service_unavailable"
    assert failed["properties"]["report_type"] == "proposal"
    assert _named(events, "proposal_quality") == []


# --- feedback ----------------------------------------------------------------------------

def test_feedback_is_recorded_with_the_report_reference(monkeypatch):
    events = _wire(monkeypatch, None)
    response = _client().post(
        "/v1/feedback",
        json={"reference": "a1b2c3d4-e5f6-4711-8899-aabbccddeeff", "rating": "down",
              "reasons": ["citations", "too_long", "citations"]},
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 200
    (event,) = _named(events, "feedback_submitted")
    assert event["properties"]["reference_id"] == "a1b2c3d4-e5f6-4711-8899-aabbccddeeff"
    assert event["properties"]["rating"] == "down"
    assert event["properties"]["reasons"] == "citations,too_long"
    assert "_schema_problems" not in event["properties"]


@pytest.mark.parametrize("body", [
    {"reference": "short", "rating": "up"},
    {"reference": "a1b2c3d4-e5f6-4711-8899-aabbccddeeff", "rating": "meh"},
    {"reference": "a1b2c3d4-e5f6-4711-8899-aabbccddeeff", "rating": "down", "reasons": ["free text here"]},
    {"reference": "a1b2c3d4-e5f6-4711-8899-aabbccddeeff", "rating": "down", "comment": "x", "reasons": ["nope"]},
])
def test_feedback_rejects_bad_references_ratings_and_free_text(monkeypatch, body):
    events = _wire(monkeypatch, None)
    response = _client().post("/v1/feedback", json=body, headers={"Authorization": "Bearer t"})
    assert response.status_code == 422
    assert _named(events, "feedback_submitted") == []


# --- scan telemetry ----------------------------------------------------------------------

def _run_scan(monkeypatch, topic):
    events = []

    class Pipeline:
        def run_research(self, **kwargs):
            Path(kwargs["output_directory"], "research_audit_x_20261001_120000.xlsx").write_bytes(b"wb")
            return {"status": "success", "included": [{"title": "Evidence"}], "excluded": [],
                    "discovery_report_name": "research_audit_x_20261001_120000.xlsx"}

    class ScanDatabase:
        def request(self, method, resource, **kwargs):
            return []

        def upload_storage_object(self, *args):
            pass

        def insert(self, table, values):
            return {"id": values.get("id", "saved-id")}

    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: ScanDatabase())
    monkeypatch.setattr(cloud_app, "pipeline", Pipeline())
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: events.append(event))
    asyncio.run(cloud_app.execute_cloud_scan(cloud_app.ScanRequest(topic=topic, max_sources=5), authorization="Bearer t"))
    return events


def test_scan_flags_a_corrected_topic_and_emits_stage_spans(monkeypatch):
    events = _run_scan(monkeypatch, "Ethical evalution frameworks for resume screning")

    (started,) = _named(events, "scan_started")
    assert started["properties"]["topic_corrected"] is True
    spans = {event["properties"]["name"] for event in _named(events, "span")}
    assert {"scan.discovery", "scan.export"} <= spans
    assert "_schema_problems" not in started["properties"]


def test_scan_does_not_flag_an_already_correct_topic(monkeypatch):
    events = _run_scan(monkeypatch, "Large language models in healthcare")
    assert _named(events, "scan_started")[0]["properties"]["topic_corrected"] is False
