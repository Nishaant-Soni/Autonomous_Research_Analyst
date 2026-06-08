"""Deterministic metrics (plan 4.3 / B1).

Reads cached per-item `result.json` files produced by the Run stage; computes purely
from the citation validator's output — no LLM judge, no embeddings, no retrieval.

Currently:
- **Citation accuracy** = `1 - stripped_fraction`, i.e. the fraction of the writer's
  cited claims whose `[n]` markers pointed to real evidence (before the validator
  stripped the orphans). `stripped_fraction` is captured per run by the citation
  validator (`app/agents/citation_validator.py`) and persisted in `result.json`.

Hallucination rate (= `1 - faithfulness`) lives in this module's sibling once B2 lands
the Ragas pass — it is the derived headline of a Ragas metric, not a deterministic one.
"""

from statistics import mean


def citation_accuracy_per_item(result_json: dict) -> float | None:
    """Per-item citation accuracy. Returns `None` for items that the Run stage marked as
    `failed:true` so the aggregate can skip them honestly rather than fabricating a score."""
    if result_json.get("failed"):
        return None
    return 1.0 - result_json["stripped_fraction"]


def citation_accuracy_aggregate(per_item: dict[str, float | None]) -> dict:
    """Aggregate over successful items only. Failed items are counted separately so the
    headline is "X% over N scored, M failed" rather than a number that silently drops data."""
    scored = {k: v for k, v in per_item.items() if v is not None}
    if not scored:
        return {
            "n_scored": 0,
            "n_failed": len(per_item),
            "mean": None,
            "min": None,
            "max": None,
        }
    values = list(scored.values())
    return {
        "n_scored": len(scored),
        "n_failed": len(per_item) - len(scored),
        "mean": mean(values),
        "min": min(values),
        "max": max(values),
    }
