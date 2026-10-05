"""Scan-side model calls: one retry on a transient error, failover, and every attempt recorded with its cost."""

import json
from types import SimpleNamespace

import pytest

from app.reports.dossier_generator import DossierGenerator
from app.synthesis.call_ledger import RequestLedger
from app.synthesis.insight_engine import InsightEngine
from app.synthesis.providers import (
    ClaudeSynthesisProvider, GeminiSynthesisProvider, SynthesisProvider, SynthesisProviderError,
    SynthesisProviderRegistry, SynthesisRateLimitError, is_transient_error,
)
from tests.test_metrics_catalog import measure, row


class Scripted(SynthesisProvider):
    """Plays back a list of outcomes: an Exception is raised, a string is returned."""

    def __init__(self, name, outcomes, usage=(1000, 200)):
        self.name, self.outcomes, self.calls, self._usage, self.model = name, list(outcomes), 0, usage, f"{name}-model"

    def is_configured(self):
        return True

    def generate_text(self, prompt, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        self.last_usage = self._usage
        return outcome


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    sleeps = []
    monkeypatch.setattr("app.synthesis.providers.time.sleep", lambda seconds: sleeps.append(seconds))
    return sleeps


def overloaded(provider="gemini"):
    return SynthesisProviderError(f"{provider} generation error: 503 UNAVAILABLE. high demand", provider=provider,
                                  error_type="provider_error", raw_error=RuntimeError("503 UNAVAILABLE high demand"))


# --- which errors are worth another try ---------------------------------------------------------------------------------

@pytest.mark.parametrize("message, expected", [
    ("503 UNAVAILABLE. This model is currently experiencing high demand", True),
    ("Error code: 529 - overloaded_error", True),
    ("Request timed out", True),
    ("429 rate_limit_error: too many requests", True),
    ("429 RESOURCE_EXHAUSTED: quota exceeded for the day", False),
    ("401 invalid x-api-key", False),
    ("400 bad request", False),
])
def test_only_short_lived_errors_are_retried(message, expected):
    assert is_transient_error(RuntimeError(message)) is expected


def test_the_wrapped_provider_wording_does_not_hide_a_transient_error():
    wrapped = SynthesisRateLimitError("Anthropic quota/rate limit: 529 overloaded_error", raw_error=RuntimeError("529 overloaded_error"))
    assert is_transient_error(wrapped) is True


# --- retry, failover, ledger ------------------------------------------------------------------------------------------------

def test_a_transient_error_is_retried_once_on_the_same_provider(no_waiting):
    first = Scripted("claude", [overloaded("claude"), "recovered"])
    second = Scripted("gemini", ["should not be needed"])
    ledger = RequestLedger(request_id="rid-12345678")

    text, provider = SynthesisProviderRegistry(providers=[first, second]).generate_with_failover(
        "prompt", ledger=ledger, purpose="scan_summary")

    assert (text, provider) == ("recovered", "claude") and second.calls == 0
    assert [(c.attempt, c.outcome) for c in ledger.calls] == [(1, "provider_error"), (2, "ok")]
    assert no_waiting == [SynthesisProviderRegistry.retry_delay_seconds]


def test_a_second_failure_moves_on_to_the_next_provider():
    first = Scripted("claude", [overloaded("claude"), overloaded("claude")])
    second = Scripted("gemini", ["from gemini"])
    ledger = RequestLedger(request_id="rid-12345678")

    text, provider = SynthesisProviderRegistry(providers=[first, second]).generate_with_failover(
        "prompt", ledger=ledger, purpose="scan_summary")

    assert (text, provider) == ("from gemini", "gemini") and first.calls == 2
    assert [(c.provider, c.attempt, c.outcome) for c in ledger.calls] == [
        ("claude", 1, "provider_error"), ("claude", 2, "provider_error"), ("gemini", 1, "ok")]


def test_a_permanent_error_is_not_retried(no_waiting):
    bad = Scripted("claude", [SynthesisProviderError("Anthropic generation error: 401 invalid x-api-key")])
    good = Scripted("gemini", ["ok"])
    assert SynthesisProviderRegistry(providers=[bad, good]).generate_with_failover("p")[1] == "gemini"
    assert bad.calls == 1 and no_waiting == []


def test_when_every_provider_fails_the_last_error_is_raised_and_everything_is_recorded():
    ledger = RequestLedger(request_id="rid-12345678")
    registry = SynthesisProviderRegistry(providers=[Scripted("claude", [overloaded(), overloaded()]),
                                                    Scripted("gemini", [overloaded(), overloaded()])])
    with pytest.raises(SynthesisProviderError):
        registry.generate_with_failover("p", ledger=ledger, purpose="scan_summary")
    assert len(ledger.calls) == 4 and all(c.outcome == "provider_error" for c in ledger.calls)


def test_calls_record_purpose_model_tokens_and_latency():
    ledger = RequestLedger(request_id="rid-12345678")
    SynthesisProviderRegistry(providers=[Scripted("claude", ["fine"], usage=(2500, 400))]).generate_with_failover(
        "p", ledger=ledger, purpose="dossier_themes")
    call = ledger.calls[0]
    assert (call.purpose, call.provider, call.model, call.outcome) == ("dossier_themes", "claude", "claude-model", "ok")
    assert (call.input_tokens, call.output_tokens) == (2500, 400) and call.latency_ms is not None


def test_an_exhausted_call_budget_never_breaks_a_scan():
    ledger = RequestLedger(request_id="rid-12345678", max_calls=1)
    registry = SynthesisProviderRegistry(providers=[Scripted("claude", ["a", "b"])])
    assert registry.generate_with_failover("p", ledger=ledger)[0] == "a"
    assert registry.generate_with_failover("p", ledger=ledger)[0] == "b"
    assert len(ledger.calls) == 1


def test_the_old_call_without_a_ledger_still_works():
    assert SynthesisProviderRegistry(providers=[Scripted("claude", ["x"])]).generate_with_failover("p") == ("x", "claude")


# --- real provider classes report usage --------------------------------------------------------------------------------------

def test_claude_reports_token_usage():
    provider = ClaudeSynthesisProvider(api_key="test")
    provider.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
        content=[SimpleNamespace(type="text", text="hello")], usage=SimpleNamespace(input_tokens=321, output_tokens=45))))
    assert provider.generate_text("p") == "hello" and provider.last_usage == (321, 45)


def test_gemini_reports_token_usage():
    provider = GeminiSynthesisProvider(api_key="test")
    provider.client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(
        text="hello", usage_metadata=SimpleNamespace(prompt_token_count=111, candidates_token_count=22))))
    assert provider.generate_text("p") == "hello" and provider.last_usage == (111, 22)


# --- the scan summary and the dossier use it ------------------------------------------------------------------------------------

def test_the_scan_summary_goes_through_the_registry_so_it_survives_a_gemini_outage():
    ledger = RequestLedger(request_id="rid-12345678")
    registry = SynthesisProviderRegistry(providers=[Scripted("gemini", [overloaded(), overloaded()]), Scripted("claude", ["A real summary."])])
    result = InsightEngine(registry=registry).generate_insight(
        "Testing AI", [{"id": "1", "title": "T", "abstract": "Some abstract text about testing AI."}], ledger=ledger)
    assert result.status == "ai" and result.insight == "A real summary."
    assert {c.purpose for c in ledger.calls} == {"scan_summary"}


def test_a_summary_with_every_provider_down_is_reported_not_invented():
    registry = SynthesisProviderRegistry(providers=[Scripted("gemini", [overloaded(), overloaded()])])
    result = InsightEngine(registry=registry).generate_insight(
        "Testing AI", [{"id": "1", "title": "T", "abstract": "Some abstract text about testing AI."}])
    assert result.status == "template"


def test_the_dossier_records_its_call_with_its_own_purpose():
    ledger = RequestLedger(request_id="rid-12345678")
    provider = Scripted("claude", ["ABSTRACT: A.\nKEY THEMES: T1\nCONTRADICTIONS: C1\nRESEARCH GAPS: G1\nRESEARCH AREAS: R1\n"
                                   "OPPORTUNITY AREAS: O1\nPROBLEMS TO SOLVE: P1\n"])
    DossierGenerator(provider_registry=SynthesisProviderRegistry(providers=[provider])).generate_comprehensive_dossier(
        query="topic", included_sources=[{"title": "T", "abstract": "A", "year": 2024}], ledger=ledger)
    assert [c.purpose for c in ledger.calls] == ["dossier_themes"]


# --- the metric ------------------------------------------------------------------------------------------------------------------------

def test_scan_cost_counts_summary_themes_and_relevance_calls_together(monkeypatch):
    monkeypatch.setenv("LLM_PRICES_JSON", json.dumps({"priced": {"input": 1.0, "output": 5.0}}))
    rows = [
        row("llm_call", model="priced", purpose="scan_summary", input_tokens=1_000_000, output_tokens=0, request_id="rep-scan0001"),
        row("llm_call", model="priced", purpose="dossier_themes", input_tokens=1_000_000, output_tokens=0, request_id="rep-scan0001"),
        row("llm_call", model="priced", purpose="proposal_synthesis", input_tokens=9_000_000, output_tokens=0, request_id="rep-prop0001"),
    ]
    assert measure(rows, "cost_per_scan")["value"] == pytest.approx(2.0)
    assert measure(rows, "cost_per_proposal")["value"] == pytest.approx(9.0)


# --- the scan handler records the calls -------------------------------------------------------------------------------------------------

import asyncio
from pathlib import Path

import cloud_app
from tests.test_free_tier_exposure import World, sources


@pytest.fixture
def world(monkeypatch, tmp_path, fake_provider, synthesized_draft_json):
    return World(monkeypatch, tmp_path, fake_provider, synthesized_draft_json)


class LedgerPipeline:
    """A pipeline that makes one billed model call through the ledger the handler gives it."""

    def __init__(self, fail=False):
        self.fail = fail

    def run_research(self, **kwargs):
        ledger = kwargs["ledger"]
        call = ledger.add_call("scan_summary", "anthropic", "claude-test")
        ledger.complete_call(call, "ok", input_tokens=1200, output_tokens=300, latency_ms=900)
        if self.fail:
            raise RuntimeError("the scan blew up after a billed call")
        Path(kwargs["output_directory"], "research_audit_x_20261001_120000.xlsx").write_bytes(b"workbook")
        return {"status": "success", "included": sources(2), "excluded": [],
                "discovery_report_name": "research_audit_x_20261001_120000.xlsx"}


def test_a_scans_model_calls_become_llm_call_events_with_the_requests_id(world, monkeypatch):
    monkeypatch.setattr(cloud_app, "pipeline", LedgerPipeline())
    asyncio.run(cloud_app.execute_cloud_scan(cloud_app.ScanRequest(topic="AI evidence"), authorization="Bearer t"))

    calls = [e for e in world.events if e["event_name"] == "llm_call"]
    assert len(calls) == 1
    assert calls[0]["properties"]["purpose"] == "scan_summary" and calls[0]["properties"]["input_tokens"] == 1200


def test_calls_are_recorded_even_when_the_scan_fails(world, monkeypatch):
    monkeypatch.setattr(cloud_app, "pipeline", LedgerPipeline(fail=True))
    with pytest.raises(Exception):
        asyncio.run(cloud_app.execute_cloud_scan(cloud_app.ScanRequest(topic="AI evidence"), authorization="Bearer t"))
    assert [e["properties"]["purpose"] for e in world.events if e["event_name"] == "llm_call"] == ["scan_summary"]
