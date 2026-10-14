import httpx
import respx

from btc_risk.chain.explorer import JsonCache, MempoolSpaceClient, parse_tx
from btc_risk.chain.heuristics import (
    cluster_by_common_input,
    find_peeling_chains,
    looks_like_coinjoin,
)
from btc_risk.chain.risk import assess_address
from btc_risk.sanctions import SanctionsList
from tests.chainfakes import FakeChain, tx
from tests.test_ofac import FIXTURE

BAD = "1ExampleBase58AddressAAAAAAAAAAAAAA"  # listed in the fixture SDN CSV
SDN = SanctionsList.from_csv_text(FIXTURE.read_text())


def test_direct_match_is_sanctioned():
    chain = FakeChain([tx("t1", [("x", 1000)], [(BAD, 900)])])
    a = assess_address(chain, SDN, BAD)
    assert a.verdict == "sanctioned" and a.score == 100 and a.direct_match
    assert any(k.startswith("ofac:") for k in a.evidence)


def test_one_hop_exposure_received_from():
    chain = FakeChain([tx("t1", [(BAD, 10_000)], [("alice", 9_000)], t=1)])
    a = assess_address(chain, SDN, "alice")
    assert a.verdict == "high_exposure"
    e = a.exposures[0]
    assert (e.hops, e.direction, e.via_coinjoin) == (1, "received_from", False)
    assert "tx:t1" in a.evidence


def test_two_hop_exposure_is_elevated():
    chain = FakeChain(
        [
            tx("t1", [(BAD, 10_000)], [("mid", 9_000)], t=1),
            tx("t2", [("mid", 9_000)], [("alice", 8_000)], t=2),
        ]
    )
    a = assess_address(chain, SDN, "alice")
    assert a.verdict == "elevated" and a.exposures[0].hops == 2


def test_coinjoin_link_is_discounted():
    ins = [(BAD, 100_000), ("p2", 100_000), ("p3", 100_000)]
    outs = [("alice", 99_000), ("o2", 99_000), ("o3", 99_000)]
    chain = FakeChain([tx("cj", ins, outs, t=1)])
    assert looks_like_coinjoin(chain._txs[0])
    a = assess_address(chain, SDN, "alice")
    assert a.exposures and a.exposures[0].via_coinjoin
    assert a.verdict == "elevated"  # not high_exposure


def test_clean_address_is_low():
    chain = FakeChain([tx("t1", [("bob", 5_000)], [("alice", 4_000), ("bob", 900)], t=1)])
    a = assess_address(chain, SDN, "alice")
    assert a.verdict == "low" and a.exposures == []


def test_unknown_address_is_insufficient_data():
    a = assess_address(FakeChain([]), SDN, "ghost")
    assert a.verdict == "insufficient_data"


def test_peeling_chain_detected():
    txs = [
        tx("p1", [("a", 1_000_000)], [("b", 950_000), ("x1", 40_000)], t=1),
        tx("p2", [("b", 950_000)], [("c", 900_000), ("x2", 40_000)], t=2),
        tx("p3", [("c", 900_000)], [("d", 850_000), ("x3", 40_000)], t=3),
    ]
    assert find_peeling_chains(txs) == [["p1", "p2", "p3"]]
    assert find_peeling_chains(txs[:2]) == []  # below min_length


def test_common_input_clustering_skips_coinjoin():
    txs = [
        tx("m1", [("a", 5), ("b", 5)], [("z", 9)]),
        tx("m2", [("b", 5), ("c", 5)], [("y", 9)]),
        tx("cj", [("d", 5), ("e", 5), ("f", 5)], [("g", 4), ("h", 4), ("i", 4)]),
    ]
    clusters = cluster_by_common_input(txs)
    assert clusters == [{"a", "b", "c"}]


RAW_TX = {
    "txid": "abc",
    "status": {"confirmed": True, "block_time": 1700000000},
    "vin": [{"prevout": {"scriptpubkey_address": "in1", "value": 1000}}, {"is_coinbase": True}],
    "vout": [{"scriptpubkey_address": "out1", "value": 900}, {"value": 0}],
}


def test_parse_tx_handles_coinbase_and_opreturn():
    t = parse_tx(RAW_TX)
    assert [i.address for i in t.inputs] == ["in1"]
    assert [o.address for o in t.outputs] == ["out1", None]
    assert t.block_time == 1700000000


@respx.mock
def test_client_paginates_and_caches():
    first = [{**RAW_TX, "txid": f"t{i}"} for i in range(25)]
    second = [{**RAW_TX, "txid": "t25"}]
    r1 = respx.get("https://x/api/address/a/txs/chain").mock(
        return_value=httpx.Response(200, json=first)
    )
    r2 = respx.get("https://x/api/address/a/txs/chain/t24").mock(
        return_value=httpx.Response(200, json=second)
    )
    client = MempoolSpaceClient(JsonCache(":memory:"), base_url="https://x/api", min_interval=0)
    assert len(client.address_txs("a", limit=100)) == 26
    client.address_txs("a", limit=100)  # served from cache
    assert r1.call_count == 1 and r2.call_count == 1
