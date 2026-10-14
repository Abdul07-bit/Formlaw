"""Agent catalogue: plan action → agent instance. Also the source for the agent directory shown in the UI/docs."""
from __future__ import annotations

from .base import Agent
from .case_analysis.agent import CaseAnalysisAgent
from .contract_review.agent import ContractReviewAgent
from .contradiction.agent import ContradictionAgent
from .drafting.agent import DraftingAgent
from .missing_information.agent import MissingInformationAgent
from .orchestrator.composer import Composer
from .research.agent import ResearchAgent
from .retrieval.agent import RetrievalAgent
from .security.agent import SecurityAgent
from .verification.agent import VerificationAgent

AGENTS: list[Agent] = [RetrievalAgent(), SecurityAgent(), CaseAnalysisAgent(), ContractReviewAgent(), ContradictionAgent(),
                       MissingInformationAgent(), ResearchAgent(), DraftingAgent(), VerificationAgent(), Composer()]
BY_ACTION: dict[str, Agent] = {a: agent for agent in AGENTS for a in agent.spec.actions}


def directory() -> list[dict]:
    from .intake.agent import SPEC as INTAKE
    from .matching.agent import SPEC as MATCHING
    specs = [a.spec for a in AGENTS] + [INTAKE, MATCHING]
    return [{"name": s.name, "purpose": s.purpose, "actions": list(s.actions), "tools": sorted(s.tools), "inputs": s.inputs,
             "outputs": s.outputs, "failureModes": s.failure_modes, "verification": s.verification, "risk": s.risk.value} for s in specs]
