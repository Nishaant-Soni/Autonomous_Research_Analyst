"""Local sentence-transformers embeddings (PRD §7, §8).

384-dim vectors, model loaded once (singleton). `bge` models get a query-only
instruction prefix (PRD §8); `all-MiniLM-L6-v2` (also 384-dim) needs none, so it stays
drop-in. The prefix is applied on the query path only — never to stored documents.
"""

from __future__ import annotations

from app.config import settings

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _needs_query_prefix(model_name: str) -> bool:
    return "bge" in model_name.lower()


def embed_documents(texts: list[str]) -> list[list[float]]:
    vectors = _get_model().encode(texts, normalize_embeddings=True)
    return [list(map(float, v)) for v in vectors]


def embed_query(text: str) -> list[float]:
    if _needs_query_prefix(settings.embedding_model):
        text = QUERY_PREFIX + text
    vector = _get_model().encode([text], normalize_embeddings=True)[0]
    return list(map(float, vector))
