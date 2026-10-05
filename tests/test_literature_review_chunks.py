"""The complete literature review is written in small validated chunks, so one bad paragraph or a cut-off answer
no longer sinks the whole report, and failures can be traced."""

import json
import logging
import re
from types import SimpleNamespace

import pytest

import cloud_app
from app.agents.scribe_agent import ReportProviderLimitError, ScribeResearchAgent
from app.synthesis.call_ledger import RequestLedger
from tests.test_free_tier_exposure import AUTH, RUN_A, World  # noqa: F401 (World is used by the fixture below)

GOOD = (
    "Scholars studying this topic emphasise how context, measurement and design choices shape the outcomes "
    "that different studies report. The supplied evidence supports a cautious reading of these patterns "
    "rather than a universal claim. Differences between studies appear to reflect unlike populations and "
    "unlike success criteria in practice. A careful synthesis therefore treats each contribution as one "
    "partial view and asks what further evidence would settle the question."
)
SOURCES = [
    {"uid": f"s{i}", "title": f"Study {i} of reasoning evaluation", "authors": ["A. Author"], "year": 2024 - i,
     "venue": "Journal", "doi": f"10.1/{i}", "abstract": "Reasoning evaluation across models and tasks."}
    for i in range(1, 5)
]
THEMES = [f"Theme {n} about reasoning evaluation" for n in range(1, 7)]
CONTRADICTIONS = ["Benchmarks disagree on reasoning evaluation outcomes"]
GAPS = ["Few studies compare reasoning evaluation across languages", "Long-horizon reasoning evaluation is untested"]


def ids_in(prompt):
    return re.findall(r'"id": "([^"]+)"', prompt.split("Report sections:")[1])


def reply(text, stop="end_turn", output_tokens=900):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
        usage=SimpleNamespace(input_tokens=1200, output_tokens=output_tokens),
    )


def good_json(ids, **overrides):
    items = [{"id": i, "paragraphs": overrides.get(i, [GOOD, GOOD])} for i in ids]
    return json.dumps({"paragraphs": items})


class FakeClaude:
    """Records every request; `script(ids, call_number)` decides the reply."""

    def __init__(self, script):
        self.requests, self.script = [], script
        self.messages = self

    def create(self, **request):
        prompt = request["messages"][0]["content"]
        ids = ids_in(prompt)
        self.requests.append({"ids": ids, "max_tokens": request["max_tokens"], "prompt": prompt})
        return self.script(ids, len(self.requests))


class FakeGemini:
    def __init__(self):
        self.calls = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(text="", usage_metadata=None)


def agent_with(script, gemini=None, ledger=None):
    agent = ScribeResearchAgent()
    agent.client, agent.provider, agent.model = FakeClaude(script), "anthropic", "claude-test"
    agent.gemini_client = gemini
    agent.ledger = ledger
    return agent


def prepare(agent):
    agent._prepare_editorial_synthesis(
        "Reasoning evaluation", SOURCES, THEMES, CONTRADICTIONS, GAPS, ["Area one on reasoning evaluation"],
        ["Opportunity on reasoning evaluation"], ["The problem of reasoning evaluation"], "full_starter", "scholarly",
    )
    return agent


# --- chunking ------------------------------------------------------------------------------------------------------

def test_the_review_is_requested_in_small_chunks_not_one_giant_call():
    agent = prepare(agent_with(lambda ids, n: reply(good_json(ids))))
    requests = agent.client.requests
    total_ids = [i for r in requests for i in r["ids"]]

    assert agent._editorial_synthesis_complete is True
    assert len(requests) >= 3 and all(len(r["ids"]) <= 5 for r in requests)
    assert len(total_ids) == len(set(total_ids)) and len(total_ids) >= 15, "every item exactly once"
    assert all(r["max_tokens"] == 4096 for r in requests)


def test_chunks_are_independent_so_all_items_land_in_the_cache():
    agent = prepare(agent_with(lambda ids, n: reply(good_json(ids))))
    assert len(agent._editorial_cache) == sum(len(r["ids"]) for r in agent.client.requests)


# --- failures are contained ---------------------------------------------------------------------------------------------

def test_a_cut_off_answer_in_one_chunk_is_retried_in_smaller_pieces_and_the_rest_is_kept():
    def script(ids, n):
        if n == 1:
            return reply('{"paragraphs": [{"id": "x", "paragraphs": ["cut off mid', stop="max_tokens", output_tokens=4096)
        return reply(good_json(ids))

    gemini = FakeGemini()
    agent = prepare(agent_with(script, gemini=gemini))

    assert agent._editorial_synthesis_complete is True
    assert gemini.calls == 0, "a truncated small chunk must not be handed to Gemini"
    retried = [r for r in agent.client.requests if len(r["ids"]) <= 3]
    assert retried, "the failed chunk was retried in smaller chunks"


def test_one_bad_paragraph_is_retried_alone_and_does_not_fail_the_report():
    seen = {"bad": None}

    def script(ids, n):
        if seen["bad"] is None:
            seen["bad"] = ids[1]
            return reply(good_json(ids, **{ids[1]: ["Too short.", GOOD]}))
        return reply(good_json(ids))

    agent = prepare(agent_with(script))
    assert agent._editorial_synthesis_complete is True
    assert any(r["ids"] == [seen["bad"]] or seen["bad"] in r["ids"] for r in agent.client.requests[1:])


def test_an_item_that_never_passes_leaves_the_review_incomplete_but_keeps_the_others():
    def script(ids, n):
        return reply(good_json(ids, **{ids[0]: [GOOD]}))  # first id of every request is always one paragraph short

    agent = prepare(agent_with(script))
    assert agent._editorial_synthesis_complete is False
    assert len(agent._editorial_cache) > 0


def test_every_rule_rejects_what_it_should():
    def check(paragraphs):
        agent = prepare(agent_with(lambda ids, n: reply(good_json(ids, **({ids[0]: paragraphs} if n == 1 else {})))))
        return agent

    for bad in (
        [GOOD],                                   # one paragraph
        [GOOD, "Two sentences only. Not enough."],  # too short
        [GOOD, GOOD[:-1]],                        # does not end in punctuation
        [GOOD, ("word " * 160).strip() + "."],    # too long
        [GOOD, GOOD.replace("shape the outcomes", "shape shape shape the outcomes")],  # repeated-word corruption
    ):
        assert check(bad)._editorial_synthesis_complete is True, "retried alone and then accepted"


def test_provider_limits_still_surface_as_a_capacity_error_so_the_queue_path_works():
    def script(ids, n):
        raise RuntimeError("429 rate_limit_error: too many requests")

    with pytest.raises(ReportProviderLimitError):
        prepare(agent_with(script))


def test_the_number_of_model_calls_is_bounded():
    agent = prepare(agent_with(lambda ids, n: reply("not json at all")))
    assert agent._editorial_synthesis_complete is False
    assert len(agent.client.requests) <= 12, "two rounds at most, never an endless loop"


# --- observability -------------------------------------------------------------------------------------------------------

def test_rejections_are_logged_with_the_rule_that_fired(caplog):
    caplog.set_level(logging.INFO, logger="app.agents.scribe_agent")
    prepare(agent_with(lambda ids, n: reply(good_json(ids, **{ids[0]: ["Too short.", GOOD]}) if n == 1 else good_json(ids))))
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "word_count" in text and "literature review" in text.lower()


def test_unparsable_answers_are_logged_not_printed(caplog, capsys):
    caplog.set_level(logging.WARNING, logger="app.agents.scribe_agent")
    prepare(agent_with(lambda ids, n: reply("not json")))
    assert "invalid_json" in " ".join(record.getMessage() for record in caplog.records)
    assert "[Scribe Synthesis Warning]" not in capsys.readouterr().out


def test_model_calls_are_recorded_in_the_ledger_with_tokens():
    ledger = RequestLedger(request_id="rid-12345678", max_calls=40)
    agent = prepare(agent_with(lambda ids, n: reply(good_json(ids)), ledger=ledger))
    assert len(ledger.calls) == len(agent.client.requests)
    call = ledger.calls[0]
    assert (call.purpose, call.provider, call.model, call.outcome) == ("literature_review", "anthropic", "claude-test", "ok")
    assert call.input_tokens == 1200 and call.output_tokens == 900 and call.latency_ms is not None


def test_a_truncated_answer_is_recorded_as_such():
    ledger = RequestLedger(request_id="rid-12345678", max_calls=40)
    prepare(agent_with(lambda ids, n: reply("{", stop="max_tokens") if n == 1 else reply(good_json(ids)), ledger=ledger))
    assert ledger.calls[0].outcome == "invalid_output" and ledger.calls[0].error_kind == "max_tokens"


# --- the endpoint: traceable failures --------------------------------------------------------------------------------------

@pytest.fixture
def world(monkeypatch, tmp_path, fake_provider, synthesized_draft_json):
    return World(monkeypatch, tmp_path, fake_provider, synthesized_draft_json)


class IncompleteAgent:
    """Stands in for ScribeResearchAgent when the editor cannot finish."""

    provider, model = "anthropic", "claude-test"

    def generate_complete_literature_review(self, **kwargs):
        raise cloud_app.ReportSynthesisError(
            "The report editor did not produce complete, validated prose. No outline or prompt text was included."
        )


def test_a_failed_literature_review_returns_the_request_id_as_its_reference(world, monkeypatch):
    world.paid = True
    world.seed_run(RUN_A)
    monkeypatch.setattr("app.agents.scribe_agent.ScribeResearchAgent", IncompleteAgent)
    monkeypatch.setattr("app.reports.dossier_generator.DossierGenerator.generate_comprehensive_dossier",
                        lambda self, **kw: SimpleNamespace(quality_report={}), raising=True)

    response = world.client.post(
        "/v1/reports", headers=AUTH,
        json={"topic": "Reasoning evaluation", "research_run_id": RUN_A, "report_type": "full_starter"},
    )
    detail = response.json()["detail"]

    assert response.status_code == 503
    assert detail["error_code"] == "report_incomplete" and detail["retryable"] is True
    assert "try again" in detail["message"].lower()
    request_id = response.headers["X-Request-ID"]
    assert detail["reference"] == request_id, "the id on the error card is the id the trace lookup uses"
    failed = [e for e in world.events if e["event_name"] == "report_failed"]
    assert failed and failed[-1]["properties"]["request_id"] == request_id


def test_the_website_shows_a_friendly_card_for_an_unfinished_review():
    js = open(cloud_app.__file__.replace("cloud_app.py", "website/app.js"), encoding="utf-8").read()
    assert "errorCode === 'report_incomplete'" in js
    assert "Literature review not finished" in js


# --- cost metrics keep proposals and literature reviews apart ---------------------------------------------------------------

def test_proposal_cost_ignores_literature_review_calls_and_the_review_has_its_own_metric(monkeypatch):
    from tests.test_metrics_catalog import measure, row
    monkeypatch.setenv("LLM_PRICES_JSON", json.dumps({"priced": {"input": 1.0, "output": 5.0}}))
    rows = [
        row("llm_call", model="priced", purpose="proposal_synthesis", input_tokens=1_000_000, output_tokens=0, request_id="rep-proposal1"),
        row("llm_call", model="priced", purpose="literature_review", input_tokens=2_000_000, output_tokens=0, request_id="rep-review001"),
        row("llm_call", model="priced", purpose="literature_review", input_tokens=2_000_000, output_tokens=0, request_id="rep-review001"),
        row("llm_call", model="priced", input_tokens=3_000_000, output_tokens=0, request_id="rep-legacy001"),  # older rows have no purpose
    ]
    assert measure(rows, "cost_per_proposal")["value"] == pytest.approx(2.0)   # mean of $1 and $3
    assert measure(rows, "cost_per_literature_review")["value"] == pytest.approx(4.0)
