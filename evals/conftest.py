import json
from pathlib import Path

import pytest

from btc_risk.config import get_settings

DATASETS = Path(__file__).parent / "datasets"
RESULTS = Path(__file__).parent / "results"


def load_wallet_cases() -> list[dict]:
    data = json.loads((DATASETS / "wallets.json").read_text())
    cases = [{**c, "group": g} for g, items in data["cases"].items() for c in items]
    curated = DATASETS / "curated_clean.json"
    if curated.exists():
        cases += [
            {**c, "group": "curated_clean", "expected": "low"}
            for c in json.loads(curated.read_text())
        ]
    return cases


def write_results(name: str, payload: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str))


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def sanctions(settings):
    from btc_risk.deps import load_sanctions

    return load_sanctions(settings)


@pytest.fixture(scope="session")
def chain(settings):
    from btc_risk.deps import build_chain_source

    return build_chain_source(settings)
