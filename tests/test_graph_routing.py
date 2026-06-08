"""Tests for the tightened critic loop-back gate (plan 4.7 follow-up, C2-tuned).

The C2 A/B showed the original `needs_more_research` gate was over-eager. The new gate
is `groundedness < 0.70 AND len(gaps) >= 2 AND iteration < max_iterations` — both
quality signals must agree before paying the cost of another research pass.
"""

from app.graph.build import _route_after_critic
from app.graph.state import Critique


def _state(
    critique: Critique | None, iteration: int = 0, max_iterations: int = 2
) -> dict:
    return {
        "critique": critique,
        "iteration": iteration,
        "max_iterations": max_iterations,
    }


def _critique(groundedness: float, gaps: list[str], needs: bool = False) -> Critique:
    """needs_more_research is intentionally NOT what the gate reads anymore — its value
    here should not affect routing."""
    return Critique(
        groundedness=groundedness,
        needs_more_research=needs,
        gaps=gaps,
        contradictions=[],
    )


def test_high_groundedness_short_circuits_to_writer_even_with_many_gaps():
    # If the draft is already well-supported, gaps in the plan don't justify burning another
    # research pass — the writer can produce a good report from what we have.
    s = _state(_critique(groundedness=0.95, gaps=["a", "b", "c"]))
    assert _route_after_critic(s) == "writer"


def test_single_gap_alone_does_not_trigger_loop():
    # One named gap on a low-quality draft is below the noise floor of the gate. C2 showed
    # single-gap items were the ones the old (over-eager) gate kept firing on.
    s = _state(_critique(groundedness=0.40, gaps=["only one"]))
    assert _route_after_critic(s) == "writer"


def test_low_groundedness_AND_multi_gap_triggers_loop():
    # Both signals agree → loop. This is the case the C2 win-items satisfied
    # (`rag-vs-finetuning` had thin coverage + low groundedness on first pass).
    s = _state(_critique(groundedness=0.50, gaps=["x", "y"]))
    assert _route_after_critic(s) == "researcher"


def test_iteration_cap_overrides_loop_even_when_signals_agree():
    s = _state(
        _critique(groundedness=0.50, gaps=["x", "y"]), iteration=2, max_iterations=2
    )
    assert _route_after_critic(s) == "writer"


def test_max_iterations_zero_disables_loop_entirely():
    # The "Critic loop OFF" mode used in the C2 A/B is preserved.
    s = _state(_critique(groundedness=0.10, gaps=["x", "y", "z"]), max_iterations=0)
    assert _route_after_critic(s) == "writer"


def test_no_critique_routes_safely_to_writer():
    assert _route_after_critic(_state(None)) == "writer"


def test_legacy_needs_more_research_flag_is_no_longer_load_bearing():
    # Critic with needs_more_research=True but a high groundedness should NOT loop —
    # confirms the gate reads the new signals, not the old boolean.
    s = _state(_critique(groundedness=0.90, gaps=["a", "b", "c"], needs=True))
    assert _route_after_critic(s) == "writer"
