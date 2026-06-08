# Chunking and Vector Search

Vector search retrieves text by meaning rather than by exact keywords. Each passage
is converted into an embedding — a dense numerical vector — and a query is matched
against the corpus by vector similarity.

Before embedding, long documents are split into smaller pieces. Documents are split
into smaller chunks before embedding because embedding models have a limited context
window and retrieval works best on focused passages. A single embedding has to
summarize an entire chunk into one vector, so the size of that chunk matters.

Chunk size is a tradeoff. Chunks that are too large dilute the embedding with
multiple topics, reducing retrieval precision. The one vector has to represent
several unrelated ideas, so it matches queries weakly. The opposite extreme has its
own failure. Chunks that are too small can lose the surrounding context needed to
answer a question. A retrieved snippet may then be relevant but insufficient on its
own.

In practice, systems tune chunk size to balance precision against context, often
overlapping adjacent chunks so a fact that straddles a boundary is not lost.
