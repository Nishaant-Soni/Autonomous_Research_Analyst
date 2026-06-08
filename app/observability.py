"""LangSmith tracing wiring (plan 3.7, FR-11).

Env-gated: tracing turns on only when a `LANGSMITH_API_KEY` is configured. pydantic-settings
reads `.env` into the `Settings` object, but LangChain/LangGraph read tracing config from
`os.environ` — so when a key is present we mirror it (plus the project and the tracing flag)
into the process environment. With that set, LangGraph auto-traces each node as a span, and
the OpenAI client wrapped via `wrap_openai` (see `app.llm.provider`) adds per-call token usage
and latency. A no-op when no key is set.
"""

import os

from app.config import settings


def configure_langsmith() -> bool:
    """Enable LangSmith tracing if a key is configured. Returns whether it was enabled."""
    if not settings.langsmith_api_key:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    return True
