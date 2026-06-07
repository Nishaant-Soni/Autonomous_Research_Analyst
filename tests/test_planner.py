import json
import os
from types import SimpleNamespace

import pytest

from app.agents import planner


class _FakeProvider:
    """Returns a Responses-API-shaped object whose `output_text` is the given payload."""

    def __init__(self, sub_questions):
        self._payload = json.dumps({"sub_questions": sub_questions})

    def complete(self, messages, tools=None, **kwargs):
        return SimpleNamespace(output_text=self._payload)


def test_plan_research_returns_sub_questions():
    subs = ["What is X?", "How does X compare to Y?", "What are X's limits?"]
    result = planner.plan_research("question", provider=_FakeProvider(subs))
    assert result == subs


def test_plan_research_clamps_to_upper_bound():
    subs = [f"sub-question {i}" for i in range(8)]  # 8 > max of 6
    result = planner.plan_research("q", provider=_FakeProvider(subs))
    assert len(result) == planner._MAX_SUBQUESTIONS


def test_plan_research_tolerates_json_fence():
    subs = ["a?", "b?", "c?"]
    fenced = SimpleNamespace(
        output_text="```json\n" + json.dumps({"sub_questions": subs}) + "\n```"
    )

    class _Fenced:
        def complete(self, messages, tools=None, **kwargs):
            return fenced

    assert planner.plan_research("q", provider=_Fenced()) == subs


def test_planner_node_populates_plan(monkeypatch):
    subs = ["one?", "two?", "three?"]
    # The node builds its own provider from settings; stub plan_research so it needs no key.
    monkeypatch.setattr(planner, "plan_research", lambda question: subs)
    update = planner.planner_node({"question": "what?"})  # type: ignore[arg-type]
    assert update == {"plan": subs}


@pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1",
    reason="set RUN_LLM_TESTS=1 with a real OPENAI_API_KEY (live LLM call)",
)
def test_plan_research_live():
    subs = planner.plan_research(
        "What is the competitive landscape for on-device LLM inference?"
    )
    assert 3 <= len(subs) <= 6
    assert all(isinstance(s, str) and s.strip() for s in subs)
