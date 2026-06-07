"""Citation validator node — pure code, no LLM (PRD §6, FR-8).

The Writer (2.5) cites evidence by a stable internal id, `[ev:i]` → `evidence[i]`. This node
is the single numbering authority: in **every** path it collects the referenced evidence items,
assigns them contiguous display numbers `[1..k]` (first-appearance order), rewrites the inline
markers, and renders a matching `## Sources` block via `render_source_line`. Validity is
positional, so web (`source_url`) and rag (`source_chunk_id`) evidence are handled uniformly
(PRD §8).

Failure path (plan 2.6 — deterministic sentence-scoped strip): if an `[ev:i]` reference does
not resolve to a real evidence item, the **whole sentence carrying it** is dropped — not just
the token. Leaving the token would keep an unsupported claim presented as fact with no source,
the exact hallucination this product exists to prevent; sentence-scoping fails safe. A sentence
is dropped if it contains *any* unresolved reference, even alongside a valid one.

Self-consistent by construction: we strip orphan sentences first, *then* number + render over
what remains — so the cleaned report always has contiguous `[1..k]` markers, a matching sources
list, and re-resolves cleanly, with no second LLM pass (the graph stays linear, 2.7).
`citations_valid` records whether the *original* report was free of unresolved references.
"""

import logging
import re
from dataclasses import dataclass, field

from app.graph.state import ResearchState
from app.models.evidence import Evidence

logger = logging.getLogger(__name__)

_REF_RE = re.compile(r"\[ev:(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")  # naive but deterministic, body-only
_SOURCES_HEADER_RE = re.compile(
    r"^\s{0,3}#{1,6}\s*sources\b.*$", re.IGNORECASE | re.MULTILINE
)
# If more than this fraction of cited claims must be stripped, the report is too thin to trust.
_LOW_CONFIDENCE_THRESHOLD = 0.5
_SOURCES_HEADING = "## Sources"


@dataclass
class CitationReport:
    citations_valid: (
        bool  # was the *original* report free of unresolved `[ev:i]` references?
    )
    cleaned_report: (
        str  # self-consistent report: contiguous `[1..k]` markers + `## Sources`
    )
    unresolved: list[int] = field(
        default_factory=list
    )  # ev indices that pointed past evidence
    stripped_fraction: float = 0.0  # dropped cited sentences / total cited sentences
    low_confidence: bool = False  # too much had to be stripped — surface, don't hide


def render_source_line(n: int, ev: Evidence) -> str:
    """Render one sources-list line for display number `n`."""
    ref = ev.source_url if ev.retriever == "web" else f"chunk #{ev.source_chunk_id}"
    return f"[{n}] {ref}"


def validate_citations(report_md: str, evidence: list[Evidence]) -> CitationReport:
    n = len(evidence)
    refs = [int(m) for m in _REF_RE.findall(report_md)]
    unresolved = sorted({i for i in refs if not (0 <= i < n)})

    body, _ = _split_at_sources(
        report_md
    )  # we own the sources block; drop any the model added

    stripped_fraction = 0.0
    if unresolved:
        body, stripped_fraction = _strip_orphan_sentences(body, valid_max=n)

    cleaned = _renumber_and_attach_sources(body, evidence)

    low_confidence = stripped_fraction > _LOW_CONFIDENCE_THRESHOLD
    if low_confidence:
        logger.warning(
            "Citation validator stripped %.0f%% of cited claims; cleaned report may be thin.",
            stripped_fraction * 100,
        )

    return CitationReport(
        citations_valid=not unresolved,
        cleaned_report=cleaned,
        unresolved=unresolved,
        stripped_fraction=stripped_fraction,
        low_confidence=low_confidence,
    )


def _split_at_sources(report_md: str) -> tuple[str, str]:
    """Split off any pre-existing ``## Sources`` block (we rebuild it). Also keeps the naive
    sentence splitter away from URL dots in the sources list."""
    match = _SOURCES_HEADER_RE.search(report_md)
    if not match:
        return report_md, ""
    return report_md[: match.start()], report_md[match.start() :]


def _strip_orphan_sentences(body: str, valid_max: int) -> tuple[str, float]:
    """Drop every sentence carrying an unresolved `[ev:i]` reference. Operate per line so
    Markdown structure (headers, list items, blank lines) is preserved; within a line the
    *sentence* is the unit. Returns the cleaned body and the fraction of cited sentences dropped.
    """
    total_cited = 0
    dropped_cited = 0
    out_lines: list[str] = []

    for line in body.split("\n"):
        if "[ev:" not in line:  # no reference possible — keep verbatim
            out_lines.append(line)
            continue

        kept: list[str] = []
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            refs = [int(m) for m in _REF_RE.findall(sentence)]
            if refs:
                total_cited += 1
                if any(not (0 <= i < valid_max) for i in refs):
                    dropped_cited += (
                        1  # fail safe: drop even if it also carries a valid ref
                    )
                    continue
            kept.append(sentence)

        new_line = " ".join(kept).rstrip()
        if new_line:
            out_lines.append(new_line)
        # else: the line's content was fully stripped — drop the now-empty line

    fraction = dropped_cited / total_cited if total_cited else 0.0
    return "\n".join(out_lines), fraction


def _renumber_and_attach_sources(body: str, evidence: list[Evidence]) -> str:
    """Map referenced `[ev:i]` (all valid here) to contiguous `[1..k]` in first-appearance
    order, rewrite the markers, and append a matching ``## Sources`` block."""
    order: list[int] = []
    for match in _REF_RE.finditer(body):
        ev_index = int(match.group(1))
        if ev_index not in order:
            order.append(ev_index)
    if not order:
        return body.rstrip()

    display = {ev_index: n for n, ev_index in enumerate(order, start=1)}
    renumbered = _REF_RE.sub(lambda m: f"[{display[int(m.group(1))]}]", body)

    source_lines = [_SOURCES_HEADING]
    for n, ev_index in enumerate(order, start=1):
        source_lines.append(render_source_line(n, evidence[ev_index]))
    return renumbered.rstrip() + "\n\n" + "\n".join(source_lines)


def citation_validator_node(state: ResearchState) -> dict:
    """Graph node: validate/clean `report_md` and surface the validator's signals on state."""
    result = validate_citations(state["report_md"], state["evidence"])
    return {
        "report_md": result.cleaned_report,
        "citations_valid": result.citations_valid,
        "low_confidence": result.low_confidence,
        "stripped_fraction": result.stripped_fraction,
    }
