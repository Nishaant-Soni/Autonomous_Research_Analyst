"""Deterministic character-based chunking with overlap.

Kept simple on purpose (PRD §6 / coding-guidelines): fixed-size windows with a fixed
overlap so the same input always yields the same chunks. Token-aware chunking is a
later optimization, not needed for v1.
"""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - overlap
    return chunks
