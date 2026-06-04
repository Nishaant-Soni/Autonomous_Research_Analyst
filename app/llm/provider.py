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
    def __init__(self, api_key: str | None = None, model: str = "gpt-5.4-mini") -> None:
        self._api_key = api_key
        self.model = model
        self._client: Any = None  # created lazily so instantiation needs no key

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key or None)
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
