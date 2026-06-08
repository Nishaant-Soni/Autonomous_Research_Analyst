"""Ragas-based metrics (plan 4.2, B2): faithfulness, answer_relevancy, context_recall,
plus the derived headline `hallucination_rate = 1 - faithfulness` (PRD §10).

Per the plan decision under 4.2:
- The judge is a **separate** `langchain_openai.ChatOpenAI` instance (and `OpenAIEmbeddings`
  for answer_relevancy), NOT a wrapper around our `OpenAIProvider`. Eval is infrastructure;
  the product's Responses-API path stays out of eval failures.
- The deps live in the `eval` optional-deps group (`pip install -e ".[eval]"`); imports are
  lazy so the deterministic Score stage (B1) keeps working without the extra installed.
"""

import logging
from statistics import mean

logger = logging.getLogger(__name__)

# Defaults match the runtime model + a cheap, fast embedding model for answer_relevancy.
# Override via env if a future change requires a different judge.
_JUDGE_MODEL = "gpt-5.4-mini"
_EMBED_MODEL = "text-embedding-3-small"


def _aggregate(per_item: dict[str, float | None]) -> dict:
    """Same shape as `eval.metrics.deterministic.citation_accuracy_aggregate` so the score
    file stays uniform. Missing/None per-item values count as `n_failed`, not zero."""
    scored = {k: v for k, v in per_item.items() if v is not None}
    if not scored:
        return {
            "n_scored": 0,
            "n_failed": len(per_item),
            "mean": None,
            "min": None,
            "max": None,
        }
    values = list(scored.values())
    return {
        "n_scored": len(scored),
        "n_failed": len(per_item) - len(scored),
        "mean": mean(values),
        "min": min(values),
        "max": max(values),
    }


def _is_nan(v) -> bool:
    """Ragas surfaces float('nan') for samples a metric couldn't score; treat as None."""
    return isinstance(v, float) and v != v


def score_with_ragas(samples: list[dict]) -> dict:
    """Score `samples` (shape: {id, question, answer, contexts, reference, ...}) on
    Ragas faithfulness / answer_relevancy / context_recall and derive hallucination_rate.
    Returns `{"ragas": {...}, "hallucination_rate": {...}}` ready to fold into scores.json."""
    # Lazy imports — only required when the user actually runs Ragas scoring.
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, evaluate
    from ragas.dataset_schema import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import AnswerRelevancy, Faithfulness, LLMContextRecall

    if not samples:
        return {"ragas": {}, "hallucination_rate": {}}

    # `ChatOpenAI` / `OpenAIEmbeddings` read `OPENAI_API_KEY` from `os.environ`, but our
    # settings load `.env` via pydantic-settings (which doesn't set os.environ). Pass the key
    # in explicitly so eval works regardless of whether the shell exported the var.
    from app.config import settings

    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(model=_JUDGE_MODEL, api_key=settings.openai_api_key)
    )
    judge_emb = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=_EMBED_MODEL, api_key=settings.openai_api_key)
    )

    ragas_samples = [
        SingleTurnSample(
            user_input=s["question"],
            response=s["answer"],
            retrieved_contexts=s["contexts"],
            reference=s["reference"],
        )
        for s in samples
    ]
    dataset = EvaluationDataset(samples=ragas_samples)
    metrics = [Faithfulness(), AnswerRelevancy(), LLMContextRecall()]

    logger.info(
        "ragas: judging %d samples × %d metrics with %s",
        len(samples),
        len(metrics),
        _JUDGE_MODEL,
    )
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_emb,
        show_progress=False,
    )

    df = result.to_pandas()
    sample_ids = [s["id"] for s in samples]
    out_ragas: dict[str, dict] = {}
    for metric_col in ("faithfulness", "answer_relevancy", "context_recall"):
        per_item = {
            sid: (None if (v is None or _is_nan(v)) else float(v))
            for sid, v in zip(sample_ids, df[metric_col].tolist(), strict=True)
        }
        out_ragas[metric_col] = {
            "aggregate": _aggregate(per_item),
            "per_item": per_item,
        }

    # Hallucination rate is the headline derivative of faithfulness (PRD §10).
    faith_per_item = out_ragas["faithfulness"]["per_item"]
    hallucination_per_item = {
        k: (None if v is None else 1.0 - v) for k, v in faith_per_item.items()
    }
    return {
        "ragas": out_ragas,
        "hallucination_rate": {
            "aggregate": _aggregate(hallucination_per_item),
            "per_item": hallucination_per_item,
        },
    }
