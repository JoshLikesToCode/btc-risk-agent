"""Blockchain data access.

`ChainSource` is the interface the rest of the system depends on. `MempoolSpaceClient`
implements it over the public mempool.space REST API with a SQLite response cache so
repeated runs (and evals) are fast, polite to the API, and reproducible.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Protocol

import httpx

from btc_risk.chain.models import AddressSummary, Tx, TxIO

CACHE_TTL_SECONDS = 24 * 3600
PAGE_SIZE = 25  # mempool.space returns 25 confirmed txs per page


class ChainSource(Protocol):
    def address_summary(self, address: str) -> AddressSummary: ...

    def address_txs(self, address: str, limit: int = 25) -> list[Tx]: ...


class JsonCache:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, fetched_at REAL, body TEXT)"
        )

    def get(self, key: str, ttl: float = CACHE_TTL_SECONDS):
        row = self._db.execute("SELECT fetched_at, body FROM cache WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[0] < ttl:
            return json.loads(row[1])
        return None

    def put(self, key: str, value) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (key, time.time(), json.dumps(value))
        )
        self._db.commit()


def parse_tx(raw: dict) -> Tx:
    def io(entry: dict) -> TxIO:
        return TxIO(address=entry.get("scriptpubkey_address"), value=entry.get("value", 0))

    inputs = [io(v["prevout"]) for v in raw.get("vin", []) if v.get("prevout")]
    outputs = [io(v) for v in raw.get("vout", [])]
    return Tx(
        txid=raw["txid"],
        block_time=(raw.get("status") or {}).get("block_time"),
        inputs=inputs,
        outputs=outputs,
    )


class MempoolSpaceClient:
    def __init__(
        self,
        cache: JsonCache,
        base_url: str = "https://mempool.space/api",
        min_interval: float = 0.15,
        client: httpx.Client | None = None,
    ):
        self._cache = cache
        self._base = base_url.rstrip("/")
        self._min_interval = min_interval
        self._last_call = 0.0
        self._http = client or httpx.Client(timeout=30, headers={"User-Agent": "btc-risk-agent"})

    def _get(self, path: str):
        cached = self._cache.get(path)
        if cached is not None:
            return cached
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            try:
                response = self._http.get(f"{self._base}{path}")
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            self._last_call = time.monotonic()
            if response.status_code == 429:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            body = response.json()
            self._cache.put(path, body)
            return body
        response.raise_for_status()

    def address_summary(self, address: str) -> AddressSummary:
        raw = self._get(f"/address/{address}")
        chain = raw["chain_stats"]
        return AddressSummary(
            address=address,
            tx_count=chain["tx_count"],
            total_received=chain["funded_txo_sum"],
            total_sent=chain["spent_txo_sum"],
        )

    def address_txs(self, address: str, limit: int = 25) -> list[Tx]:
        """Most recent confirmed transactions, newest first, up to `limit`."""
        txs: list[Tx] = []
        path = f"/address/{address}/txs/chain"
        while len(txs) < limit:
            page = self._get(path)
            if not page:
                break
            txs.extend(parse_tx(raw) for raw in page)
            path = f"/address/{address}/txs/chain/{page[-1]['txid']}"
            if len(page) < PAGE_SIZE:
                break
        return txs[:limit]
