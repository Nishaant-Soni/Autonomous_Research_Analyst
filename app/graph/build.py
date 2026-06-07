"""Assemble the research StateGraph + conditional critic loop (PRD §5, FR-6).

Planner → Researcher → Critic → (conditional) → Writer → CitationValidator → END.

After the Critic, a conditional edge routes back to the Researcher while it still asks for
more research *and* the iteration cap hasn't been reached; otherwise it goes to the Writer.
The hard `max_iterations` cap guarantees termination (PRD §5.2).
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


def _route_after_critic(state: ResearchState) -> str:
    critique = state.get("critique")
    if (
        critique is not None
        and critique.needs_more_research
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
