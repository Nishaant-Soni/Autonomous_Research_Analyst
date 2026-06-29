import os
import re
from types import SimpleNamespace

import pytest

from app.agents import writer
from app.agents.citation_validator import validate_citations
from app.models.evidence import Evidence


class _RecordingProvider:
    def __init__(self, output_text):
        self._output_text = output_text
        self.messages = None

    def complete(self, messages, tools=None, **kwargs):
        self.messages = messages
        return SimpleNamespace(output_text=self._output_text)


def _evidence():
    return [
        Evidence(
            content="On-device inference cuts latency.",
            retriever="web",
            source_url="https://a.example",
        ),
        Evidence(
            content="Quantization shrinks models.", retriever="rag", source_chunk_id=3
        ),
    ]


def test_writer_prompt_presents_indexed_evidence():
    provider = _RecordingProvider("## Executive Summary\nx [ev:0].")
    writer.write_report(
        "Q?", _evidence(), draft_findings="some notes", provider=provider
    )

    user_msg = next(m for m in provider.messages if m["role"] == "user")["content"]
    assert "[ev:0] (web) On-device inference cuts latency." in user_msg
    assert "[ev:1] (rag) Quantization shrinks models." in user_msg
    assert "some notes" in user_msg  # advisory draft hint is included
    # Evidence is fenced as untrusted, and the system prompt carries the injection guard.
    assert "<<<UNTRUSTED_DATA>>>" in user_msg
    sys_msg = next(m for m in provider.messages if m["role"] == "system")["content"]
    assert "UNTRUSTED DATA" in sys_msg


def test_writer_node_sets_report_md(monkeypatch):
    monkeypatch.setattr(
        writer, "write_report", lambda q, ev, draft: "## Conclusion\ndone [ev:0]"
    )
    out = writer.writer_node(
        {"question": "Q", "evidence": _evidence(), "draft_findings": ""}  # type: ignore[arg-type]
    )
    assert out == {"report_md": "## Conclusion\ndone [ev:0]"}


def test_writer_to_validator_integration_produces_display_numbers_and_sources():
    # A Writer-style draft (no ## Sources, sparse [ev:i]); 2.6 turns it into [1..k] + sources.
    writer_output = (
        "## Executive Summary\nOn-device inference cuts latency [ev:0].\n\n"
        "## Findings\n### Efficiency\nQuantization shrinks models [ev:1].\n\n"
        "## Conclusion\nBoth matter [ev:0]."
    )
    result = validate_citations(writer_output, _evidence())

    assert result.citations_valid is True
    assert "[ev:" not in result.cleaned_report
    assert "[1]" in result.cleaned_report and "[2]" in result.cleaned_report
    assert "## Sources\n[1] https://a.example\n[2] chunk #3" in result.cleaned_report


@pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1",
    reason="set RUN_LLM_TESTS=1 with a real OPENAI_API_KEY (live LLM call)",
)
def test_write_report_live():
    report = writer.write_report(
        "What are the benefits of on-device LLM inference?", _evidence()
    )
    assert re.search(r"\[ev:\d+\]", report)  # cites by internal id
    assert "## " in report  # has structured sections
    assert "## Sources" not in report  # the Writer must NOT hand-roll a sources list
