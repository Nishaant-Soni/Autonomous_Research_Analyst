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
        for i in range(n)
    ]


def test_clean_report_gets_contiguous_numbering_and_sources():
    # Writer emitted [ev:0] and [ev:1]; both resolve.
    report = "Paris is the capital of France [ev:0]. It sits on the Seine [ev:1]."
    result = validate_citations(report, _web_evidence(2))

    assert result.citations_valid is True
    assert result.unresolved == []
    assert (
        "[ev:" not in result.cleaned_report
    )  # internal ids rewritten to display numbers
    assert "[1]" in result.cleaned_report and "[2]" in result.cleaned_report
    assert (
        "## Sources\n[1] https://e0.example\n[2] https://e1.example"
        in result.cleaned_report
    )


def test_sparse_references_renumber_contiguously():
    # Writer referenced ev:0 then ev:2 (skipping ev:1) -> display [1], [2]; sources from 0 and 2.
    report = "Claim A [ev:0]. Claim B [ev:2]."
    result = validate_citations(report, _web_evidence(3))

    assert result.citations_valid is True
    assert "Claim A [1]" in result.cleaned_report
    assert "Claim B [2]" in result.cleaned_report
    assert "[1] https://e0.example" in result.cleaned_report
    assert "[2] https://e2.example" in result.cleaned_report


def test_first_appearance_order_drives_display_numbers():
    report = "First mentioned [ev:2]. Then [ev:0]."
    result = validate_citations(report, _web_evidence(3))
    assert "First mentioned [1]" in result.cleaned_report
    assert "Then [2]" in result.cleaned_report
    assert (
        "[1] https://e2.example" in result.cleaned_report
    )  # ev:2 appeared first -> display 1


def test_unresolved_reference_drops_its_sentence_and_report_is_self_consistent():
    report = (
        "Grounded claim [ev:0]. Fabricated claim [ev:9]. Another grounded one [ev:1]."
    )
    result = validate_citations(report, _web_evidence(2))

    assert result.citations_valid is False
    assert result.unresolved == [9]
    assert "Fabricated claim" not in result.cleaned_report
    assert "[ev:" not in result.cleaned_report
    # the cleaned report re-resolves cleanly (no unresolved refs remain)
    assert (
        validate_citations(result.cleaned_report, _web_evidence(2)).citations_valid
        is True
    )


def test_sentence_with_both_valid_and_orphan_ref_is_dropped_then_renumbered():
    # First sentence has valid [ev:0] AND orphan [ev:9] -> dropped wholesale; surviving [ev:1]
    # renumbers to [1], its source rebuilt from the original 2nd evidence item.
    report = "Mixed claim [ev:0] and [ev:9]. Standalone claim [ev:1]."
    result = validate_citations(report, _web_evidence(2))

    assert result.citations_valid is False
    assert "Standalone claim [1]." in result.cleaned_report
    assert "[1] https://e1.example" in result.cleaned_report


def test_high_orphan_fraction_sets_low_confidence(caplog):
    report = "A [ev:0]. B [ev:5]. C [ev:6]."  # 2 of 3 cited sentences orphaned (>50%)
    with caplog.at_level(logging.WARNING):
        result = validate_citations(report, _web_evidence(1))
    assert result.citations_valid is False
    assert result.stripped_fraction > 0.5
    assert result.low_confidence is True
    assert any("stripped" in r.message for r in caplog.records)


def test_abbreviation_period_does_not_split_sentence_mid_abbreviation():
    # Without abbreviation protection, "The U.S. has growth [ev:9]." would split into
    # ["The U.S.", "has growth [ev:9]."] — only the orphan-carrying half would be dropped,
    # leaving the fragment "The U.S." in the report. The protected splitter keeps the
    # whole real sentence together, so the strip drops it wholesale (fail-safe).
    report = "The U.S. has rapid AI growth [ev:9]. Real claim [ev:0]."
    result = validate_citations(report, _web_evidence(1))

    assert result.citations_valid is False
    assert "U.S." not in result.cleaned_report  # the fragment is gone, not retained
    assert "rapid AI growth" not in result.cleaned_report
    assert "Real claim [1]." in result.cleaned_report
    assert "[1] https://e0.example" in result.cleaned_report


def test_abbreviation_protection_handles_multiple_forms_in_one_line():
    # e.g. (Latin) + Dr. (title) + Inc. (business) all on one line; the unresolved ref is
    # the only thing that causes a drop, and the abbreviations don't fragment the sentence.
    report = (
        "Dr. Smith of Acme Inc. studied LLMs, e.g. the 7B class [ev:0]. Bad [ev:9]."
    )
    result = validate_citations(report, _web_evidence(1))

    assert result.citations_valid is False
    assert (
        "Dr. Smith of Acme Inc. studied LLMs, e.g. the 7B class [1]."
        in result.cleaned_report
    )
    assert "Bad" not in result.cleaned_report


def test_render_source_line_for_web_and_rag():
    web = Evidence(content="x", retriever="web", source_url="https://a.example")
    rag = Evidence(content="y", retriever="rag", source_chunk_id=42)
    assert render_source_line(1, web) == "[1] https://a.example"
    assert render_source_line(3, rag) == "[3] chunk #42"


def test_node_writes_all_state_signals():
    state = {"report_md": "Good [ev:0]. Bad [ev:7].", "evidence": _web_evidence(1)}
    update = citation_validator_node(state)  # type: ignore[arg-type]
    assert set(update) == {
        "report_md",
        "citations_valid",
        "low_confidence",
        "stripped_fraction",
    }
    assert update["citations_valid"] is False
    assert "Bad" not in update["report_md"]
    assert "[1]" in update["report_md"]
