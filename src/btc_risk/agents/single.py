"""Single-agent baseline: one tool-calling agent with every tool, same verifier and report schema.

Exists so evals can compare it with the multi-agent graph on identical inputs.
"""

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from btc_risk.agents.graph import ANALYST_PROMPT, UNTRUSTED
from btc_risk.agents.schemas import Report, ReportDraft
from btc_risk.agents.tools import (
    build_chain_tools,
    build_intel_tools,
    build_research_tools,
    run_assessment,
)
from btc_risk.agents.verify import finalize_report, verify_draft
from btc_risk.deps import Deps

SINGLE_PROMPT = (
    "You investigate the risk of a Bitcoin wallet. Use assess_wallet first, then any other tools "
    f"you need, then write the report. {ANALYST_PROMPT} {UNTRUSTED}"
)


def investigate_single(
    deps: Deps, model: BaseChatModel, address: str, config: RunnableConfig | None = None
) -> Report:
    tools = build_chain_tools(deps) + build_intel_tools(deps)
    if deps.store is not None:
        tools += build_research_tools(deps)
    agent = create_agent(
        model, tools=tools, system_prompt=SINGLE_PROMPT, response_format=ReportDraft
    )
    result = agent.invoke(
        {"messages": [("user", f"Investigate this address: {address.strip()}")]},
        config={**(config or {}), "recursion_limit": 25},
    )
    draft: ReportDraft = result["structured_response"]
    assessment = run_assessment(deps, address)  # verdict is code-computed, as in the graph
    verification = verify_draft(draft, deps.evidence, assessment)
    return finalize_report(draft, deps.evidence, assessment, verification)
