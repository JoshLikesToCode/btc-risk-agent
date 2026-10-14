"""Deterministic on-chain heuristics. Pure functions over transactions; no network, no LLM.

These are heuristics, not proof: common-input ownership breaks under CoinJoin, and peeling
chains also describe ordinary wallet behaviour. Callers should treat results as signals.
"""

from collections import Counter

from btc_risk.chain.models import Tx

PEEL_RATIO = 0.2  # the "peeled" output must be under this fraction of the larger output


def looks_like_coinjoin(tx: Tx) -> bool:
    """>=3 inputs from distinct addresses and >=3 outputs of identical value."""
    if len(tx.input_addresses) < 3:
        return False
    counts = Counter(o.value for o in tx.outputs if o.address)
    return any(n >= 3 for n in counts.values())


def cluster_by_common_input(txs: list[Tx]) -> list[set[str]]:
    """Common-input-ownership clusters (union-find), skipping CoinJoin-like transactions."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for tx in txs:
        addrs = sorted(tx.input_addresses)
        if len(addrs) < 2 or looks_like_coinjoin(tx):
            continue
        root = find(addrs[0])
        for a in addrs[1:]:
            parent[find(a)] = root
    groups: dict[str, set[str]] = {}
    for a in list(parent):
        groups.setdefault(find(a), set()).add(a)
    return [g for g in groups.values() if len(g) > 1]


def _peel_step(tx: Tx) -> str | None:
    """If tx looks like a peel (1 input address, 2 outputs, one small), return the big output address."""
    outs = [o for o in tx.outputs if o.address]
    if len(tx.input_addresses) != 1 or len(outs) != 2:
        return None
    small, big = sorted(outs, key=lambda o: o.value)
    if big.value <= 0 or small.value / big.value >= PEEL_RATIO:
        return None
    return big.address


def find_peeling_chains(txs: list[Tx], min_length: int = 3) -> list[list[str]]:
    """Chains of peel transactions where each big output is spent by the next peel.

    Returns lists of txids, oldest first. Only sees transactions in `txs`.
    """
    by_input_addr: dict[str, list[Tx]] = {}
    for tx in txs:
        if len(tx.input_addresses) == 1:
            by_input_addr.setdefault(next(iter(tx.input_addresses)), []).append(tx)

    peels = {tx.txid: tx for tx in txs if _peel_step(tx)}
    has_predecessor: set[str] = set()
    nxt: dict[str, str] = {}
    for txid, tx in peels.items():
        big_addr = _peel_step(tx)
        followers = [
            t
            for t in by_input_addr.get(big_addr, [])
            if t.txid in peels and t.txid != txid and (t.block_time or 0) >= (tx.block_time or 0)
        ]
        if followers:
            follower = min(followers, key=lambda t: t.block_time or 0)
            nxt[txid] = follower.txid
            has_predecessor.add(follower.txid)

    chains = []
    for start in peels:
        if start in has_predecessor:
            continue
        chain, seen, cur = [start], {start}, start
        while cur in nxt and nxt[cur] not in seen:
            cur = nxt[cur]
            chain.append(cur)
            seen.add(cur)
        if len(chain) >= min_length:
            chains.append(chain)
    return chains
