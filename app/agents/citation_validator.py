"""Citation validator — pure code, no LLM (PRD §6, FR-8).

Every inline ``[n]`` marker in the report must resolve to a real evidence item. Markers are
1-indexed references into the supplied ``evidence`` list: ``[n]`` is valid iff
``1 <= n <= len(evidence)``. Validity is positional, so it works uniformly for web
(``source_url``) and rag (``source_chunk_id``) evidence (PRD §8) — the source *type* is
irrelevant to whether the citation resolves.

Failure path (plan 2.6 — deterministic sentence-scoped strip): ``citations_valid`` records
whether the *original* report was clean. When a marker is unresolved we drop the **whole
sentence carrying it**, not just the ``[n]`` token — leaving the marker alone would keep an
unsupported claim presented as fact with no attribution, the exact hallucination this product
exists to prevent. Sentence-scoping fails safe (a claim that can't be tied to a real source
simply doesn't appear). A sentence is dropped if it contains *any* orphan marker, even if it
also carries a valid one.

After stripping we make the result self-consistent by construction: surviving markers are
**renumbered contiguously** and the **sources list is rebuilt** from the surviving evidence,
so a re-resolve of the cleaned report always passes with no orphan markers and no never-cited
sources — no second LLM pass, the graph stays linear (2.7).

This is a final safety net, not a quality stage — coverage/quality is the Critic loop's job
(2.4), which runs before the Writer. 2.3's evidence-as-source-of-truth keeps orphans rare.
"""

import logging
import re
from dataclasses import dataclass

from app.graph.state import ResearchState
from app.models.evidence import Evidence

logger = logging.getLogger(__name__)

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")  # naive but deterministic, body-only
_SOURCES_HEADER_RE = re.compile(
    r"^\s{0,3}#{1,6}\s*sources\b.*$", re.IGNORECASE | re.MULTILINE
)
# If more than this fraction of cited claims must be stripped, the report is too thin to trust.
_LOW_CONFIDENCE_THRESHOLD = 0.5
_SOURCES_HEADING = "## Sources"


@dataclass
class CitationReport:
    citations_valid: bool  # was the *original* report free of unresolved markers?
    unresolved: list[int]  # markers pointing past the evidence list (orphan citations)
    never_cited: list[int]  # evidence items (1-indexed) no marker references
    cleaned_report: str  # self-consistent report after stripping/renumbering
    stripped_fraction: float = 0.0  # dropped cited sentences / total cited sentences
    low_confidence: bool = False  # too much had to be stripped — surface, don't hide


def render_source_line(n: int, ev: Evidence) -> str:
    """Render one sources-list line. Shared contract: the Writer (2.5) must use this too,
    so the sources list looks identical whether or not the validator rebuilt it."""
    ref = ev.source_url if ev.retriever == "web" else f"chunk #{ev.source_chunk_id}"
    return f"[{n}] {ref}"


def validate_citations(report_md: str, evidence: list[Evidence]) -> CitationReport:
    n = len(evidence)
    cited = {int(m) for m in _MARKER_RE.findall(report_md)}
    unresolved = sorted(i for i in cited if not (1 <= i <= n))
    never_cited = sorted(i for i in range(1, n + 1) if i not in cited)

    if not unresolved:
        # Everything resolves — return the report untouched. `never_cited` is informational
        # (PRD §6 flags uncited sources, but that is not a gate failure — PRD §14).
        return CitationReport(
            citations_valid=True,
            unresolved=[],
            never_cited=never_cited,
            cleaned_report=report_md,
        )

    body, _ = _split_at_sources(
        report_md
    )  # original sources block is discarded + rebuilt
    cleaned_body, stripped_fraction = _strip_orphan_sentences(body, valid_max=n)
    cleaned_body, new_to_old = _renumber(cleaned_body)
    cleaned = _attach_sources(cleaned_body, new_to_old, evidence)

    low_confidence = stripped_fraction > _LOW_CONFIDENCE_THRESHOLD
    if low_confidence:
        logger.warning(
            "Citation validator stripped %.0f%% of cited claims; cleaned report may be thin.",
            stripped_fraction * 100,
        )

    return CitationReport(
        citations_valid=False,  # the *original* had orphan markers
        unresolved=unresolved,
        never_cited=[],  # the rebuilt list cites exactly the survivors
        cleaned_report=cleaned,
        stripped_fraction=stripped_fraction,
        low_confidence=low_confidence,
    )


def _split_at_sources(report_md: str) -> tuple[str, str]:
    """Split the report into (body, sources_block) at the first ``## Sources`` heading.
    Sentence-stripping must never touch the sources block (URLs contain dots)."""
    match = _SOURCES_HEADER_RE.search(report_md)
    if not match:
        return report_md, ""
    return report_md[: match.start()], report_md[match.start() :]


def _strip_orphan_sentences(body: str, valid_max: int) -> tuple[str, float]:
    """Drop every sentence carrying an orphan marker. Operate per line so Markdown structure
    (headers, list items, blank lines) is preserved; within a line, the *sentence* is the
    unit (a line may bundle several). Returns the cleaned body and the fraction of cited
    sentences that were dropped."""
    total_cited = 0
    dropped_cited = 0
    out_lines: list[str] = []

    for line in body.split("\n"):
        if (
            "[" not in line
        ):  # no possible marker — keep verbatim (headers, blanks, prose)
            out_lines.append(line)
            continue

        kept: list[str] = []
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            markers = [int(m) for m in _MARKER_RE.findall(sentence)]
            if markers:
                total_cited += 1
                if any(not (1 <= m <= valid_max) for m in markers):
                    dropped_cited += (
                        1  # fail safe: drop even if it also has a valid marker
                    )
                    continue
            kept.append(sentence)

        new_line = " ".join(kept).rstrip()
        if new_line:
            out_lines.append(new_line)
        # else: the line's content was fully stripped — drop the now-empty line entirely

    fraction = dropped_cited / total_cited if total_cited else 0.0
    return "\n".join(out_lines), fraction


def _renumber(body: str) -> tuple[str, dict[int, int]]:
    """Renumber the surviving (all valid) markers contiguously from 1, preserving order.
    Returns the rewritten body and the new→old marker map (for rebuilding the sources list)."""
    survivors = sorted({int(m) for m in _MARKER_RE.findall(body)})
    new_to_old = {new: old for new, old in enumerate(survivors, start=1)}
    old_to_new = {old: new for new, old in new_to_old.items()}
    renumbered = _MARKER_RE.sub(lambda m: f"[{old_to_new[int(m.group(1))]}]", body)
    return renumbered, new_to_old


def _attach_sources(
    body: str, new_to_old: dict[int, int], evidence: list[Evidence]
) -> str:
    """Append a freshly rendered sources list for the surviving, renumbered markers."""
    if not new_to_old:
        return body.rstrip()
    lines = [_SOURCES_HEADING]
    for new in sorted(new_to_old):
        lines.append(render_source_line(new, evidence[new_to_old[new] - 1]))
    return body.rstrip() + "\n\n" + "\n".join(lines)


def citation_validator_node(state: ResearchState) -> dict:
    """Graph node: validate `report_md` against `evidence`, return the cleaned report."""
    result = validate_citations(state["report_md"], state["evidence"])
    return {
        "report_md": result.cleaned_report,
        "citations_valid": result.citations_valid,
    }
