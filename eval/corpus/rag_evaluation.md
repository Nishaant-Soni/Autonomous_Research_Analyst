# Evaluating a RAG System

A retrieval-augmented generation system can fail in two distinct ways: it can
retrieve the wrong evidence, or it can write claims its evidence does not support.
Different metrics target each failure.

Faithfulness measures the fraction of claims in an answer that are supported by the
retrieved evidence. It is sometimes called groundedness. A faithful answer invents
nothing beyond what its sources say; an unfaithful one contains claims with no
backing, which is the definition of a hallucination.

Context recall measures whether retrieval surfaced the information needed to answer
the question. It is computed against a reference answer: of the facts the reference
considers necessary, how many appear in the retrieved context. Low context recall
points at the retriever, not the writer.

Answer relevance measures whether the response actually addresses the question that
was asked. A relevant answer is on-topic, as opposed to being correct but off-topic.

These metrics are often computed with an LLM acting as a judge, which reads the
question, the answer, the evidence, and the reference and scores each dimension.
