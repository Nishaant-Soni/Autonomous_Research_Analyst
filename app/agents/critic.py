"""Critic / fact-checker node (PRD §6, FR-6).

LLM-as-judge used *internally* (not just for offline eval): given the question, plan,
gathered evidence, and the draft, it checks that claims are supported, flags unsupported
claims and contradictions, and decides whether another research pass is warranted.

`needs_more_research` leans on **plan coverage** (per plan 2.4): since the loop-back gathers
*more* evidence, the most actionable signal is "does the accumulated evidence cover every
sub-question in the plan?". A sub-question with thin/no support is a gap and the clearest
trigger to loop back. The named `gaps` feed straight into the Researcher's next pass.
"""

import json

from app.graph.state import Critique, ResearchState
from app.llm.provider import LLMProvider, get_default_provider
from app.models.evidence import Evidence

_SYSTEM_PROMPT = (
    "You are the critic / fact-checker of an autonomous research system. You receive a "
    "research question, its planned sub-questions, the evidence gathered, and a draft of "
    "findings. Judge the draft strictly:\n"
    "- Verify each claim in the draft is supported by the listed evidence; flag unsupported "
    "claims and any contradictions between evidence items.\n"
    "- Assess COVERAGE: does the gathered evidence address every sub-question? A sub-question "
    "with thin or no supporting evidence is a gap.\n"
    "- Set needs_more_research=true when coverage gaps or unsupported key claims remain that "
    "another research pass could plausibly fix; otherwise false.\n"
    'Respond with a JSON object of exactly this shape and nothing else: {"groundedness": '
    '<number 0..1>, "needs_more_research": <boolean>, "gaps": ["..."], "contradictions": '
    '["..."]}. Make `gaps` name the specific sub-questions or angles still needing evidence '
    "(they directly focus the next research pass)."
)


def _build_user(
    question: str, plan: list[str], draft_findings: str, evidence: list[Evidence]
) -> str:
    subqs = "\n".join(f"- {q}" for q in plan) or "(none)"
    ev_lines = (
        "\n".join(
            f"[{i}] ({ev.retriever}) {ev.content}"
            for i, ev in enumerate(evidence, start=1)
        )
        or "(no evidence gathered)"
    )
    return (
        f"Research question: {question}\n\n"
        f"Planned sub-questions:\n{subqs}\n\n"
        f"Evidence gathered:\n{ev_lines}\n\n"
        f"Draft findings:\n{draft_findings or '(empty)'}"
    )


def _parse_critique(text: str) -> Critique:
    cleaned = text.strip()
    if cleaned.startswith("```"):  # tolerate a ```json fence if the model adds one
        cleaned = cleaned.strip("`")
        cleaned = cleaned[4:] if cleaned.lower().startswith("json") else cleaned
    data = json.loads(cleaned)
    groundedness = max(
        0.0, min(1.0, float(data.get("groundedness", 0.0)))
    )  # clamp to bound
    return Critique(
        groundedness=groundedness,
        needs_more_research=bool(data.get("needs_more_research", False)),
        gaps=[str(g) for g in data.get("gaps", [])],
        contradictions=[str(c) for c in data.get("contradictions", [])],
    )


def critique_findings(
    question: str,
    plan: list[str],
    draft_findings: str,
    evidence: list[Evidence],
    provider: LLMProvider | None = None,
) -> Critique:
    """Judge the draft against the evidence/plan. `provider` is injectable for tests."""
    provider = provider or get_default_provider()
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _build_user(question, plan, draft_findings, evidence),
        },
    ]
    response = provider.complete(
        messages,
        text={"format": {"type": "json_object"}},
        reasoning={"effort": "medium"},
    )
    return _parse_critique(response.output_text)


def critic_node(state: ResearchState) -> dict:
    """Graph node: produce a `Critique` for the current draft + evidence."""
    critique = critique_findings(
        state["question"], state["plan"], state["draft_findings"], state["evidence"]
    )
    return {"critique": critique}
