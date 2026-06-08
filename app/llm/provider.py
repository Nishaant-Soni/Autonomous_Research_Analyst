"""Thin LLM provider interface.

One default (OpenAI), swappable behind a small interface (PRD §7). Kept intentionally
minimal — just enough surface for the agents in Phase 2 to call `complete(...)`.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Return a chat completion for the given messages (and optional tools)."""
        ...


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.4-mini",
        timeout: float | None = None,
        max_retries: int | None = None,
        trace: bool = False,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._timeout = timeout  # per-call timeout; SDK retries handle transient errors
        self._max_retries = max_retries
        self._trace = trace  # wrap with LangSmith tracing (token usage + latency)
        self._client: Any = None  # created lazily so instantiation needs no key

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self._api_key or None}
            if self._timeout is not None:
                kwargs["timeout"] = self._timeout
            if self._max_retries is not None:
                kwargs["max_retries"] = self._max_retries
            client = OpenAI(**kwargs)
            if self._trace:
                from langsmith.wrappers import wrap_openai

                client = wrap_openai(client)
            self._client = client
        return self._client

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        # Newer models use the Responses API: `messages` map to `input`. Per-call
        # knobs (reasoning_effort, max_completion_tokens, store, ...) pass via kwargs.
        params: dict[str, Any] = {"model": self.model, "input": messages, **kwargs}
        if tools is not None:
            params["tools"] = tools
        return self._get_client().responses.create(**params)


_default_provider: LLMProvider | None = None


def get_default_provider() -> LLMProvider:
    """The shared default provider for the agent nodes.

    Cached so every node reuses one provider (and thus one lazily-created OpenAI client /
    connection pool) across a graph run, instead of each node building its own. Nodes still
    accept an injected `provider` for tests; this is only the fallback when none is given.
    """
    global _default_provider
    if _default_provider is None:
        from app.config import settings

        _default_provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            trace=bool(settings.langsmith_api_key),
        )
    return _default_provider
