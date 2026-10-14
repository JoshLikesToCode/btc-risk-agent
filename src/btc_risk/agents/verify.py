"""Deterministic verification of an LLM-written report against gathered evidence."""

from btc_risk.agents.schemas import Report, ReportDraft, Verification
from btc_risk.chain.risk import RiskAssessment


def verify_draft(
    draft: ReportDraft, evidence: dict[str, str], assessment: RiskAssessment
) -> Verification:
    problems: list[str] = []
    if not draft.findings:
        problems.append("report has no findings")
    cited_ofac = False
    for i, f in enumerate(draft.findings, 1):
        if not f.evidence_ids:
            problems.append(f"finding {i} cites no evidence: {f.claim[:60]!r}")
        for eid in f.evidence_ids:
            if eid not in evidence:
                problems.append(f"finding {i} cites unknown evidence id {eid!r}")
            cited_ofac = cited_ofac or eid.startswith("ofac:")
    if (assessment.direct_match or assessment.exposures) and not cited_ofac:
        problems.append("sanctions match/exposure exists but no finding cites an ofac: evidence id")
    if assessment.verdict == "low" and any(
        f.severity in ("high", "critical") for f in draft.findings
    ):
        problems.append("a finding is rated high/critical but the deterministic verdict is low")
    return Verification(passed=not problems, problems=problems)


def finalize_report(
    draft: ReportDraft,
    evidence: dict[str, str],
    assessment: RiskAssessment,
    verification: Verification,
) -> Report:
    cited = {eid for f in draft.findings for eid in f.evidence_ids if eid in evidence}
    return Report(
        address=assessment.address,
        verdict=assessment.verdict,  # set by code, never by the model
        score=assessment.score,
        summary=draft.summary,
        findings=draft.findings,
        recommended_actions=draft.recommended_actions,
        limitations=assessment.limitations,
        verification=verification,
        evidence={k: evidence[k] for k in sorted(cited)},
    )
