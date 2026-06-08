"""Tests for the cost metric's graceful-degrade paths (plan 4.4 B3.3).

The live LangSmith query is covered by the live verify step (DB+key required); these
unit tests cover what happens when LangSmith is unavailable, which is the more important
property because the score CLI must never crash on a missing/expired key.
"""

import pytest

from eval.metrics import cost as cost_mod


def test_returns_none_when_no_api_key(monkeypatch):
    # Settings has an empty key -> the function should log and return None (whole block).
    monkeypatch.setattr(cost_mod.settings, "langsmith_api_key", "")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    out = cost_mod.fetch_cost_per_item("run-x", ["a", "b"])

    assert out is None


def test_returns_none_when_client_init_fails(monkeypatch):
    monkeypatch.setattr(cost_mod.settings, "langsmith_api_key", "k")

    class _BoomClient:
        def __init__(self, *a, **kw):
            raise RuntimeError("auth blew up")

    monkeypatch.setattr("langsmith.Client", _BoomClient)

    out = cost_mod.fetch_cost_per_item("run-x", ["a"])

    assert out is None


def test_per_item_lookup_failure_yields_none_not_crash(monkeypatch):
    # If individual item lookups blow up, the function returns per_item with None for the
    # broken ones — not None for the whole block. Lets one bad item not erase the rest.
    monkeypatch.setattr(cost_mod.settings, "langsmith_api_key", "k")

    class _Client:
        def __init__(self, *a, **kw): ...
        def list_runs(self, **kw):
            raise RuntimeError("transient")

    monkeypatch.setattr("langsmith.Client", _Client)

    out = cost_mod.fetch_cost_per_item("run-x", ["a", "b"])

    assert out == {"a": None, "b": None}


def test_price_lookup_falls_back_to_default():
    # Unknown / None model maps to the runtime default (single-model project).
    p_unknown = cost_mod._price_for("not-a-real-model")
    p_default = cost_mod._price_for(None)
    assert p_unknown == p_default
    assert p_default.prompt_per_million > 0


def test_cost_computation_via_stub_client(monkeypatch):
    """Wire happy-path math: 1000 prompt + 500 completion tokens at known prices."""
    monkeypatch.setattr(cost_mod.settings, "langsmith_api_key", "k")

    # Set a price we control for deterministic math.
    from eval.metrics.cost import ModelPrice

    monkeypatch.setitem(
        cost_mod._PRICES,
        "gpt-5.4-mini",
        ModelPrice(prompt_per_million=1.0, completion_per_million=2.0),
    )

    class _Root:
        trace_id = "trace-1"
        parent_run_id = None
        name = "eval:run-x:a"

    class _LLMChild:
        run_type = "llm"
        prompt_tokens = 1000
        completion_tokens = 500

    class _Client:
        def __init__(self, *a, **kw): ...
        def list_runs(self, **kw):
            if kw.get("filter", "").startswith("eq(name,"):
                return iter([_Root()])
            if kw.get("trace_id") == "trace-1":
                return iter([_LLMChild(), _LLMChild()])  # two LLM calls
            return iter([])

    monkeypatch.setattr("langsmith.Client", _Client)

    out = cost_mod.fetch_cost_per_item("run-x", ["a"])

    # 2 calls × (1000 * $1/M + 500 * $2/M) = 2 × (0.001 + 0.001) = 0.004
    assert out is not None
    assert out["a"] == pytest.approx(0.004)
