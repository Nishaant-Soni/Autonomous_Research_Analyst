"""pgvector similarity search — the `rag_retrieve` tool (FR-4)."""

from sqlalchemy import select

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.embeddings import embed_query
from app.models.evidence import Evidence


def rag_retrieve(query: str, k: int = 5) -> list[Evidence]:
    """Return the top-k corpus chunks most similar to `query` as `Evidence`.

    Uses cosine distance (matches the HNSW cosine index and normalized embeddings).
    """
    query_vector = embed_query(query)
    with SessionLocal() as db:
        chunks = (
            db.execute(
                select(Chunk)
                .order_by(Chunk.embedding.cosine_distance(query_vector))
                .limit(k)
            )
            .scalars()
            .all()
        )
    return [
        Evidence(content=c.content, source_chunk_id=c.id, retriever="rag")
        for c in chunks
    ]
