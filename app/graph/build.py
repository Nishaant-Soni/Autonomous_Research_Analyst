"""Assemble the research StateGraph + conditional critic loop (PRD §5, FR-6).

Planner → Researcher → Critic → (conditional) → Writer → CitationValidator → END.

After the Critic, a conditional edge routes back to the Researcher only when the draft's
groundedness is low AND the critic names ≥2 coverage gaps AND the iteration cap hasn't
been reached; otherwise control goes to the Writer. The two-signal AND was tuned in C2 —
see `_route_after_critic` below. The hard `max_iterations` cap guarantees termination
(PRD §5.2).
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.citation_validator import citation_validator_node
from app.agents.critic import critic_node
from app.agents.planner import planner_node
from app.agents.researcher import researcher_node
from app.agents.writer import writer_node
from app.graph.state import ResearchState


def _researcher_with_iteration(state: ResearchState) -> dict:
    """Run the Researcher and bump `iteration`.

    The increment lives in a node, not the conditional edge: LangGraph edge functions only
    choose the next node, they can't mutate state (plan 2.7). Bumping on each Researcher entry
    is what lets the critic loop reach its cap and terminate.
    """
    update = researcher_node(state)
    update["iteration"] = state["iteration"] + 1
    return update


# Loop-back gate (C2-tuned; see docs/iteration_28.md). The original gate
# (`critique.needs_more_research`) was over-eager — the C2 A/B showed it fires on items
# where one extra research pass dilutes focus more than it fills gaps (`rag-components`
# +10pp, `prompt-injection` +9pp hallucination). Tightened to require BOTH signals to
# agree: a low-groundedness draft AND multiple named coverage gaps. The critic node still
# runs every pass (its critique is preserved for observability); only the edge back to
# the researcher is gated.
_LOOPBACK_GROUNDEDNESS_MAX = 0.70  # loop only when the draft is meaningfully shaky
_LOOPBACK_GAPS_MIN = 2  # AND the critic names at least two uncovered angles


def _route_after_critic(state: ResearchState) -> str:
    critique = state.get("critique")
    if (
        critique is not None
        and critique.groundedness < _LOOPBACK_GROUNDEDNESS_MAX
        and len(critique.gaps) >= _LOOPBACK_GAPS_MIN
        and state["iteration"] < state["max_iterations"]
    ):
        return "researcher"
    return "writer"


def build_graph(checkpointer: Any = None):
    """Compile the research graph. Pass a checkpointer (2.8) to persist/resume runs."""
    builder = StateGraph(ResearchState)
    builder.add_node("planner", planner_node)
    builder.add_node("researcher", _researcher_with_iteration)
    builder.add_node("critic", critic_node)
    builder.add_node("writer", writer_node)
    builder.add_node("validator", citation_validator_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "critic")
    builder.add_conditional_edges(
        "critic", _route_after_critic, {"researcher": "researcher", "writer": "writer"}
    )
    builder.add_edge("writer", "validator")
    builder.add_edge("validator", END)

    return builder.compile(checkpointer=checkpointer)
