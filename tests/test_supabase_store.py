import pytest
import requests

from app.supabase_store import SupabaseRequestError, SupabaseRestClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.ok = status_code < 400
        self.content = b"response" if payload is not None or text else b""

    def json(self):
        if self.payload is None:
            raise ValueError("No JSON body.")
        return self.payload


def test_from_env_requires_both_supabase_credentials(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Both SUPABASE_URL"):
        SupabaseRestClient.from_env()


def test_insert_uses_service_role_and_returns_inserted_record(monkeypatch):
    client = SupabaseRestClient("https://example.supabase.co/", "server-secret")
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return FakeResponse(payload=[{"id": "run-1"}])

    monkeypatch.setattr(requests, "request", fake_request)

    result = client.insert("research_runs", {"query": "test"})

    assert result == {"id": "run-1"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.supabase.co/rest/v1/research_runs"
    assert captured["headers"]["Authorization"] == f"Bearer {client.service_role_key}"
    assert captured["headers"]["Prefer"] == "return=representation"
    assert captured["json"] == {"query": "test"}


def test_request_raises_status_aware_error_for_postgrest_failure(monkeypatch):
    client = SupabaseRestClient("https://example.supabase.co", "server-secret")

    def fake_request(*args, **kwargs):
        return FakeResponse(status_code=409, payload={"message": "duplicate"})

    monkeypatch.setattr(requests, "request", fake_request)

    with pytest.raises(SupabaseRequestError, match="duplicate") as error:
        client.request("POST", "payment_events", json={"event_id": "event-1"})

    assert error.value.status_code == 409
