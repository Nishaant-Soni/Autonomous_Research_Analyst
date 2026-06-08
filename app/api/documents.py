"""Document ingestion endpoint (FR-5): chunk + embed + store."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingest.store import ingest_document

router = APIRouter()


class DocumentIn(BaseModel):
    raw_text: str = Field(min_length=1)
    title: str | None = None
    source_uri: str | None = None
    metadata: dict | None = None


class DocumentOut(BaseModel):
    document_id: int
    chunks: int


@router.post("/documents", response_model=DocumentOut)
def ingest_document_endpoint(
    doc: DocumentIn, db: Session = Depends(get_db)
) -> DocumentOut:
    document_id, chunks = ingest_document(
        db,
        raw_text=doc.raw_text,
        title=doc.title,
        source_uri=doc.source_uri,
        doc_metadata=doc.metadata,
    )
    db.commit()
    return DocumentOut(document_id=document_id, chunks=chunks)
