"""
Security Agent — detects prompt injection, tool-abuse and exfiltration attempts in the request and in retrieved
evidence. It is NOT the security boundary: the policy engine, case-scoped repositories and the tool gateway enforce
security deterministically whether or not this agent notices anything.
"""
from __future__ import annotations

from ..base import AgentSpec, StepResult
from ..runtime.state import SecurityItem

SPEC = AgentSpec(
    name="Security Agent",
    purpose="Keep untrusted instructions out of model context and tell the lawyer when a document tries to instruct the AI",
    actions=("security.scan_request", "security.screen"),
    tools=frozenset({"scan_text"}),
    inputs="the lawyer's request; retrieved evidence",
    outputs="security findings (kind, source, snippet); flagged chunks excluded from prompts",
    failure_modes="false negatives are contained by the gateway (no dangerous tools) and output verification",
    verification="deterministic pattern scan; decisions enforced by policy code, not by this agent",
)


class SecurityAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        if step.action == "security.scan_request":
            f = ctx.tool("scan_text", text=ctx.state.goal)
            if f.flagged:
                ctx.board.security.append(SecurityItem(f.kind, "chat request", f.snippet, action="request_refused"))
                return StepResult("failed", "The request asks FormLaw to change its rules or move data — refused", {"injection": sorted(f.kinds)})
            return StepResult("ok", "Request checked — no embedded instructions")
        known = {s.chunk_id for s in ctx.board.security}
        new = []
        for e in ctx.board.evidence.values():
            if e.flagged and e.chunk_id not in known:
                f = ctx.tool("scan_text", text=e.text)
                item = SecurityItem(f.kind if f.flagged else e.security_flags[0], e.document_name, f.snippet or e.text[:200], e.chunk_id)
                ctx.board.security.append(item)
                new.append(item)
        if not new:
            return StepResult("ok", "No instruction-like text in retrieved evidence")
        docs = sorted({i.source for i in new})
        return StepResult("ok", f"Blocked {len(new)} instruction-like passage(s) in {', '.join(docs)} from AI context; kept as evidence",
                          {"security_findings": len(new), "documents": docs})
