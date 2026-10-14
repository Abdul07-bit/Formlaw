"""
Agent contract. An agent is a module with a declared spec and one `run` method. Agents never call each other and
never touch the database directly: they read and write the run blackboard and reach tools only through the gateway.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from ..domain.enums import Risk

if TYPE_CHECKING:
    from .runtime.context import AgentContext
    from .runtime.state import PlanStep

StepStatus = Literal["ok", "insufficient", "failed", "skipped"]


@dataclass(frozen=True)
class AgentSpec:
    name: str
    purpose: str
    actions: tuple[str, ...]         # plan actions this agent serves, e.g. ("retrieval.search",)
    tools: frozenset[str]            # gateway allow-list
    inputs: str
    outputs: str
    failure_modes: str
    verification: str
    risk: Risk = Risk.LOW


@dataclass
class StepResult:
    status: StepStatus
    summary: str                                            # one-line reasoning summary for the lawyer (not chain-of-thought)
    signals: dict[str, Any] = field(default_factory=dict)   # observations for the orchestrator's observers
    engine: str = "deterministic"                           # model label, or deterministic


class Agent(Protocol):
    spec: AgentSpec

    def run(self, ctx: AgentContext, step: PlanStep) -> StepResult: ...
