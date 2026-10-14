from typing import Literal

from pydantic import BaseModel, Field

from btc_risk.chain.risk import Verdict


class Plan(BaseModel):
    """Supervisor's plan for the specialist agents. Empty lists mean 'skip that specialist'."""

    chain_tasks: list[str] = Field(
        default_factory=list,
        description="Concrete on-chain follow-ups, e.g. 'assess counterparty <address>'. Max 3.",
    )
    intel_tasks: list[str] = Field(
        default_factory=list,
        description="Sanctions/intel lookups on specific addresses or entities. Max 3.",
    )
    research_questions: list[str] = Field(
        default_factory=list,
        description="Questions for the typology document corpus, e.g. 'how are peeling chains used?'. Max 3.",
    )


class Finding(BaseModel):
    claim: str = Field(description="One factual statement about the wallet.")
    severity: Literal["info", "low", "medium", "high", "critical"]
    evidence_ids: list[str] = Field(
        description="Evidence ids (tx:..., ofac:..., doc:...) that support the claim. Required."
    )


class ReportDraft(BaseModel):
    """What the LLM writes. The verdict and score are NOT chosen by the model."""

    summary: str = Field(
        description="2-4 sentence plain-language summary for a compliance analyst."
    )
    findings: list[Finding]
    recommended_actions: list[str]


class Verification(BaseModel):
    passed: bool
    problems: list[str] = Field(default_factory=list)


class Report(BaseModel):
    address: str
    verdict: Verdict
    score: int
    summary: str
    findings: list[Finding]
    recommended_actions: list[str]
    limitations: list[str]
    verification: Verification
    evidence: dict[str, str]  # only the evidence ids the findings cite
