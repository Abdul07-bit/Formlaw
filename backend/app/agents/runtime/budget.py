"""Execution limits. Exceeding any of them stops the run safely; verified partial results are still returned."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ...core.config import AgentLimits


class BudgetExceeded(Exception):
    def __init__(self, which: str):
        super().__init__(f"{which} limit reached")
        self.which = which


@dataclass
class Budget:
    limits: AgentLimits
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    replans: int = 0
    # Headroom granted once, after a limit is hit, to finish from evidence already gathered (no model calls).
    extra_seconds: float = 0
    extra_steps: int = 0
    extra_tools: int = 0

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    def check_time(self) -> None:
        if time.monotonic() - self.started > self.limits.max_execution_seconds + self.extra_seconds:
            raise BudgetExceeded("MAX_EXECUTION_SECONDS")

    def step(self) -> None:
        self.steps += 1
        if self.steps > self.limits.max_agent_steps + self.extra_steps:
            raise BudgetExceeded("MAX_AGENT_STEPS")
        self.check_time()

    def tool(self) -> None:
        self.tool_calls += 1
        if self.tool_calls > self.limits.max_tool_calls + self.extra_tools:
            raise BudgetExceeded("MAX_TOOL_CALLS")
        self.check_time()

    def spend(self, tokens: int) -> None:
        self.tokens += tokens
        if self.tokens > self.limits.max_token_budget:
            raise BudgetExceeded("MAX_TOKEN_BUDGET")

    def grace(self, seconds: float = 15, steps: int = 6, tools: int = 12) -> None:
        """Allow a bounded wrap-up after a limit was reached (deterministic verification and composition only)."""
        self.extra_seconds = max(0.0, time.monotonic() - self.started - self.limits.max_execution_seconds) + seconds
        self.extra_steps = max(0, self.steps - self.limits.max_agent_steps) + steps
        self.extra_tools = max(0, self.tool_calls - self.limits.max_tool_calls) + tools

    def can_replan(self) -> bool:
        return self.replans < self.limits.max_replans
