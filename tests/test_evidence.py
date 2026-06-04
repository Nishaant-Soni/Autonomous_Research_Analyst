import pytest
from pydantic import ValidationError

from app.models.evidence import Evidence


def test_web_evidence_valid():
    e = Evidence(content="x", retriever="web", source_url="https://example.com")
    assert e.retriever == "web"
    assert e.source_url == "https://example.com"


def test_rag_evidence_valid():
    e = Evidence(content="x", retriever="rag", source_chunk_id=42)
    assert e.retriever == "rag"
    assert e.source_chunk_id == 42


def test_bad_retriever_rejected():
    with pytest.raises(ValidationError):
        Evidence(content="x", retriever="other", source_url="https://example.com")


def test_web_requires_source_url():
    with pytest.raises(ValidationError):
        Evidence(content="x", retriever="web")


def test_rag_requires_source_chunk_id():
    with pytest.raises(ValidationError):
        Evidence(content="x", retriever="rag")
