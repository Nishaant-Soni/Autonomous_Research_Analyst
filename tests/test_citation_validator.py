import logging

from app.agents.citation_validator import (
    citation_validator_node,
    render_source_line,
    validate_citations,
)
from app.models.evidence import Evidence


def _web_evidence(n: int) -> list[Evidence]:
    return [
        Evidence(
            content=f"fact {i}", retriever="web", source_url=f"https://e{i}.example"
        )
        for i in range(1, n + 1)
    ]


def test_all_markers_resolve_keeps_report_unchanged():
    report = (
        "Paris is the capital of France [1]. It sits on the Seine [2].\n\n"
        "## Sources\n[1] https://e1.example\n[2] https://e2.example"
    )
    result = validate_citations(report, _web_evidence(2))
    assert result.citations_valid is True
    assert result.unresolved == []
    assert result.cleaned_report == report  # untouched when everything resolves
    assert result.low_confidence is False


def test_orphan_sentence_is_dropped_and_report_is_self_consistent():
    report = "Grounded claim [1]. Fabricated claim [9]. Another grounded one [2]."
    result = validate_citations(report, _web_evidence(2))

    assert result.citations_valid is False
    assert result.unresolved == [9]
    # the whole "[9]" sentence is gone, not just the marker token
    assert "Fabricated claim" not in result.cleaned_report
    assert "[9]" not in result.cleaned_report
    # a rebuilt sources list is present and the cleaned report re-resolves cleanly
    assert "## Sources" in result.cleaned_report
    revalidated = validate_citations(result.cleaned_report, _web_evidence(2))
    assert revalidated.citations_valid is True
    assert revalidated.never_cited == []


def test_dropping_a_valid_marker_triggers_contiguous_renumbering():
    # First sentence carries BOTH [1] (valid) and [9] (orphan) -> dropped wholesale,
    # so the surviving [2] must be renumbered down to [1] and its source rebuilt.
    report = "Claim with both [1] and [9] markers. Standalone claim [2]."
    result = validate_citations(report, _web_evidence(2))

    assert result.citations_valid is False
    assert "[2]" not in result.cleaned_report  # renumbered
    assert "Standalone claim [1]." in result.cleaned_report
    # the rebuilt source for new [1] points at the *original* second evidence item
    assert "[1] https://e2.example" in result.cleaned_report


def test_high_orphan_fraction_sets_low_confidence(caplog):
    report = "A [1]. B [5]. C [6]."  # 2 of 3 cited claims orphaned (>50%)
    with caplog.at_level(logging.WARNING):
        result = validate_citations(report, _web_evidence(1))
    assert result.citations_valid is False
    assert result.stripped_fraction > 0.5
    assert result.low_confidence is True
    assert any("stripped" in r.message for r in caplog.records)


def test_never_cited_source_is_flagged_when_otherwise_clean():
    report = "Only the first source is used here [1]."
    result = validate_citations(report, _web_evidence(3))
    assert result.citations_valid is True  # no unresolved markers
    assert result.never_cited == [2, 3]


def test_render_source_line_for_web_and_rag():
    web = Evidence(content="x", retriever="web", source_url="https://a.example")
    rag = Evidence(content="y", retriever="rag", source_chunk_id=42)
    assert render_source_line(1, web) == "[1] https://a.example"
    assert render_source_line(3, rag) == "[3] chunk #42"


def test_node_returns_cleaned_report_and_flag():
    state = {"report_md": "Good [1]. Bad [7].", "evidence": _web_evidence(1)}
    update = citation_validator_node(state)  # type: ignore[arg-type]
    assert update["citations_valid"] is False
    assert "Bad" not in update["report_md"]
    assert "[7]" not in update["report_md"]
    assert "[1]" in update["report_md"]
