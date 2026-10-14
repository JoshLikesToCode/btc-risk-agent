"""Deterministic verdict eval on labeled wallets (live chain data, cached locally).

What this measures: whether the full pipeline (SDN parsing, explorer client, graph building,
exposure logic, verdict thresholds) reproduces labels that were derived independently by simple
adjacency rules. It is an integration/regression eval, NOT a measure of real-world fraud
detection accuracy, and `presumed_clean` is unverified. See evals/build_dataset.py.

Run: uv run pytest evals/test_wallet_eval.py -m eval -s
"""

import pytest
from conftest import load_wallet_cases, write_results

from btc_risk.chain.risk import assess_address

pytestmark = pytest.mark.eval
FLAGGED = {"sanctioned", "high_exposure", "elevated"}


@pytest.fixture(scope="module")
def results(chain, sanctions):
    rows = []
    for case in load_wallet_cases():
        a = assess_address(chain, sanctions, case["address"])
        rows.append(
            {
                "group": case["group"],
                "address": case["address"],
                "expected": case["expected"],
                "verdict": a.verdict,
                "score": a.score,
                "note": case.get("note", ""),
            }
        )
    return rows


def _group(rows, name):
    return [r for r in rows if r["group"] == name]


def test_report_and_thresholds(results):
    summary = {}
    for g in sorted({r["group"] for r in results}):
        rows = _group(results, g)
        if g == "presumed_clean" or g == "curated_clean":
            hits = sum(r["verdict"] in FLAGGED for r in rows)
            summary[g] = {"n": len(rows), "false_positive_rate": hits / len(rows)}
        else:
            hits = sum(r["verdict"] == r["expected"] for r in rows)
            summary[g] = {"n": len(rows), "recall": hits / len(rows)}
    write_results("wallets-latest", {"summary": summary, "rows": results})
    print("\n" + "\n".join(f"{g:>15}: {m}" for g, m in summary.items()))
    for r in results:
        if (
            (r["expected"] == "low") != (r["verdict"] not in FLAGGED)
            or r["verdict"] != r["expected"]
            and r["group"] in ("sanctioned", "hop1")
        ):
            print(
                f"  MISS {r['group']} {r['address']} expected={r['expected']} got={r['verdict']} ({r['note']})"
            )

    assert summary["sanctioned"]["recall"] == 1.0
    assert summary["hop1"]["recall"] >= 0.8  # provisional threshold
    assert summary["presumed_clean"]["false_positive_rate"] <= 0.1  # provisional threshold
