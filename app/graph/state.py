"""The shared state contract that flows through every agent node (PRD §5.3).

`ResearchState` is the single typed object the LangGraph nodes read and update. The
`Evidence` payload is reused from Phase 1 (`app.models.evidence`) — it is the canonical
artifact across the whole graph (Researcher appends to it; Writer synthesizes from it;
the citation validator checks against it), so it must be the *same* type the retrievers
already emit, not a second definition.
"""

import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from app.models.evidence import Evidence


class Critique(BaseModel):
    """The Critic's verdict on a research pass (PRD §6).

    `needs_more_research` drives the bounded critic loop in 2.7: when it is True and the
    iteration cap has not been hit, control routes back to the Researcher to fill the
    named gaps; otherwise the graph proceeds to the Writer.
    """

    groundedness: float = Field(
        ge=0.0, le=1.0
    )  # fraction of claims supported by evidence
    needs_more_research: bool
    gaps: list[str] = []  # sub-questions / angles still lacking supporting evidence
    contradictions: list[str] = []


class ResearchState(TypedDict):
    """Shared state for the research graph (PRD §5.3, plus the validator's output signal).

    `evidence` accumulates across the critic loop, so it carries an additive reducer:
    LangGraph channels are last-value-wins by default, which would drop earlier evidence
    when the Researcher returns again on a loop-back. `operator.add` concatenates each
    node's returned list onto the existing one instead. The other fields are last-value-
    wins, which is what we want (e.g. the latest `critique`, the current `iteration`).

    `low_confidence` / `stripped_fraction` extend §5.3: the citation validator (2.6) sets
    them and the runner (3.2) reads them off final state to persist onto the session —
    they are the node's only channel to the runner (a node must not touch the DB itself).
    """

    session_id: str
    question: str
    plan: list[str]
    evidence: Annotated[list[Evidence], operator.add]
    draft_findings: str
    critique: Critique | None
    iteration: int
    max_iterations: int
    report_md: str
    citations_valid: bool
    low_confidence: bool
    stripped_fraction: float
