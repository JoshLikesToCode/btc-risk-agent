"""RAG quality with Ragas over the starter corpus. Needs OPENAI_API_KEY and the Postgres container.

Run: uv run pytest evals/test_rag_eval.py -m llm_eval -s
Thresholds are provisional: set them after the first real run, then tighten.
"""

import json

import pytest
from conftest import DATASETS, write_results
from ragas_compat import import_ragas

pytestmark = pytest.mark.llm_eval


@pytest.fixture(scope="module")
def qa(settings):
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")
    from btc_risk.agents.qa import answer_question
    from btc_risk.deps import build_chat_model, build_vector_store
    from btc_risk.ingest.pipeline import ingest

    store = build_vector_store(settings)
    ingest(["corpus"], store)
    model = build_chat_model(settings)
    return [
        (item, answer_question(store, model, item["question"]))
        for item in json.loads((DATASETS / "rag_questions.json").read_text())
    ]


def test_ragas_scores(qa, settings):
    import_ragas()
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall

    samples = [
        SingleTurnSample(
            user_input=item["question"],
            retrieved_contexts=ans.contexts,
            response=ans.answer,
            reference=item["reference"],
        )
        for item, ans in qa
    ]
    judge = LangchainLLMWrapper(
        ChatOpenAI(model=settings.chat_model, api_key=settings.openai_api_key)
    )
    emb = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
    )
    result = evaluate(
        EvaluationDataset(samples=samples),
        metrics=[Faithfulness(), LLMContextRecall(), LLMContextPrecisionWithReference()],
        llm=judge,
        embeddings=emb,
    )
    df = result.to_pandas()
    scores = {
        c: float(df[c].mean())
        for c in df.columns
        if c in ("faithfulness", "context_recall", "llm_context_precision_with_reference")
    }
    write_results("rag-latest", {"scores": scores, "n": len(samples)})
    print("\nRagas:", scores)
    assert scores["faithfulness"] >= 0.7
    assert scores["context_recall"] >= 0.6
