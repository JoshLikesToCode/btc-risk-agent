import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from btc_risk.agents.tools import is_valid_address
from btc_risk.config import get_settings

app = FastAPI(title="btc-risk-agent")
STATIC = Path(__file__).parent / "static"


class AssessRequest(BaseModel):
    address: str
    depth: int = 2


class AskRequest(BaseModel):
    question: str


@lru_cache(maxsize=1)
def _sanctions():
    from btc_risk.deps import load_sanctions

    return load_sanctions(get_settings())


def _require_llm() -> None:
    if not get_settings().openai_api_key:
        raise HTTPException(400, "OPENAI_API_KEY is not set on the server (see .env)")


def _jsonable(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonable(v) for v in obj]
    return obj


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(_jsonable(data))}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "llm_configured": bool(get_settings().openai_api_key)}


@app.post("/api/assess")
def assess(req: AssessRequest):
    from btc_risk.chain.risk import assess_address
    from btc_risk.deps import build_chain_source

    if not is_valid_address(req.address):
        raise HTTPException(422, "not a valid Bitcoin address")
    return assess_address(
        build_chain_source(get_settings()),
        _sanctions(),
        req.address.strip(),
        max_depth=max(1, min(2, req.depth)),
    )


@app.post("/api/ask")
def ask(req: AskRequest):
    from btc_risk.agents.qa import answer_question
    from btc_risk.deps import build_chat_model, build_vector_store, langfuse_config

    _require_llm()
    settings = get_settings()
    ans = answer_question(
        build_vector_store(settings),
        build_chat_model(settings),
        req.question,
        config=langfuse_config(),
    )
    return {"answer": ans.answer, "chunk_ids": ans.chunk_ids}


@app.get("/api/investigate")
def investigate_stream(address: str, mode: str = "multi"):
    from btc_risk.agents.graph import stream_investigation
    from btc_risk.agents.single import investigate_single
    from btc_risk.deps import (
        Deps,
        build_chain_source,
        build_chat_model,
        build_vector_store,
        langfuse_config,
    )

    if not is_valid_address(address):
        raise HTTPException(422, "not a valid Bitcoin address")
    _require_llm()
    settings = get_settings()

    def events():
        try:
            deps = Deps(
                source=build_chain_source(settings),
                sanctions=_sanctions(),
                store=build_vector_store(settings),
            )
            model, config = build_chat_model(settings), langfuse_config()
            if mode == "single":
                yield _sse("node", {"name": "single_agent", "update": "running"})
                yield _sse("report", investigate_single(deps, model, address, config=config))
                return
            for node, update in stream_investigation(deps, model, address, config=config):
                if node == "finalize":
                    yield _sse("report", update["report"])
                else:
                    yield _sse("node", {"name": node, "update": update})
        except Exception as exc:
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(events(), media_type="text/event-stream")
