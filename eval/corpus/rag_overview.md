# Retrieval-Augmented Generation: An Overview

Retrieval-augmented generation (RAG) is an architecture for grounding a language
model's output in an external knowledge source. A retrieval-augmented generation
system has two core components: a retriever and a generator.

The retriever finds relevant documents or passages from a knowledge source given
the user's query. It typically embeds the query into a vector and searches a
corpus of pre-embedded passages for the closest matches, returning the top
candidates as evidence.

The second component is a language model. The generator conditions its output on
the retrieved passages, producing an answer grounded in that evidence. Because the
answer is built from the retrieved text, each claim can be traced back to a specific
source.

A key operational advantage is freshness. RAG keeps knowledge current by updating
the retrieval corpus rather than retraining the model. To teach the system about
new information, you add or replace documents in the corpus; the generator picks
them up on the next query with no change to its weights.
