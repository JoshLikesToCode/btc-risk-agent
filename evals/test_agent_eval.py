"""Multi-agent graph vs single-agent baseline on the same wallets. Needs OPENAI_API_KEY + Postgres.

Both modes use the same tools, report schema and verifier, and the verdict is computed by code in
both, so this compares REPORT QUALITY (citations resolve, sanctions evidence is cited, no
overstated severity on clean wallets), cost and latency. It does not compare verdict accuracy.

Run: uv run pytest evals/test_agent_eval.py -m llm_eval -s
"""

import time

import pytest
from conftest import load_wallet_cases, write_results

pytestmark = pytest.mark.llm_eval
PER_GROUP = 2


@pytest.fixture(scope="module")
def cases():
    by_group: dict[str, list] = {}
    for c in load_wallet_cases():
        by_group.setdefault(c["group"], []).append(c)
    return [
        c for g in ("sanctioned", "hop1", "presumed_clean") for c in by_group.get(g, [])[:PER_GROUP]
    ]


def _run(mode, case, settings):
    from btc_risk.agents.graph import investigate
    from btc_risk.agents.single import investigate_single
    from btc_risk.deps import build_chat_model, build_deps, langfuse_config

    deps = build_deps(settings)
    run = investigate if mode == "multi" else investigate_single
    t0 = time.time()
    report = run(deps, build_chat_model(settings), case["address"], config=langfuse_config())
    return report, time.time() - t0


def test_multi_vs_single(cases, settings):
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")
    table = {}
    for mode in ("single", "multi"):
        rows = []
        for case in cases:
            report, secs = _run(mode, case, settings)
            expects_ofac = case["expected"] in ("sanctioned", "high_exposure")
            rows.append(
                {
                    "address": case["address"],
                    "group": case["group"],
                    "verification_passed": report.verification.passed,
                    "cites_ofac": any(
                        e.startswith("ofac:") for f in report.findings for e in f.evidence_ids
                    ),
                    "expects_ofac": expects_ofac,
                    "overstated": case["expected"] == "low"
                    and any(f.severity in ("high", "critical") for f in report.findings),
                    "findings": len(report.findings),
                    "seconds": round(secs, 1),
                }
            )
        exp = [r for r in rows if r["expects_ofac"]]
        table[mode] = {
            "verification_pass_rate": sum(r["verification_passed"] for r in rows) / len(rows),
            "ofac_citation_recall": (sum(r["cites_ofac"] for r in exp) / len(exp)) if exp else None,
            "overstated_on_clean": sum(r["overstated"] for r in rows),
            "mean_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 1),
            "rows": rows,
        }
    write_results("agents-latest", table)
    for mode, m in table.items():
        print(f"\n{mode}: " + ", ".join(f"{k}={v}" for k, v in m.items() if k != "rows"))
    assert table["multi"]["verification_pass_rate"] >= 0.8  # provisional
