# btc-risk-agent

A multi-agent RAG system that triages Bitcoin wallet risk from public data. It traces transaction
graphs, checks sanctions exposure, retrieves guidance from a corpus of fraud and sanctions-evasion
research, and writes an evidence-cited report.

It reports **exposure to flagged entities, with evidence**. It does not label people. Output is
risk triage for a human analyst, and the evals measure false positives explicitly.

## Stack

LangGraph (agent orchestration) · Postgres + pgvector · Langfuse (tracing) · pytest (evals) ·
Ragas (RAG metrics) · Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

## Quick start

```bash
uv sync
cp .env.example .env
docker compose up -d      # Postgres + pgvector
uv run pytest
```

## Layout

```
src/btc_risk/
├── sanctions/   # OFAC SDN parsing + address lookup (deterministic)
├── chain/       # blockchain data + graph analysis tools
├── ingest/      # document ingestion agent / RAG pipeline
├── agents/      # LangGraph supervisor + specialist agents
└── api/         # FastAPI / chat surface
evals/           # labeled wallet datasets + eval runs
tests/           # unit tests
docs/design.md   # architecture and decisions
```

## Status

Early. Done: OFAC sanctions lookup. See `docs/design.md` for the roadmap.
