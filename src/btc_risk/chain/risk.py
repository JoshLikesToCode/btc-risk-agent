"""Deterministic risk assessment: sanctions exposure + behavioural signals.

Score weights are hand-set priors, not calibrated probabilities. The evals measure how the
resulting verdicts behave on labeled addresses; do not read the number as a likelihood.
"""

from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field

from btc_risk.chain.explorer import ChainSource
from btc_risk.chain.graph import TxGraph, build_subgraph
from btc_risk.chain.heuristics import (
    cluster_by_common_input,
    find_peeling_chains,
    looks_like_coinjoin,
)
from btc_risk.sanctions import SanctionsList

Verdict = Literal["sanctioned", "high_exposure", "elevated", "low", "insufficient_data"]

# exposure score by (hops, via_coinjoin); hops beyond 2 are not computed
_EXPOSURE_SCORE = {(1, False): 80, (2, False): 50, (1, True): 35, (2, True): 20}


class Exposure(BaseModel):
    sanctioned_address: str
    entity_name: str
    program: str
    ent_num: str
    hops: int
    direction: Literal["received_from", "sent_to"]
    via_coinjoin: bool
    txids: list[str]


class Signal(BaseModel):
    kind: Literal["peeling_chain", "coinjoin_participation", "common_input_cluster"]
    description: str
    txids: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    address: str
    verdict: Verdict
    score: int
    direct_match: bool = False
    exposures: list[Exposure] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    nodes: int = 0
    txs_analyzed: int = 0
    tx_count_total: int = 0
    truncated: bool = False
    limitations: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)  # evidence id -> human summary


def _shortest(g: nx.DiGraph, src: str, dst: str) -> list[str] | None:
    try:
        return nx.shortest_path(g, src, dst)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def _path_txids(g: nx.DiGraph, path: list[str]) -> list[str]:
    return [g[a][b]["txids"][0] for a, b in zip(path, path[1:], strict=False)]


def find_exposures(tg: TxGraph, sanctions: SanctionsList, max_hops: int = 2) -> list[Exposure]:
    strict = nx.DiGraph((u, v, d) for u, v, d in tg.graph.edges(data=True) if not d["coinjoin"])
    out: list[Exposure] = []
    for node in tg.graph.nodes:
        entry = sanctions.lookup(node)
        if entry is None or node == tg.seed:
            continue
        best: Exposure | None = None
        for direction, (src, dst) in (
            ("received_from", (node, tg.seed)),
            ("sent_to", (tg.seed, node)),
        ):
            for graph, via_cj in ((strict, False), (tg.graph, True)):
                path = _shortest(graph, src, dst)
                if path is None or len(path) - 1 > max_hops:
                    continue
                cand = Exposure(
                    sanctioned_address=node,
                    entity_name=entry.entity_name,
                    program=entry.program,
                    ent_num=entry.ent_num,
                    hops=len(path) - 1,
                    direction=direction,
                    via_coinjoin=via_cj,
                    txids=_path_txids(tg.graph, path),
                )
                if (
                    best is None
                    or _EXPOSURE_SCORE[(cand.hops, cand.via_coinjoin)]
                    > _EXPOSURE_SCORE[(best.hops, best.via_coinjoin)]
                ):
                    best = cand
                break  # strict path found for this direction; don't downgrade to coinjoin
        if best:
            out.append(best)
    return sorted(out, key=lambda e: (-_EXPOSURE_SCORE[(e.hops, e.via_coinjoin)], e.hops))


def assess_address(
    source: ChainSource,
    sanctions: SanctionsList,
    address: str,
    max_depth: int = 2,
    max_txs: int = 25,
) -> RiskAssessment:
    summary = source.address_summary(address)
    direct = sanctions.lookup(address)
    if summary.tx_count == 0 and direct is None:
        return RiskAssessment(
            address=address,
            verdict="insufficient_data",
            score=0,
            limitations=["Address has no confirmed on-chain history."],
        )

    tg = build_subgraph(source, address, sanctions, max_depth=max_depth, max_txs=max_txs)
    txs = list(tg.txs.values())
    exposures = find_exposures(tg, sanctions, max_hops=max_depth)

    signals: list[Signal] = []
    seed_txs = [t for t in txs if address in t.input_addresses | t.output_addresses]
    chains = sorted(find_peeling_chains(txs), key=len, reverse=True)
    if chains:
        signals.append(
            Signal(
                kind="peeling_chain",
                description=(
                    f"{len(chains)} peeling chain(s) in the analyzed graph; "
                    f"longest has {len(chains[0])} consecutive transactions"
                ),
                txids=chains[0],
            )
        )
    cj = [t.txid for t in seed_txs if looks_like_coinjoin(t)]
    if cj:
        signals.append(
            Signal(
                kind="coinjoin_participation",
                description=f"Address appears in {len(cj)} CoinJoin-like transaction(s)",
                txids=cj,
            )
        )
    for cluster in cluster_by_common_input(txs):
        if address in cluster:
            signals.append(
                Signal(
                    kind="common_input_cluster",
                    description=f"Address co-spends with {len(cluster) - 1} other address(es)",
                    txids=[],
                )
            )

    evidence: dict[str, str] = {}
    if direct:
        evidence[f"ofac:{direct.ent_num}"] = (
            f"{address} is listed on the OFAC SDN list: {direct.entity_name} ({direct.program})"
        )
    for e in exposures:
        evidence[f"ofac:{e.ent_num}"] = (
            f"{e.sanctioned_address} is OFAC-listed: {e.entity_name} ({e.program})"
        )
        for txid in e.txids:
            evidence[f"tx:{txid}"] = (
                f"transaction on a {e.hops}-hop path ({e.direction}) to {e.sanctioned_address}"
            )
    for s in signals:
        for txid in s.txids:
            evidence.setdefault(f"tx:{txid}", f"{s.kind}: {s.description}")

    if direct:
        verdict, score = "sanctioned", 100
    elif exposures:
        score = _EXPOSURE_SCORE[(exposures[0].hops, exposures[0].via_coinjoin)]
        verdict = "high_exposure" if score >= 80 else "elevated"
    else:
        score, verdict = 0, "low"
    if verdict not in ("sanctioned",):
        score = min(99, score + (5 if any(s.kind == "peeling_chain" for s in signals) else 0))
        score = min(99, score + (5 if cj else 0))
        if verdict == "low" and signals and score >= 10:
            verdict = "elevated"

    limitations = [
        f"Only the {max_txs} most recent transactions per expanded address were analyzed; "
        "older exposure is not visible.",
        "Exposure is limited to OFAC-listed Bitcoin addresses; other risk sources are not checked.",
        "Heuristics (peeling, common-input) are probabilistic and also match ordinary wallets.",
    ]
    if summary.tx_count > 1000:
        limitations.append(
            f"High-volume address ({summary.tx_count} txs; likely a service or exchange): "
            "counterparty exposure is expected and weakly informative."
        )
    if tg.truncated:
        limitations.append("The transaction graph was truncated by node/fanout limits.")

    return RiskAssessment(
        address=address,
        verdict=verdict,
        score=score,
        direct_match=direct is not None,
        exposures=exposures,
        signals=signals,
        nodes=len(tg.graph),
        txs_analyzed=len(tg.txs),
        tx_count_total=summary.tx_count,
        truncated=tg.truncated,
        limitations=limitations,
        evidence=evidence,
    )
