# Design

## Principle

Deterministic code does the analysis; agents decide what to investigate and explain results.
Chain tracing, sanctions matching and graph heuristics are plain tested Python exposed to agents
as tools. LLMs are never asked to "figure out" whether an address is sanctioned.

## Agents (LangGraph supervisor + specialists)

| Agent | Responsibility |
|---|---|
| Supervisor | Plans the investigation, fans out, merges findings, writes the report |
| Ingestion | Parses PDFs/advisories, chunks, embeds into pgvector with metadata (source, date, typology) |
| Chain data | Fetches address/tx data, builds a depth-bounded subgraph, caches in Postgres |
| Intel | Sanctions lists, labeled-address datasets, scraped/public context |
| Verifier | Checks each report claim against retrieved evidence and real transactions |

## Data sources

- OFAC SDN list (authoritative sanctioned XBT addresses)
- Public explorer API (mempool.space / Blockstream) for chain data, cached for repeatable evals
- Public labeled datasets for fraud labels (verify license before use)
- RAG corpus: published research on fraud and sanctions evasion typologies

## Evals

- Labeled set: OFAC-listed addresses vs. known-clean ones (exchanges, ordinary wallets)
- Metrics: verdict accuracy, false-positive rate, evidence faithfulness (claims trace to txs)
- RAG: Ragas (faithfulness, context precision/recall) on typology questions
- Compare single agent vs. multi-agent on the same set before claiming multi-agent helps
- Known limitation: "innocent" is hard to prove; high-volume exchange wallets look suspicious

## Roadmap

1. [x] OFAC sanctions lookup
2. [ ] Chain-data tools + graph heuristics (hop exposure, peeling chains)
3. [ ] Single agent over the tools + first eval set
4. [ ] RAG ingestion + retrieval
5. [ ] Multi-agent supervisor + comparison eval
6. [ ] Langfuse tracing, chat UI, compose for everything
