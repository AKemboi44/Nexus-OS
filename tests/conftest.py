import json

import pytest


class _UnconfiguredProvider:
    name = "unconfigured"

    def is_configured(self):
        return False


class FakeProvider:
    """Stands in for the model provider and counts calls."""
    name = "fake"

    def __init__(self, content=None, error=None):
        # `content` may be a list of responses served in order (the last one repeats).
        self.content = content
        self.error = error
        self.calls = 0
        self.prompts = []

    def is_configured(self):
        return True

    async def generate_structured_once(self, **kwargs):
        self.calls += 1
        self.prompts.append(kwargs.get("prompt_user", ""))
        if self.error:
            raise self.error
        content = self.content
        if isinstance(content, list):
            content = content[min(self.calls, len(content)) - 1]
        return {"content": content, "provider": "fake", "model": "fake-model",
                "input_tokens": 1, "output_tokens": 1}


_SENTENCES = (
    "Scholars examining this area increasingly emphasise how institutional context, measurement choices "
    "and stakeholder expectations jointly shape the outcomes that different studies report.",
    "Taken together, the available accounts point toward a pattern in which design decisions made early "
    "in a project constrain what later evaluation can credibly conclude.",
    "Where the sources diverge, the disagreement appears to originate in unlike populations and unlike "
    "success criteria rather than in outright contradictory evidence.",
    "A careful reading therefore treats each contribution as one partial view that gains meaning only "
    "when positioned against the others in the set.",
    "This reasoning motivates a proposal that is explicit about assumptions, transparent about limits, "
    "and deliberately incremental in the claims it seeks to defend.",
)


def _paragraph(kind="evidence", ids=("S1", "S2"), offset=0):
    text = " ".join(_SENTENCES[(offset + i) % len(_SENTENCES)] for i in range(len(_SENTENCES)))
    return {"text": text, "kind": kind, "evidence_ids": list(ids)}


def build_synthesized_draft(**overrides):
    draft = {
        "schema_version": "proposal.v2",
        "overview": [_paragraph(offset=0)],
        "literature_insights": [
            {"title": "Design choices and reported outcomes", "blocks": [_paragraph(offset=1)]},
            {"title": "Sources of disagreement", "blocks": [_paragraph(ids=("S2", "S3"), offset=2)]},
            {"title": "Implications for practice", "blocks": [_paragraph(ids=("S1",), offset=3)]},
        ],
        "contradictions_and_limitations": [_paragraph(ids=("S1", "S3"), offset=4)],
        "research_gap": [_paragraph(offset=0)],
        "research_problem": [_paragraph(offset=1)],
        "research_questions": [
            {"question_id": "RQ1", "text": "How do design decisions shape reported outcomes?", "evidence_ids": []},
            {"question_id": "RQ2", "text": "Which criteria explain disagreement between studies?", "evidence_ids": []},
        ],
        "research_objectives": [
            {"text": "To compare how existing studies define success.", "question_ids": ["RQ1"], "evidence_ids": []},
            {"text": "To explain divergent findings across settings.", "question_ids": ["RQ2"], "evidence_ids": []},
        ],
        "methodology": {
            "research_design": [_paragraph("proposal", (), 2)],
            "data_collection": [_paragraph("proposal", (), 3)],
            "analysis": [_paragraph("proposal", (), 4)],
            "limitations": [_paragraph("limitation", (), 0)],
        },
        "conclusion": [_paragraph("interpretation", ("S1", "S2", "S3"), 1)],
        "evidence_limitations": [_paragraph("limitation", (), 2)],
    }
    draft.update(overrides)
    return json.dumps(draft)


@pytest.fixture
def fake_provider():
    return FakeProvider


@pytest.fixture
def synthesized_draft_json():
    return build_synthesized_draft


@pytest.fixture(autouse=True)
def no_live_proposal_provider(monkeypatch):
    """Tests must never reach a real model provider, whatever keys exist in the environment."""
    monkeypatch.setattr("app.reports.proposal_service._default_provider", lambda: _UnconfiguredProvider())


@pytest.fixture(autouse=True)
def no_live_synthesis_providers(monkeypatch):
    """Scans, summaries and relevance checks must not call a real model whatever keys the machine has."""
    from app.synthesis.providers import SynthesisProviderRegistry
    monkeypatch.setattr(SynthesisProviderRegistry, "_discover_providers", classmethod(lambda cls: []))
