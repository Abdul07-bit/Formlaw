"""
ToolGateway — the only way an agent reaches a tool. Independently of anything a model or document says, it enforces:

* the agent's declared tool allow-list (default deny),
* tool risk: no HIGH-risk tool is registered for agents at all, so none can be called,
* budgets (tool calls, time, tokens) and bounded retries for transient failures,

and records every call (agent, tool, risk, status, latency, tokens, model) for the run's tool_calls log.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ...domain.enums import Risk
from .budget import Budget

log = logging.getLogger("formlaw.agents.gateway")


class ToolDenied(Exception):
    pass


class TransientToolError(Exception):
    """Raised by tools for failures worth retrying (timeouts, rate limits)."""


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[..., Any]
    risk: Risk
    description: str


@dataclass
class ToolCallRecord:
    step_id: str | None
    agent: str
    tool: str
    risk: str
    status: str
    latency_ms: int
    tokens: int = 0
    model: str | None = None
    error: str | None = None


@dataclass
class Gateway:
    tools: dict[str, Tool]
    budget: Budget
    max_retries: int
    calls: list[ToolCallRecord] = field(default_factory=list)
    on_retry: Callable[[str, str, int], None] | None = None

    def call(self, *, agent: str, allowed: frozenset[str], step_id: str | None, tool: str, **kwargs: Any) -> Any:
        t = self.tools.get(tool)
        if t is None or tool not in allowed:
            self.calls.append(ToolCallRecord(step_id, agent, tool, "HIGH", "denied", 0, error="not in allow-list"))
            log.warning("tool_denied agent=%s tool=%s", agent, tool)
            raise ToolDenied(f"{agent} is not permitted to use {tool}")
        if t.risk == Risk.HIGH:  # defence in depth: HIGH tools must go through human approval, never an agent
            self.calls.append(ToolCallRecord(step_id, agent, tool, t.risk, "denied", 0, error="high risk"))
            raise ToolDenied(f"{tool} requires human approval")
        attempt = 0
        while True:
            self.budget.tool()
            t0 = time.monotonic()
            try:
                result = t.fn(**kwargs)
            except TransientToolError as e:
                attempt += 1
                self.calls.append(ToolCallRecord(step_id, agent, tool, t.risk, "retry", _ms(t0), error=str(e)[:200]))
                if attempt > self.max_retries:
                    raise
                if self.on_retry:
                    self.on_retry(agent, tool, attempt)
                continue
            except Exception as e:
                self.calls.append(ToolCallRecord(step_id, agent, tool, t.risk, "error", _ms(t0), error=type(e).__name__))
                raise
            tokens, model = 0, None
            if isinstance(result, dict) and "_tokens" in result:
                tokens, model = result.pop("_tokens"), result.pop("_model", None)
                self.budget.spend(tokens)
            self.calls.append(ToolCallRecord(step_id, agent, tool, t.risk, "ok", _ms(t0), tokens, model))
            return result


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)
