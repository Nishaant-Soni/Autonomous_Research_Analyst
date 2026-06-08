"""Reliability + observability wiring (plan 3.6/3.7). All DB-/network-free: we check the
knobs are forwarded, not that a live timeout fires (the SDK owns the actual retry/timeout)."""

from typing import Any

from app.llm.provider import LLMProvider, OpenAIProvider


def test_provider_forwards_timeout_and_retries_to_client():
    # Client construction is offline; assert our reliability knobs reach the OpenAI client.
    provider = OpenAIProvider(api_key="x", timeout=12.5, max_retries=4)
    client = provider._get_client()
    assert client.timeout == 12.5
    assert client.max_retries == 4


class _RecordingProvider(LLMProvider):
    """Captures the kwargs of the last complete() call and returns a canned response."""

    def __init__(self, output_text: str = "{}"):
        self.calls: list[dict[str, Any]] = []
        self._output_text = output_text

    def complete(self, messages, tools=None, **kwargs):
        self.calls.append(kwargs)

        class _Resp:
            output_text = self._output_text
            output: list = []

        return _Resp()


def test_planner_sets_token_budget():
    from app.agents.planner import _MAX_OUTPUT_TOKENS, plan_research

    provider = _RecordingProvider(output_text='{"sub_questions": ["a", "b", "c"]}')
    plan_research("q", provider=provider)
    assert provider.calls[-1]["max_output_tokens"] == _MAX_OUTPUT_TOKENS


def test_critic_sets_token_budget():
    from app.agents.critic import _MAX_OUTPUT_TOKENS, critique_findings

    provider = _RecordingProvider(
        output_text='{"groundedness": 0.5, "needs_more_research": false, "gaps": [], "contradictions": []}'
    )
    critique_findings("q", ["s1"], "draft", [], provider=provider)
    assert provider.calls[-1]["max_output_tokens"] == _MAX_OUTPUT_TOKENS


def test_writer_sets_token_budget():
    from app.agents.writer import _MAX_OUTPUT_TOKENS, write_report

    provider = _RecordingProvider(output_text="# Report")
    write_report("q", [], provider=provider)
    assert provider.calls[-1]["max_output_tokens"] == _MAX_OUTPUT_TOKENS


def test_configure_langsmith_is_noop_without_key(monkeypatch):
    import app.observability as obs

    monkeypatch.setattr(obs.settings, "langsmith_api_key", "")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    assert obs.configure_langsmith() is False
    import os

    assert os.environ.get("LANGSMITH_TRACING") is None


def test_configure_langsmith_enables_with_key(monkeypatch):
    import os

    import app.observability as obs

    monkeypatch.setattr(obs.settings, "langsmith_api_key", "ls-test-key")
    monkeypatch.setattr(obs.settings, "langsmith_project", "proj-x")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    assert obs.configure_langsmith() is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-test-key"
    assert os.environ["LANGSMITH_PROJECT"] == "proj-x"
