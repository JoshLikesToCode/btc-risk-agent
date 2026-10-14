"""Composition root: build the concrete services from settings."""

from dataclasses import dataclass, field

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from btc_risk.chain.explorer import ChainSource, JsonCache, MempoolSpaceClient
from btc_risk.chain.risk import RiskAssessment
from btc_risk.config import Settings, get_settings
from btc_risk.sanctions import SanctionsList, download_sdn_xml


def load_sanctions(settings: Settings, refresh: bool = False) -> SanctionsList:
    path = settings.sdn_path
    if refresh or not path.exists():
        download_sdn_xml(path)
    return SanctionsList.from_xml(path)


def build_chain_source(settings: Settings) -> ChainSource:
    return MempoolSpaceClient(
        JsonCache(settings.chain_cache_path), base_url=settings.mempool_base_url
    )


def build_chat_model(settings: Settings) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.chat_model, api_key=settings.openai_api_key or None, temperature=0
    )


def build_embeddings(settings: Settings) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key or None)


def build_vector_store(settings: Settings, embeddings: Embeddings | None = None) -> VectorStore:
    from langchain_postgres import PGVector

    return PGVector(
        embeddings=embeddings or build_embeddings(settings),
        collection_name="typologies",
        connection=settings.sqlalchemy_url,
        use_jsonb=True,
    )


def langfuse_config(settings: Settings | None = None) -> dict:
    """LangChain run config that traces to Langfuse when keys are configured, else empty."""
    import os

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return {}
    from langfuse.langchain import CallbackHandler

    return {"callbacks": [CallbackHandler()]}


@dataclass
class Deps:
    """Everything an investigation run needs. One instance per run (holds run-local evidence)."""

    source: ChainSource
    sanctions: SanctionsList
    store: VectorStore | None = None
    evidence: dict[str, str] = field(default_factory=dict)
    assessments: dict[str, RiskAssessment] = field(default_factory=dict)


def build_deps(settings: Settings | None = None, with_store: bool = True) -> Deps:
    settings = settings or get_settings()
    return Deps(
        source=build_chain_source(settings),
        sanctions=load_sanctions(settings),
        store=build_vector_store(settings) if with_store else None,
    )
