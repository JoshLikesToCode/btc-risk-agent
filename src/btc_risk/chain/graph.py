"""Depth-bounded transaction subgraph around a seed address.

Edges are address -> address flows. For each transaction, every output is attributed to the
input addresses in proportion to how much each input contributed. Expansion is bounded three
ways (depth, per-node fanout, total nodes) because real transaction graphs explode; anything
the bound cuts off is recorded so the report can say so instead of implying full coverage.
"""

from dataclasses import dataclass, field

import networkx as nx

from btc_risk.chain.explorer import ChainSource
from btc_risk.chain.heuristics import looks_like_coinjoin
from btc_risk.chain.models import Tx
from btc_risk.sanctions import SanctionsList


@dataclass
class TxGraph:
    seed: str
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    txs: dict[str, Tx] = field(default_factory=dict)
    expanded: set[str] = field(default_factory=set)
    truncated: bool = False  # a bound (nodes/fanout) cut off part of the graph


def add_tx_edges(tg: TxGraph, tx: Tx) -> None:
    if tx.txid in tg.txs:
        return
    tg.txs[tx.txid] = tx
    coinjoin = looks_like_coinjoin(tx)
    total_in = sum(i.value for i in tx.inputs)
    if not total_in:
        return
    in_by_addr: dict[str, int] = {}
    for i in tx.inputs:
        if i.address:
            in_by_addr[i.address] = in_by_addr.get(i.address, 0) + i.value
    for out in tx.outputs:
        if not out.address:
            continue
        for src, contributed in in_by_addr.items():
            if src == out.address:
                continue  # change back to self
            flow = out.value * contributed / total_in
            if tg.graph.has_edge(src, out.address):
                edge = tg.graph[src][out.address]
                edge["value"] += flow
                edge["txids"].append(tx.txid)
                edge["coinjoin"] = edge["coinjoin"] and coinjoin
            else:
                tg.graph.add_edge(src, out.address, value=flow, txids=[tx.txid], coinjoin=coinjoin)


def _edge_value(g: nx.DiGraph, node: str, other: str) -> float:
    out = g[node][other]["value"] if g.has_edge(node, other) else 0
    inn = g[other][node]["value"] if g.has_edge(other, node) else 0
    return out + inn


def build_subgraph(
    source: ChainSource,
    seed: str,
    sanctions: SanctionsList,
    max_depth: int = 2,
    max_txs: int = 25,
    max_fanout: int = 5,
    max_nodes: int = 150,
) -> TxGraph:
    tg = TxGraph(seed=seed)
    tg.graph.add_node(seed)
    frontier = [seed]
    for _ in range(max_depth):
        next_frontier: list[str] = []
        for node in frontier:
            if node in tg.expanded:
                continue
            tg.expanded.add(node)
            for tx in source.address_txs(node, limit=max_txs):
                add_tx_edges(tg, tx)
            if len(tg.graph) > max_nodes:
                tg.truncated = True
                return tg
            neighbors = set(tg.graph.successors(node)) | set(tg.graph.predecessors(node))
            neighbors.discard(node)

            # sanctioned neighbors need no expansion (already visible); expand biggest others
            candidates = sorted(
                (n for n in neighbors if sanctions.lookup(n) is None and n not in tg.expanded),
                key=lambda n, node=node: _edge_value(tg.graph, node, n),
                reverse=True,
            )
            if len(candidates) > max_fanout:
                tg.truncated = True
            next_frontier.extend(candidates[:max_fanout])
        frontier = next_frontier
    return tg
