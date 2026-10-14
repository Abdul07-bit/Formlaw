"""
ToolGateway — the only way an agent reaches a tool. It enforces, independently of any model output:

* a per-agent tool allow-list (default deny; no agent has network, email or file-system tools),
* budgets: MAX_AGENT_STEPS, MAX_TOOL_CALLS, MAX_EXECUTION_SECONDS, MAX_TOKEN_BUDGET,
* bounded retries (MAX_RETRIES) for transient failures,

and records an observability trace entry (task_id, agent, tool, latency, result) for every call.
The LLM is not the security boundary; this is.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from ..core.config import AgentLimits
from ..core.errors import AgentLimitExceeded, Forbidden

log = logging.getLogger("formlaw.agents")
T = TypeVar("T")

PERMISSIONS: dict[str, frozenset[str]] = {
    "Orchestrator": frozenset({"plan", "classify"}),
    "Ingestion": frozenset({"read_case_documents"}),
    "Security Agent": frozenset({"scan_untrusted_text"}),
    "Case Review Agent": frozenset({"read_case_documents", "extract_facts"}),
    "Contract Review Agent": frozenset({"read_case_documents", "review_contract"}),
    "Retrieval Agent": frozenset({"search_case_evidence", "search_legal_corpus"}),
    "Verification Agent": frozenset({"verify_claims", "search_case_evidence", "search_legal_corpus"}),
    "Missing Info Agent": frozenset({"checklist"}),
    "Precedent Agent": frozenset({"search_lawyer_cases"}),
    "Matching Agent": frozenset({"search_verified_lawyers"}),
    "Drafting Agent": frozenset({"compose_draft"}),
    "Research Agent": frozenset({"search_legal_corpus"}),
    "Legal Agents": frozenset({"run_legal_pipeline"}),
    "Chat Agent": frozenset({"search_case_evidence", "search_legal_corpus", "llm_generate"}),
}


@dataclass
class TraceStep:
    t: float
    agent: str
    message: str
    kind: str = "ok"  # info | ok | warn | danger | adapt


@dataclass
class AgentRun:
    task_id: str
    limits: AgentLimits
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    trace: list[TraceStep] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def _check_time(self) -> None:
        if self.elapsed > self.limits.max_execution_seconds:
            raise AgentLimitExceeded("Agent run exceeded MAX_EXECUTION_SECONDS and was stopped safely")

    def log(self, agent: str, message: str, kind: str = "ok") -> None:
        self.steps += 1
        if self.steps > self.limits.max_agent_steps:
            raise AgentLimitExceeded("Agent run exceeded MAX_AGENT_STEPS and was stopped safely")
        self._check_time()
        self.trace.append(TraceStep(round(self.elapsed, 2), agent, message, kind))

    def spend_tokens(self, n: int) -> None:
        self.tokens += n
        if self.tokens > self.limits.max_token_budget:
            raise AgentLimitExceeded("Agent run exceeded MAX_TOKEN_BUDGET and was stopped safely")

    def call(self, agent: str, tool: str, fn: Callable[..., T], *args: Any, retryable: tuple[type[Exception], ...] = (), **kwargs: Any) -> T:
        if tool not in PERMISSIONS.get(agent, frozenset()):
            log.warning("tool_denied task=%s agent=%s tool=%s", self.task_id, agent, tool)
            raise Forbidden(f"{agent} is not permitted to use {tool}", code="tool_denied")
        attempts = 0
        while True:
            self.tool_calls += 1
            if self.tool_calls > self.limits.max_tool_calls:
                raise AgentLimitExceeded("Agent run exceeded MAX_TOOL_CALLS and was stopped safely")
            self._check_time()
            t0 = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                self.calls.append({"agent": agent, "tool": tool, "latency_ms": int((time.monotonic() - t0) * 1000), "result": "ok"})
                return result
            except retryable as e:
                attempts += 1
                self.calls.append({"agent": agent, "tool": tool, "latency_ms": int((time.monotonic() - t0) * 1000), "result": "retry", "error": type(e).__name__})
                if attempts > self.limits.max_retries:
                    raise
                self.log("Orchestrator", f"{tool} failed ({type(e).__name__}) - retrying ({attempts}/{self.limits.max_retries})", "adapt")
