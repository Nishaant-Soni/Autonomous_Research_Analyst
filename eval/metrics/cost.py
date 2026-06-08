"""Per-item cost in USD, sourced from LangSmith token usage (plan 4.4 B3).

Strategy: each eval item's graph run is tagged at eval time with
`run_name="eval:<run_id>:<item.id>"` and `metadata={"eval_run_id", "eval_item_id"}`
(see `eval.runner.run_one_question`). At score time we query LangSmith for the matching
root run by name, walk its `trace_id` to pull every LLM child span, sum prompt +
completion tokens, and multiply by the pinned price table below.

Why this design (recorded in plan 4.4 / B3):
- Cost = tokens × price; tokens are per-LLM-call which only the trace store has.
- Pinning prices in code (not fetching) keeps eval deterministic — re-scoring an old
  run gives the same number it gave originally, so iteration comparisons are honest.
- LangSmith outages or a missing API key MUST NOT fail the whole score stage. The caller
  catches and degrades gracefully (logs a warning, omits the `cost` block).
"""

import logging
import os
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


# OpenAI pricing for `gpt-5.4-mini` in USD per 1M tokens.
# Updated 2026-06-08. Re-check + bump on any vendor price change (eval results are versioned,
# so changing this table starts a new pricing era — old run reports stay correct).
@dataclass(frozen=True)
class ModelPrice:
    prompt_per_million: float
    completion_per_million: float


_PRICES: dict[str, ModelPrice] = {
    "gpt-5.4-mini": ModelPrice(prompt_per_million=0.25, completion_per_million=2.00),
}
_DEFAULT_MODEL = "gpt-5.4-mini"


def _price_for(model: str | None) -> ModelPrice:
    """Look up the price row; fall back to the default model (the runtime is single-model)."""
    if model and model in _PRICES:
        return _PRICES[model]
    return _PRICES[_DEFAULT_MODEL]


def _ensure_env_key() -> bool:
    """Mirror the LangSmith env-bridge from `app.observability.configure_langsmith` so the
    LangSmith Client can pick up the key when score.py runs standalone."""
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        return True
    return False


def fetch_cost_per_item(
    run_id: str, item_ids: list[str], project_name: str | None = None
) -> dict[str, float | None] | None:
    """Return `{item_id: cost_usd | None}` for every requested item. Returns `None` (the
    whole block) on LangSmith failure so the caller can omit the `cost` metric cleanly."""
    if not _ensure_env_key():
        logger.info("cost: no LANGSMITH_API_KEY set; skipping cost metric")
        return None

    project = project_name or settings.langsmith_project

    # Lazy import — only required when cost is actually computed.
    try:
        from langsmith import Client
    except ImportError as exc:
        logger.warning("cost: langsmith not importable (%s); skipping cost metric", exc)
        return None

    try:
        client = Client()
    except Exception as exc:  # broad: client init can fail for many auth reasons
        logger.warning(
            "cost: LangSmith client init failed (%s); skipping cost metric", exc
        )
        return None

    per_item: dict[str, float | None] = {}
    for item_id in item_ids:
        try:
            per_item[item_id] = _cost_for_one_item(client, project, run_id, item_id)
        except Exception as exc:
            logger.warning("cost: item %s lookup failed: %s", item_id, exc)
            per_item[item_id] = None
    return per_item


def _cost_for_one_item(client, project: str, run_id: str, item_id: str) -> float | None:
    """One item's cost in USD. Returns None if LangSmith has no data yet (ingest lag) or
    the run isn't tagged (e.g. an older run before B3.1 instrumentation)."""
    name = f"eval:{run_id}:{item_id}"
    # Get the unique root run by name. is_root=True so we don't pick up child spans that
    # happen to share the name (shouldn't happen with our naming, but defensive).
    roots = list(
        client.list_runs(
            project_name=project,
            filter=f'eq(name, "{name}")',
            is_root=True,
            limit=5,
        )
    )
    if not roots:
        return None
    root = roots[0]

    # Walk the trace for LLM child spans; iterator paginates internally.
    prompt_tokens = 0
    completion_tokens = 0
    for child in client.list_runs(
        project_name=project, trace_id=root.trace_id, run_type="llm"
    ):
        prompt_tokens += child.prompt_tokens or 0
        completion_tokens += child.completion_tokens or 0

    # Single-model runtime today; if multi-model ever lands, sum per-model and add here.
    price = _price_for(_DEFAULT_MODEL)
    cost_usd = (
        prompt_tokens * price.prompt_per_million / 1_000_000
        + completion_tokens * price.completion_per_million / 1_000_000
    )
    return cost_usd
