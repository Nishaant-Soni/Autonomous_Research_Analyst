import os

import pytest

from app import embeddings


class _FakeModel:
    def __init__(self):
        self.seen: list[str] = []

    def encode(self, texts, **kwargs):
        self.seen = list(texts)
        return [[0.0] * 384 for _ in texts]


def test_needs_query_prefix_branching():
    assert embeddings._needs_query_prefix("BAAI/bge-small-en-v1.5") is True
    assert embeddings._needs_query_prefix("all-MiniLM-L6-v2") is False


def test_embed_query_applies_prefix_for_bge(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(embeddings, "_get_model", lambda: fake)
    monkeypatch.setattr(
        embeddings.settings, "embedding_model", "BAAI/bge-small-en-v1.5"
    )

    vec = embeddings.embed_query("what is rag")

    assert len(vec) == 384
    assert fake.seen[0] == embeddings.QUERY_PREFIX + "what is rag"


def test_embed_query_no_prefix_for_minilm(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(embeddings, "_get_model", lambda: fake)
    monkeypatch.setattr(embeddings.settings, "embedding_model", "all-MiniLM-L6-v2")

    embeddings.embed_query("what is rag")

    assert fake.seen[0] == "what is rag"


def test_embed_documents_never_prefixed(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(embeddings, "_get_model", lambda: fake)
    monkeypatch.setattr(
        embeddings.settings, "embedding_model", "BAAI/bge-small-en-v1.5"
    )

    vecs = embeddings.embed_documents(["doc one", "doc two"])

    assert len(vecs) == 2 and all(len(v) == 384 for v in vecs)
    assert fake.seen == ["doc one", "doc two"]  # no prefix on the document path


@pytest.mark.skipif(
    os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="set RUN_MODEL_TESTS=1 to load the real embedding model",
)
def test_real_model_is_384_dim():
    assert len(embeddings.embed_documents(["hello world"])[0]) == 384
    assert len(embeddings.embed_query("hello world")) == 384
