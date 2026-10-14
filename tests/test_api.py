from fastapi.testclient import TestClient

from btc_risk.api import app as api
from btc_risk.sanctions import SanctionsList
from tests.chainfakes import FakeChain, tx
from tests.test_ofac import FIXTURE

BAD = "1ExampleBase58AddressAAAAAAAAAAAAAA"
ALICE = "1AliceAddressAAAAAAAAAAAAAAAAAAAAAA"


def client(monkeypatch, key=""):
    monkeypatch.setattr(api, "_sanctions", lambda: SanctionsList.from_csv_text(FIXTURE.read_text()))
    monkeypatch.setattr(
        "btc_risk.deps.build_chain_source",
        lambda settings: FakeChain([tx("t1", [(BAD, 10_000)], [(ALICE, 9_000)], t=1)]),
    )
    monkeypatch.setenv("OPENAI_API_KEY", key)
    return TestClient(api.app)


def test_index_served(monkeypatch):
    r = client(monkeypatch).get("/")
    assert r.status_code == 200 and "BTC Risk Agent" in r.text


def test_assess_endpoint(monkeypatch):
    r = client(monkeypatch).post("/api/assess", json={"address": ALICE})
    assert r.status_code == 200 and r.json()["verdict"] == "high_exposure"


def test_invalid_address_rejected(monkeypatch):
    c = client(monkeypatch)
    assert c.post("/api/assess", json={"address": "nope"}).status_code == 422
    assert c.get("/api/investigate", params={"address": "nope"}).status_code == 422


def test_llm_endpoints_report_missing_key(monkeypatch):
    c = client(monkeypatch, key="")
    r = c.get("/api/investigate", params={"address": ALICE})
    assert r.status_code == 400 and "OPENAI_API_KEY" in r.json()["detail"]
    assert c.post("/api/ask", json={"question": "x"}).status_code == 400


def test_investigate_streams_nodes_then_report(monkeypatch):
    from tests.test_agents import good_draft, make_deps, scripted_model

    c = client(monkeypatch, key="test-key")
    model, _ = scripted_model(lambda n, p: good_draft(p))
    monkeypatch.setattr("btc_risk.deps.build_chat_model", lambda settings: model)
    monkeypatch.setattr("btc_risk.deps.build_vector_store", lambda settings: make_deps().store)
    r = c.get("/api/investigate", params={"address": ALICE})
    assert r.status_code == 200
    events = [line.split(": ", 1)[1] for line in r.text.splitlines() if line.startswith("event: ")]
    assert events[0] == "node" and events[-1] == "report" and "error" not in events
    assert '"verdict": "high_exposure"' in r.text
