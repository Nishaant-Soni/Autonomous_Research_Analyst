"""The shared state contract that flows through every agent node (PRD §5.3).

`ResearchState` is the single typed object the LangGraph nodes read and update. The
`Evidence` payload is reused from Phase 1 (`app.models.evidence`) — it is the canonical
artifact across the whole graph (Researcher appends to it; Writer synthesizes from it;
the citation validator checks against it), so it must be the *same* type the retrievers
already emit, not a second definition.
"""

from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from app.models.evidence import Evidence


def _source_key(ev: Evidence) -> tuple[str, object]:
    """Identity of an evidence item's *source* (not its snippet): same web URL or same rag
    chunk id is the same source, even if the retrieved text differs slightly."""
    return (
        ev.retriever,
        ev.source_url if ev.retriever == "web" else ev.source_chunk_id,
    )


def _merge_evidence(existing: list[Evidence], new: list[Evidence]) -> list[Evidence]:
    """Reducer for the `evidence` channel: append only sources not already present.

    Replaces a plain `operator.add` so the same source can't accumulate twice — whether the
    Researcher repeats a query within one pass or re-fetches a source on a critic loop-back.
    Keeps the first occurrence and preserves order; a duplicate source would otherwise show up
    as two identical lines in the final `## Sources` list (PRD §6/§8).
    """
    merged = list(existing)
    seen = {_source_key(e) for e in merged}
    for ev in new:
        key = _source_key(ev)
        if key not in seen:
            seen.add(key)
            merged.append(ev)
    return merged


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

    `evidence` accumulates across the critic loop, so it carries a custom reducer
    (`_merge_evidence`): LangGraph channels are last-value-wins by default, which would drop
    earlier evidence when the Researcher returns again on a loop-back. The reducer appends each
    node's returned items, skipping any whose *source* is already present (dedup). The other
    fields are last-value-wins, which is what we want (e.g. the latest `critique`, `iteration`).

    `low_confidence` / `stripped_fraction` extend §5.3: the citation validator (2.6) sets
    them and the runner (3.2) reads them off final state to persist onto the session —
    they are the node's only channel to the runner (a node must not touch the DB itself).
    """

    session_id: str
    question: str
    plan: list[str]
    evidence: Annotated[list[Evidence], _merge_evidence]
    draft_findings: str
    critique: Critique | None
    iteration: int
    max_iterations: int
    report_md: str
    citations_valid: bool
    low_confidence: bool
    stripped_fraction: float
    user_id: (
        int | None
    )  # owning user; None for eval/anonymous runs (no RAG filter applied)
    # Explicit opt-in to cross-user RAG (eval/offline only). Fail-closed: with user_id=None
    # this must be True for rag_retrieve to run at all (see app/retrieval/rag.py). The
    # per-user API path leaves it False so a missing user_id can't silently read all corpora.
    allow_all_users: bool
