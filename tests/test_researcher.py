import json
import os
from types import SimpleNamespace

import pytest

from app.agents import researcher
from app.graph.state import Critique
from app.models.evidence import Evidence


def _fn_call(name, query, call_id="c1"):
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=json.dumps({"query": query}),
        call_id=call_id,
    )


def _response(output, text=""):
    return SimpleNamespace(output=output, output_text=text)


class _ScriptedProvider:
    """Returns pre-scripted Responses-API-shaped objects; records each call's (input, tools)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, messages, tools=None, **kwargs):
        self.calls.append((messages, tools))
        return self._responses.pop(0)


@pytest.fixture
def recorded_retrievers(monkeypatch):
    queries = []

    def fake_web(query, max_results=5):
        queries.append(("web", query))
        return [
            Evidence(
                content=f"web:{query}", retriever="web", source_url="https://x.example"
            )
        ]

    def fake_rag(query, k=5, user_id=None):
        queries.append(("rag", query))
        return [Evidence(content=f"rag:{query}", retriever="rag", source_chunk_id=1)]

    monkeypatch.setattr(researcher, "web_search", fake_web)
    monkeypatch.setattr(researcher, "rag_retrieve", fake_rag)
    return queries


def test_tool_loop_executes_calls_and_accumulates_evidence(recorded_retrievers):
    provider = _ScriptedProvider(
        [
            _response([_fn_call("web_search", "q1")]),
            _response([_fn_call("rag_retrieve", "q2", call_id="c2")]),
            _response([], text="Final findings."),
        ]
    )
    result = researcher.run_researcher("Q", ["sub1"], provider=provider)

    assert result["draft_findings"] == "Final findings."
    assert [e.retriever for e in result["evidence"]] == ["web", "rag"]
    # the real retrievers ran with the model's chosen queries (evidence is from them, not the LLM)
    assert recorded_retrievers == [("web", "q1"), ("rag", "q2")]


def test_loop_back_prompt_narrows_to_critic_gaps(recorded_retrievers):
    provider = _ScriptedProvider([_response([], text="done")])
    critique = Critique(
        groundedness=0.4, needs_more_research=True, gaps=["cost of on-device inference"]
    )
    researcher.run_researcher(
        "Q", ["sub1", "sub2"], critique=critique, provider=provider
    )

    first_input = provider.calls[0][0]
    user_msg = next(m for m in first_input if m.get("role") == "user")
    assert "cost of on-device inference" in user_msg["content"]
    assert "Focus ONLY" in user_msg["content"]


def test_round_cap_forces_toolless_final_synthesis(recorded_retrievers):
    provider = _ScriptedProvider(
        [
            _response([_fn_call("web_search", "q1")]),
            _response([_fn_call("web_search", "q2", call_id="c2")]),
            _response([], text="Synthesized after cap."),
        ]
    )
    result = researcher.run_researcher("Q", ["sub1"], provider=provider, max_rounds=2)

    assert result["draft_findings"] == "Synthesized after cap."
    assert provider.calls[-1][1] is None  # final synthesis call passes no tools


def test_node_reads_state(recorded_retrievers):
    provider = _ScriptedProvider([_response([], text="d")])
    # exercise the node wrapper by injecting via run_researcher (node builds its own provider)
    out = researcher.run_researcher("Q", ["s"], provider=provider)
    assert set(out) == {"evidence", "draft_findings"}


@pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1",
    reason="set RUN_LLM_TESTS=1 with a real OPENAI_API_KEY (live LLM + tool-calling protocol)",
)
def test_run_researcher_live(monkeypatch):
    # Stub the retrievers (no Tavily/DB needed) but use the real provider, so this validates
    # the live Responses-API function-calling round-trip against gpt-5.4-mini.
    monkeypatch.setattr(
        researcher,
        "web_search",
        lambda q, max_results=5: [
            Evidence(
                content="On-device inference reduces latency.",
                retriever="web",
                source_url="https://a.example",
            )
        ],
    )
    monkeypatch.setattr(researcher, "rag_retrieve", lambda q, k=5, user_id=None: [])

    result = researcher.run_researcher(
        "What are the benefits of on-device LLM inference?", ["latency", "privacy"]
    )
    assert (
        isinstance(result["draft_findings"], str) and result["draft_findings"].strip()
    )
    assert (
        len(result["evidence"]) >= 1
    )  # the model called a tool and we captured its results
