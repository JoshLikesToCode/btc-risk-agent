# btc-risk-agent

A multi-agent RAG system that triages Bitcoin wallet risk from public data. It traces
transaction graphs, checks sanctions exposure against the OFAC SDN list, retrieves guidance from a
corpus of fraud and sanctions-evasion research, and writes an evidence-cited report that a
deterministic verifier checks.

It reports **exposure to flagged entities, with evidence**. It does not label people. Output is
risk triage for a human analyst.

## How it works

```
                       ┌────────────── deterministic (no LLM) ──────────────┐
 address ─► triage ────┤ OFAC match · 1–2 hop exposure · peeling · CoinJoin │
                       └──────────────────────┬─────────────────────────────┘
                                              ▼
                                         supervisor (LLM plans follow-ups)
                              ┌───────────────┼────────────────┐   parallel
                              ▼               ▼                ▼
                        chain analyst      intel          researcher (RAG, pgvector)
                              └───────────────┼────────────────┘
                                              ▼
                       analyst (writes findings, each citing evidence ids)
                                              ▼
                       verifier ──fail (once)──► analyst
                                              ▼
                                           report
```

Design rules that matter:

- **Code decides the verdict; LLMs explain it.** Chain tracing, sanctions matching and scoring are
  plain tested Python. The model never chooses the verdict or score, and cannot override them.
- **Every finding must cite evidence** (`tx:…`, `ofac:…`, `doc:…`) that was actually gathered. The
  verifier rejects reports that cite anything else, and a failed report is returned *flagged*, not
  hidden.
- **Retrieved and fetched text is untrusted.** Web fetching is domain-allowlisted, and the model
  can only affect output through evidence ids that must resolve.
- A single-agent baseline (`--single`) shares tools, schema and verifier, so evals can compare the two.

## Stack

LangGraph (orchestration) · LangChain (agents, tools, retrieval) · OpenAI (chat + embeddings) ·
Postgres + pgvector · Langfuse (tracing) · Ragas (RAG metrics) · pytest (evals) · FastAPI ·
networkx · Python 3.12 with [uv](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync
cp .env.example .env        # add OPENAI_API_KEY (and Langfuse keys if you want tracing)
docker compose up -d        # Postgres + pgvector on localhost:5433
uv run btc-risk sanctions-update
```

## Use it

```bash
# works with no API key: deterministic assessment from live chain data
uv run btc-risk assess <address>
uv run btc-risk assess <address> --json --depth 1

# RAG: ingest PDFs / markdown / text / directories / allowlisted URLs, then ask
uv run btc-risk ingest corpus/ path/to/paper.pdf
uv run btc-risk ask "Why is a CoinJoin link weaker evidence?"

# full multi-agent investigation (or --single for the baseline)
uv run btc-risk investigate <address>

# web UI at http://127.0.0.1:8000
uv run btc-risk serve
```

The first lookup of an address is slow (public explorer, polite rate limit); responses are cached
in `data/chain_cache.sqlite` for 24 hours.

## Tests and evals

```bash
uv run pytest                              # 41 offline unit tests, no network or key needed
uv run pytest evals -m eval -s             # labeled-wallet verdict eval (live chain data)
uv run pytest evals -m llm_eval -s         # Ragas RAG eval + multi-vs-single agent comparison
uv run python evals/build_dataset.py       # rebuild the labeled wallet snapshot
```

See `docs/design.md` for what each eval does and does not prove.

## Layout

```
src/btc_risk/
├── sanctions/   OFAC SDN parsing + address lookup
├── chain/       explorer client + cache, graph builder, heuristics, risk scoring
├── ingest/      loaders, chunking with stable ids, idempotent vector-store ingest
├── agents/      LangGraph supervisor, single-agent baseline, tools, verifier, corpus QA
├── api/         FastAPI + SSE streaming + static UI
├── web.py       allowlisted fetch
└── cli.py       `btc-risk` command
corpus/          starter analyst notes (replace/extend with real research and guidance)
evals/           datasets, Ragas + agent + wallet evals, results
tests/           offline unit tests (scripted fake chat model, in-memory vector store)
```

## Known limitations

See "Honest limitations" in `docs/design.md`. In short: exposure only covers OFAC-listed addresses,
the analysis window is the most recent transactions, heuristics are probabilistic, and the labeled
eval set is small and partly synthetic.
