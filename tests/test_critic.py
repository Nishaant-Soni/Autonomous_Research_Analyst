import json
import os
from types import SimpleNamespace

import pytest

from app.agents import critic
from app.graph.state import Critique
from app.models.evidence import Evidence


class _FakeProvider:
    def __init__(self, payload):
        self._payload = json.dumps(payload) if isinstance(payload, dict) else payload

    def complete(self, messages, tools=None, **kwargs):
        return SimpleNamespace(output_text=self._payload)


def _evidence():
    return [
        Evidence(
            content="Paris is the capital of France.",
            retriever="web",
            source_url="https://x",
        )
    ]


def test_flags_unsupported_claim_and_requests_more_research():
    provider = _FakeProvider(
        {
            "groundedness": 0.3,
            "needs_more_research": True,
            "gaps": ["population of France"],
            "contradictions": [],
        }
    )
    result = critic.critique_findings(
        "Q", ["capital", "population"], "draft", _evidence(), provider
    )
    assert isinstance(result, Critique)
    assert result.needs_more_research is True
    assert result.gaps == ["population of France"]


def test_well_grounded_draft_does_not_request_more_research():
    provider = _FakeProvider(
        {
            "groundedness": 0.95,
            "needs_more_research": False,
            "gaps": [],
            "contradictions": [],
        }
    )
    result = critic.critique_findings(
        "Q", ["capital"], "Paris is the capital [1].", _evidence(), provider
    )
    assert result.needs_more_research is False
    assert result.groundedness == 0.95


def test_groundedness_is_clamped_to_bound():
    provider = _FakeProvider(
        {
            "groundedness": 1.5,
            "needs_more_research": False,
            "gaps": [],
            "contradictions": [],
        }
    )
    result = critic.critique_findings("Q", [], "d", _evidence(), provider)
    assert (
        result.groundedness == 1.0
    )  # clamped into [0, 1] so the Critique model validates


def test_tolerates_json_fence():
    provider = _FakeProvider(
        '```json\n{"groundedness": 0.5, "needs_more_research": false, "gaps": [], "contradictions": []}\n```'
    )
    result = critic.critique_findings("Q", [], "d", _evidence(), provider)
    assert result.groundedness == 0.5


@pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1",
    reason="set RUN_LLM_TESTS=1 with a real OPENAI_API_KEY (live LLM call)",
)
def test_critique_findings_live():
    evidence = [
        Evidence(
            content="The Eiffel Tower is in Paris.",
            retriever="web",
            source_url="https://a.example",
        )
    ]
    draft = "The Eiffel Tower is in Paris. It was built in 1889 by aliens."  # 2nd claim unsupported
    result = critic.critique_findings(
        "Tell me about the Eiffel Tower.", ["location", "history"], draft, evidence
    )
    assert isinstance(result, Critique)
    assert 0.0 <= result.groundedness <= 1.0
    assert isinstance(result.needs_more_research, bool)
