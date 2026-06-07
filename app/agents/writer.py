"""Writer node (PRD §6, FR-7).

Synthesizes the gathered `evidence` (the canonical artifact per 2.3) into a structured
Markdown report. `draft_findings` is an advisory hint only — the report's facts come from
evidence, and the Writer is instructed to introduce none of its own.

Two numbering spaces (plan 2.5): the Writer cites by a **stable internal id** — it emits
`[ev:i]` for `evidence[i]` — and does *not* assign display numbers or write a sources list.
The Citation validator (2.6) owns the final contiguous `[1..k]` numbering and the `## Sources`
block in all paths. This keeps a single numbering authority and lets 2.6 renumber freely after
dropping any unsupported claims.
"""

from app.graph.state import ResearchState
from app.llm.provider import LLMProvider, get_default_provider
from app.models.evidence import Evidence

_SYSTEM_PROMPT = (
    "You are the report writer of an autonomous research system. Write a structured Markdown "
    "report with exactly these sections: '## Executive Summary', '## Findings' (organized into "
    "themed '### ' subsections), and '## Conclusion'.\n"
    "CITATIONS: cite the evidence supporting every factual claim using the exact token "
    "`[ev:i]`, where i is the index shown next to that evidence item. Cite multiple where "
    "relevant, e.g. `[ev:0][ev:3]`. Use only the supplied evidence — introduce NO facts that "
    "are not in it, and cite nothing that is not in the list.\n"
    "Do NOT write a sources, references, or citations list, and do NOT renumber — citation "
    "numbering and the sources section are added automatically downstream. End after the "
    "Conclusion."
)


def _format_evidence(evidence: list[Evidence]) -> str:
    if not evidence:
        return "(no evidence gathered)"
    return "\n".join(
        f"[ev:{i}] ({e.retriever}) {e.content}" for i, e in enumerate(evidence)
    )


def write_report(
    question: str,
    evidence: list[Evidence],
    draft_findings: str = "",
    provider: LLMProvider | None = None,
) -> str:
    """Produce the Markdown report (with `[ev:i]` citations). `provider` injectable for tests."""
    provider = provider or get_default_provider()
    hint = (
        f"\nDraft notes (for structure/ideas only, not authoritative):\n{draft_findings}\n"
        if draft_findings
        else ""
    )
    user = (
        f"Research question: {question}\n"
        f"{hint}\n"
        f"Evidence (cite by these exact [ev:i] tokens):\n{_format_evidence(evidence)}"
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    return provider.complete(messages, reasoning={"effort": "medium"}).output_text


def writer_node(state: ResearchState) -> dict:
    """Graph node: synthesize the report from evidence (+ advisory draft)."""
    report = write_report(state["question"], state["evidence"], state["draft_findings"])
    return {"report_md": report}
