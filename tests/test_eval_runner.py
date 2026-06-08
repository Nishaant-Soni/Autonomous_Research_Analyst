"""Tests for eval.runner artifact writing (plan 4.5 A2, no DB/network)."""

import json
from pathlib import Path

import pytest

from app.models.evidence import Evidence
from eval.dataset import GoldenItem
from eval.runner import persist_artifacts, persist_error


def _item() -> GoldenItem:
    return GoldenItem(
        id="x",
        question="q?",
        target="web",
        key_facts=["one.", "two."],
        acceptable_domains=["arxiv.org"],
    )


def _final(evidence: list[Evidence]) -> dict:
    return {
        "report_md": "# Report\n\nbody [1]\n\n[1] https://x",
        "evidence": evidence,
        "citations_valid": True,
        "low_confidence": False,
        "stripped_fraction": 0.0,
    }


def test_persist_artifacts_writes_report_evidence_result(tmp_path: Path):
    evidence = [
        Evidence(content="alpha", source_url="https://a", retriever="web", claim="c1"),
        Evidence(content="beta", source_chunk_id=42, retriever="rag", claim="c2"),
    ]
    persist_artifacts(
        tmp_path, _item(), {"final": _final(evidence), "latency_seconds": 1.23}
    )

    assert (tmp_path / "report.md").read_text().startswith("# Report")

    ev_lines = (tmp_path / "evidence.jsonl").read_text().strip().splitlines()
    parsed = [json.loads(line) for line in ev_lines]
    assert len(parsed) == 2
    assert parsed[0]["content"] == "alpha" and parsed[0]["source_url"] == "https://a"
    assert parsed[1]["source_chunk_id"] == 42 and parsed[1]["retriever"] == "rag"

    result = json.loads((tmp_path / "result.json").read_text())
    assert result["id"] == "x"
    assert result["reference"] == "one. two."
    assert result["citations_valid"] is True
    assert result["latency_seconds"] == pytest.approx(1.23)
    assert result["evidence_count"] == 2


def test_persist_error_writes_error_and_minimal_result(tmp_path: Path):
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        persist_error(tmp_path, _item(), exc)

    err = (tmp_path / "error.txt").read_text()
    assert "RuntimeError: boom" in err
    assert "Traceback" in err  # full traceback for debugging

    result = json.loads((tmp_path / "result.json").read_text())
    assert result["id"] == "x"
    assert result["failed"] is True
    assert "RuntimeError: boom" in result["error"]
    # The failed-item shape must NOT carry success-only keys (Score stage filters on `failed`).
    assert "citations_valid" not in result
    assert "evidence_count" not in result
