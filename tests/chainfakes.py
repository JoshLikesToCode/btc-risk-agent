"""Helpers for building synthetic chains in tests."""

from btc_risk.chain.models import AddressSummary, Tx, TxIO


def tx(txid, ins, outs, t=0):
    """ins/outs: lists of (address, value)."""
    return Tx(
        txid=txid,
        block_time=t,
        inputs=[TxIO(address=a, value=v) for a, v in ins],
        outputs=[TxIO(address=a, value=v) for a, v in outs],
    )


class FakeChain:
    def __init__(self, txs: list[Tx]):
        self._txs = txs

    def address_summary(self, address: str) -> AddressSummary:
        mine = [t for t in self._txs if address in t.input_addresses | t.output_addresses]
        return AddressSummary(address=address, tx_count=len(mine), total_received=0, total_sent=0)

    def address_txs(self, address: str, limit: int = 25) -> list[Tx]:
        mine = [t for t in self._txs if address in t.input_addresses | t.output_addresses]
        return sorted(mine, key=lambda t: -(t.block_time or 0))[:limit]
