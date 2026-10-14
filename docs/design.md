# Design

## Principle

Deterministic code does the analysis; agents decide what to investigate and explain results.
Chain tracing, sanctions matching and scoring are tested Python exposed to agents as tools. LLMs are
never asked whether an address is sanctioned, and never choose the verdict or score.

## Components

| Component | Responsibility |
|---|---|
| `sanctions/` | Parse the OFAC SDN CSV, extract `Digital Currency Address - XBT` entries, exact lookup (bech32 case-insensitive) |
| `chain/explorer.py` | `ChainSource` interface; mempool.space client with pagination, retry, and a SQLite response cache |
| `chain/graph.py` | Depth/fanout/node-bounded subgraph; flows attributed to inputs proportionally; marks CoinJoin edges; records truncation |
| `chain/heuristics.py` | CoinJoin detection, common-input clustering, peeling-chain detection |
| `chain/risk.py` | Exposure paths (1-2 hops, strict vs CoinJoin-mediated), signals, verdict/score, evidence ids, limitations |
| `ingest/` | Load md/txt/pdf/URL, chunk with deterministic ids (`doc:<source>#<n>`), upsert into pgvector |
| `agents/graph.py` | LangGraph: triage → supervisor → parallel specialists → analyst ⇄ verifier → report |
| `agents/single.py` | Single tool-calling agent baseline with the same tools, schema and verifier |
| `agents/verify.py` | Deterministic report checks (citations resolve, sanctions evidence cited, severity not overstated) |
| `api/` | FastAPI; SSE streams graph node updates; static page renders with `textContent` only (no model HTML) |

## Risk scoring

Hand-set priors, not calibrated probabilities:

| Condition | Verdict | Score |
|---|---|---|
| Address is OFAC-listed | `sanctioned` | 100 |
| 1 hop to a listed address | `high_exposure` | 80 |
| 2 hops | `elevated` | 50 |
| 1 / 2 hops only through a CoinJoin | `elevated` | 35 / 20 |
| No exposure | `low` | 0 |
| Peeling chain / CoinJoin participation | adds 5 each (capped at 99) | |
| No on-chain history | `insufficient_data` | 0 |

CoinJoin-mediated links are discounted because every participant in the transaction is linked to
every other one by construction.

## Evals

| Eval | Where | Measures | Needs |
|---|---|---|---|
| Unit tests | `tests/` | Logic, graph orchestration with a scripted model, verifier retry loop, API + SSE | nothing |
| Wallet verdicts | `evals/test_wallet_eval.py` | Pipeline reproduces labels from an independent adjacency rule: sanctioned recall, hop-1 recall, false-positive rate on presumed-clean addresses | network |
| RAG | `evals/test_rag_eval.py` | Ragas faithfulness, context recall, context precision on typology questions | OpenAI key, Postgres |
| Multi vs single | `evals/test_agent_eval.py` | Verification pass rate, OFAC citation recall, overstated severity on clean wallets, latency | OpenAI key, Postgres |

## Honest limitations

- **The wallet eval is an integration/regression test, not a measure of real-world detection
  accuracy.** Its labels come from adjacency rules over the same public data. Real validation needs
  independently labeled illicit-activity data (for example published research datasets; verify
  licensing) and curated, sourced clean wallets such as exchanges. Put the latter in
  `evals/datasets/curated_clean.json` as `[{"address": ..., "note": ...}]`.
- `presumed_clean` addresses are random and unverified. They estimate a base rate, not innocence.
- Exposure covers OFAC-listed Bitcoin addresses only. Designated parties use unlisted addresses.
- Only the most recent transactions per expanded address are analyzed (default 25), so older
  exposure is invisible. Reports state coverage and truncation.
- High-volume service/exchange addresses produce expected indirect exposure; this is flagged as a
  limitation rather than modelled.
- Common-input and peeling heuristics are probabilistic and also match ordinary wallets.
- Ragas 0.4.3 does not import with langchain-community 0.4.x (it imports a removed Vertex AI
  class). `evals/ragas_compat.py` shims it for evals only; remove it when upstream fixes this.
- Tool-calling paths are tested offline with a scripted chat model. Real-model behaviour (prompt
  quality, tool selection) is only exercised by the `llm_eval` suite, which needs a key.
- The corpus shipped in `corpus/` is short analyst notes written for this project, not primary
  sources. Ingest real regulator guidance and research and prefer those.

## Roadmap

1. [x] OFAC sanctions lookup
2. [x] Chain-data tools + graph heuristics
3. [x] Single-agent baseline
4. [x] RAG ingestion + retrieval (pgvector)
5. [x] Multi-agent supervisor with verifier
6. [x] CLI, web UI, Langfuse hook, evals
7. [ ] Real labeled illicit-wallet dataset and curated exchange/clean set
8. [ ] Self-hosted Langfuse in compose
9. [ ] Service/exchange address recognition to dampen indirect exposure
10. [ ] Taint models (haircut/FIFO) beyond hop distance
