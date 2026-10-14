"""Build evals/datasets/wallets.json from live public data (one-off snapshot, then committed).

Cases (all small-history addresses so the 25-tx window covers their full history, which keeps
labels stable as the chain grows):

- sanctioned: addresses listed on the OFAC SDN list that have on-chain history.
- hop1: non-listed addresses one transaction away from a listed address. The label comes from a
  direct adjacency rule applied to a single transaction, independent of the graph/risk code.
- presumed_clean: random addresses from the latest block. NOT verified innocent; they are a
  base-rate negative sample. Add curated, sourced clean wallets (e.g. exchanges) to
  evals/datasets/curated_clean.json to stress false positives properly.

Usage: uv run python evals/build_dataset.py
"""

import json
import random
from datetime import date
from pathlib import Path

from btc_risk.chain.heuristics import looks_like_coinjoin
from btc_risk.config import get_settings
from btc_risk.deps import build_chain_source, load_sanctions

OUT = Path(__file__).parent / "datasets" / "wallets.json"
N_SANCTIONED, N_HOP1, N_CLEAN = 10, 10, 20
MAX_TXS = 20


def main() -> None:
    settings = get_settings()
    sanctions = load_sanctions(settings)
    chain = build_chain_source(settings)
    rng = random.Random(7)

    listed = sorted(sanctions._by_address)
    rng.shuffle(listed)

    sanctioned, hop1, seen = [], [], set()
    for addr in listed:
        if len(sanctioned) >= N_SANCTIONED and len(hop1) >= N_HOP1:
            break
        try:
            summary = chain.address_summary(addr)
        except Exception as exc:
            print("skip", addr, exc)
            continue
        if not 1 <= summary.tx_count <= MAX_TXS:
            continue
        entry = sanctions.lookup(addr)
        if len(sanctioned) < N_SANCTIONED:
            sanctioned.append(
                {
                    "address": addr,
                    "expected": "sanctioned",
                    "note": f"OFAC SDN: {entry.entity_name} ({entry.program})",
                }
            )
        if len(hop1) >= N_HOP1:
            continue
        for tx in chain.address_txs(addr, limit=MAX_TXS):
            if looks_like_coinjoin(tx):
                continue
            if addr in tx.input_addresses:
                direction, others = "received_from", [o.address for o in tx.outputs if o.address]
            elif addr in tx.output_addresses:
                direction, others = "sent_to", sorted(tx.input_addresses)
            else:
                continue
            for other in others:
                if other == addr or other in seen or sanctions.lookup(other):
                    continue
                try:
                    if chain.address_summary(other).tx_count > MAX_TXS:
                        continue
                except Exception:
                    continue
                seen.add(other)
                hop1.append(
                    {
                        "address": other,
                        "expected": "high_exposure",
                        "note": f"1-hop {direction} {addr} via tx {tx.txid}",
                    }
                )
                break
            if len(hop1) >= N_HOP1:
                break
        print(f"sanctioned={len(sanctioned)} hop1={len(hop1)}")

    tip = chain._http.get(f"{chain._base}/blocks/tip/hash").text.strip()
    block_txs = chain._get(f"/block/{tip}/txs/0")
    candidates = sorted(
        {
            o["scriptpubkey_address"]
            for t in block_txs
            for o in t["vout"]
            if o.get("scriptpubkey_address")
        }
    )
    rng.shuffle(candidates)
    clean = []
    for addr in candidates:
        if len(clean) >= N_CLEAN:
            break
        if sanctions.lookup(addr) or addr in seen:
            continue
        try:
            if chain.address_summary(addr).tx_count > MAX_TXS:
                continue
        except Exception:
            continue
        clean.append(
            {
                "address": addr,
                "expected": "low",
                "note": "random address from latest block (presumed clean, unverified)",
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "built": date.today().isoformat(),
                "cases": {"sanctioned": sanctioned, "hop1": hop1, "presumed_clean": clean},
            },
            indent=2,
        )
    )
    print(
        f"wrote {OUT}: {len(sanctioned)} sanctioned, {len(hop1)} hop1, {len(clean)} presumed clean"
    )


if __name__ == "__main__":
    main()
