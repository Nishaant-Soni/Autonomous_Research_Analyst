"""Per-run Ragas scoring for completed UI runs (reference-free metrics only).

Computes faithfulness + answer_relevancy and derives hallucination_rate = 1 - faithfulness,
then persists all three on the reports row. Soft-imports ragas so the runtime image works
without the eval deps installed — when ragas is absent the function returns silently and
the report columns stay NULL.

Called from runner.py in a threadpool executor after _persist_result succeeds so the user
sees the finished report immediately while scoring happens in the background.
"""

import logging

logger = logging.getLogger(__name__)

_JUDGE_MODEL = "gpt-5.4-mini"
_EMBED_MODEL = "text-embedding-3-small"


def score_run(session_id: int, question: str, report_md: str, evidence: list) -> None:
    """Score a completed run and persist the results. Safe to call in a threadpool.

    Silently skips if ragas is not installed or if scoring fails — the run result is
    never affected.
    """
    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import EvaluationDataset, evaluate
        from ragas.dataset_schema import SingleTurnSample
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import AnswerRelevancy, Faithfulness
    except ImportError:
        logger.debug(
            "ragas not installed; skipping per-run scoring for session %d", session_id
        )
        return

    try:
        from app.config import settings

        contexts = [ev.content for ev in evidence if ev.content]
        if not contexts:
            logger.warning(
                "session %d: no evidence content; skipping scoring", session_id
            )
            return

        judge_llm = LangchainLLMWrapper(
            ChatOpenAI(model=_JUDGE_MODEL, api_key=settings.openai_api_key)
        )
        judge_emb = LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(model=_EMBED_MODEL, api_key=settings.openai_api_key)
        )

        sample = SingleTurnSample(
            user_input=question,
            response=report_md,
            retrieved_contexts=contexts,
        )
        dataset = EvaluationDataset(samples=[sample])
        result = evaluate(
            dataset=dataset,
            metrics=[Faithfulness(), AnswerRelevancy()],
            llm=judge_llm,
            embeddings=judge_emb,
            show_progress=False,
        )

        df = result.to_pandas()

        def _val(col: str) -> float | None:
            v = df[col].iloc[0]
            if v is None or (isinstance(v, float) and v != v):  # None or NaN
                return None
            return float(v)

        faithfulness = _val("faithfulness")
        answer_relevancy = _val("answer_relevancy")
        hallucination_rate = (1.0 - faithfulness) if faithfulness is not None else None

        _persist_scores(session_id, faithfulness, answer_relevancy, hallucination_rate)
        logger.info(
            "session %d scored: faithfulness=%.3f answer_relevancy=%.3f hallucination_rate=%.3f",
            session_id,
            faithfulness or 0.0,
            answer_relevancy or 0.0,
            hallucination_rate or 0.0,
        )

    except Exception:
        logger.exception(
            "ragas scoring failed for session %d; run result is unaffected", session_id
        )


def _persist_scores(
    session_id: int,
    faithfulness: float | None,
    answer_relevancy: float | None,
    hallucination_rate: float | None,
) -> None:
    from app.db.models import Report
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        report = (
            db.query(Report)
            .filter_by(session_id=session_id)
            .order_by(Report.id.desc())
            .first()
        )
        if report is None:
            logger.warning("no report row for session %d; scores not saved", session_id)
            return
        report.faithfulness = faithfulness
        report.answer_relevancy = answer_relevancy
        report.hallucination_rate = hallucination_rate
        db.commit()
