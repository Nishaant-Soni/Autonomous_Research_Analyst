"""pgvector similarity search — the `rag_retrieve` tool (FR-4)."""

from sqlalchemy import select

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.embeddings import embed_query
from app.models.evidence import Evidence


def rag_retrieve(
    query: str,
    k: int = 5,
    user_id: int | None = None,
    allow_all_users: bool = False,
) -> list[Evidence]:
    """Return the top-k corpus chunks most similar to `query` as `Evidence`.

    Fail-closed scoping: a query is scoped to `user_id`'s documents. Retrieving across all
    users must be opted into *explicitly* with `allow_all_users=True` (eval / offline only).
    A bare `user_id=None` raises — so a future API call site that forgets to pass the owner
    cannot silently read another user's corpus (the dangerous default this guard removes).

    Uses cosine distance (matches the HNSW cosine index and normalized embeddings).
    """
    if user_id is None and not allow_all_users:
        raise ValueError(
            "rag_retrieve requires user_id; pass allow_all_users=True only for "
            "eval/offline use (never on a per-user request path)"
        )
    query_vector = embed_query(query)
    with SessionLocal() as db:
        q = select(Chunk).join(Document, Chunk.document_id == Document.id)
        if user_id is not None:
            q = q.where(Document.user_id == user_id)
        chunks = (
            db.execute(
                q.order_by(Chunk.embedding.cosine_distance(query_vector)).limit(k)
            )
            .scalars()
            .all()
        )
    return [
        Evidence(content=c.content, source_chunk_id=c.id, retriever="rag")
        for c in chunks
    ]
