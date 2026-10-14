from btc_risk.agents.schemas import Report
from btc_risk.chain.risk import RiskAssessment


def format_assessment(a: RiskAssessment) -> str:
    lines = [f"{a.address}", f"  verdict: {a.verdict}   score: {a.score}/100"]
    if a.direct_match:
        lines.append("  DIRECT OFAC SDN MATCH")
    for e in a.exposures[:5]:
        cj = " (via CoinJoin, discounted)" if e.via_coinjoin else ""
        lines.append(
            f"  exposure: {e.hops}-hop {e.direction} {e.sanctioned_address} [{e.entity_name}; {e.program}]{cj}"
        )
        lines.append(f"    txs: {', '.join(t[:12] + '…' for t in e.txids)}")
    for s in a.signals:
        lines.append(f"  signal: {s.kind}: {s.description}")
    lines.append(
        f"  coverage: {a.nodes} addresses, {a.txs_analyzed} txs analyzed"
        f"{' (truncated)' if a.truncated else ''}; address has {a.tx_count_total} txs total"
    )
    lines += [f"  note: {n}" for n in a.limitations]
    return "\n".join(lines)


def format_report(r: Report) -> str:
    lines = [
        f"{r.address}",
        f"  verdict: {r.verdict}   score: {r.score}/100",
        "",
        f"  {r.summary}",
        "",
    ]
    for f in r.findings:
        lines.append(f"  [{f.severity}] {f.claim}")
        lines.append(f"      evidence: {', '.join(f.evidence_ids)}")
    if r.recommended_actions:
        lines += ["", "  recommended:"] + [f"   - {a}" for a in r.recommended_actions]
    lines += ["", "  limitations:"] + [f"   - {n}" for n in r.limitations]
    v = r.verification
    lines.append(f"\n  verification: {'passed' if v.passed else 'FAILED'}")
    lines += [f"   - {p}" for p in v.problems]
    return "\n".join(lines)
