"""Planner node (PRD §6, FR-2).

A single LLM call, no tools: decompose the research question into 3–6 focused
sub-questions. Cheap/fast model is fine (the provider default, `gpt-5.4-mini`).

The PRD also asks the planner to note which sub-questions want live web data vs. corpus
retrieval. `ResearchState.plan` is `list[str]` (PRD §5.3), and each sub-question doubles as
a retrieval query downstream, so we keep the plan as clean sub-question strings and do *not*
fold the web-vs-corpus hint into them (it would pollute the query). The Researcher (2.3) has
both tools and works each sub-question regardless — the routing hint is advisory, not load-
bearing, so dropping it from persisted state is a deliberate v1 simplification.
"""

import json

from app.graph.state import ResearchState
from app.llm.provider import LLMProvider, get_default_provider

_MIN_SUBQUESTIONS = 3
_MAX_SUBQUESTIONS = 6
_MAX_OUTPUT_TOKENS = (
    2000  # per-agent token budget (PRD §12); a short JSON list of sub-qs
)

_SYSTEM_PROMPT = (
    "You are the planning agent of an autonomous research system. Decompose the user's "
    f"research question into {_MIN_SUBQUESTIONS} to {_MAX_SUBQUESTIONS} focused, "
    "non-overlapping sub-questions that together fully cover it. Each should be "
    "independently researchable. Respond with a JSON object of exactly this shape: "
    '{"sub_questions": ["...", "..."]} and nothing else.'
)


def _parse_sub_questions(text: str) -> list[str]:
    """Parse the model's JSON reply into a clamped list of sub-question strings."""
    cleaned = text.strip()
    if cleaned.startswith("```"):  # tolerate a ```json fence if the model adds one
        cleaned = cleaned.strip("`")
        cleaned = cleaned[4:] if cleaned.lower().startswith("json") else cleaned
    data = json.loads(cleaned)
    subs = [
        s.strip() for s in data["sub_questions"] if isinstance(s, str) and s.strip()
    ]
    return subs[
        :_MAX_SUBQUESTIONS
    ]  # enforce the PRD upper bound; prompt handles the lower


def plan_research(question: str, provider: LLMProvider | None = None) -> list[str]:
    """Return 3–6 sub-questions for `question`. `provider` is injectable for tests."""
    provider = provider or get_default_provider()
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    response = provider.complete(
        messages,
        text={"format": {"type": "json_object"}},
        max_output_tokens=_MAX_OUTPUT_TOKENS,
    )
    return _parse_sub_questions(response.output_text)


def planner_node(state: ResearchState) -> dict:
    """Graph node: question → `plan`."""
    return {"plan": plan_research(state["question"])}
