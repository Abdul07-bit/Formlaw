"""
Action catalogue. Every state-changing or data-reading action FormLaw (or an agent) can take is declared here with
its risk, the account roles allowed, the case roles allowed (for case-scoped actions) and whether a human approval is
required. Anything not declared is denied.

    REQUEST → RISK CLASSIFICATION → POLICY CHECK → (HUMAN APPROVAL) → EXECUTE → VERIFY → AUDIT
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import Risk

LAWYER, CLIENT, ADMIN, COMPLIANCE = "lawyer", "client", "admin", "compliance"
TEAM = frozenset({"lead", "member"})
TEAM_READ = frozenset({"lead", "member", "viewer"})
LEAD = frozenset({"lead"})


@dataclass(frozen=True)
class ActionPolicy:
    risk: Risk
    roles: frozenset[str]
    case_roles: frozenset[str] | None = None  # None = not case-scoped
    requires_approval: bool = False
    description: str = ""


def _p(risk: Risk, roles: set[str], case_roles: frozenset[str] | None = None, approval: bool = False, d: str = "") -> ActionPolicy:
    return ActionPolicy(risk, frozenset(roles), case_roles, approval, d)


POLICIES: dict[str, ActionPolicy] = {
    # LOW — read, search, analyse
    "case.read": _p(Risk.LOW, {LAWYER}, TEAM_READ),
    "case.list": _p(Risk.LOW, {LAWYER}),
    "agent.run": _p(Risk.LOW, {LAWYER}, TEAM, d="Search, retrieve, analyse, summarise"),
    "research.search": _p(Risk.LOW, {LAWYER}),
    "portal.read": _p(Risk.LOW, {CLIENT}, frozenset({"client"})),
    # MEDIUM — internal writes
    "case.create": _p(Risk.MEDIUM, {LAWYER}),
    "case.update": _p(Risk.MEDIUM, {LAWYER}, TEAM),
    "case.member.add": _p(Risk.MEDIUM, {LAWYER}, LEAD),
    "document.upload": _p(Risk.MEDIUM, {LAWYER}, TEAM),
    "portal.document.upload": _p(Risk.MEDIUM, {CLIENT}, frozenset({"client"})),
    "knowledge.review": _p(Risk.MEDIUM, {LAWYER}, TEAM, d="Accept / reject AI findings"),
    "draft.write": _p(Risk.MEDIUM, {LAWYER}, TEAM),
    "draft.approve": _p(Risk.MEDIUM, {LAWYER}, TEAM),
    "finding.save": _p(Risk.MEDIUM, {LAWYER}, TEAM),
    "task.write": _p(Risk.MEDIUM, {LAWYER}, TEAM),
    "message.send": _p(Risk.MEDIUM, {LAWYER, CLIENT}, frozenset({"lead", "member", "client"})),
    "profile.update": _p(Risk.MEDIUM, {LAWYER}),
    "verification.submit": _p(Risk.MEDIUM, {LAWYER}),
    "intake.create": _p(Risk.MEDIUM, {CLIENT}),
    "connection.respond": _p(Risk.MEDIUM, {LAWYER}),
    # HIGH — external communication, sharing, deletion: human approval required
    "client_update.send": _p(Risk.HIGH, {LAWYER}, TEAM, approval=True, d="Send information to the client"),
    "draft.share": _p(Risk.HIGH, {LAWYER}, TEAM, approval=True, d="Share a draft outside the legal team"),
    "case.delete": _p(Risk.HIGH, {LAWYER}, LEAD, approval=True, d="Delete a case and all its data"),
    "document.delete": _p(Risk.HIGH, {LAWYER}, TEAM, approval=True, d="Delete a case document"),
    "connection.request": _p(Risk.HIGH, {CLIENT}, approval=True, d="Share the intake summary with a lawyer"),
    # HIGH — platform administration (no case content)
    "verification.decide": _p(Risk.HIGH, {ADMIN}),
    "connection_policy.read": _p(Risk.LOW, {ADMIN, COMPLIANCE}),
    "connection_policy.draft": _p(Risk.HIGH, {ADMIN}, d="Propose a client-advocate connection policy (inactive until reviewed)"),
    "connection_policy.review": _p(Risk.HIGH, {COMPLIANCE}, d="Compliance decision: approve or reject a connection policy"),
    "connection_policy.revoke": _p(Risk.HIGH, {ADMIN, COMPLIANCE}, d="Switch connection features off (only ever reduces exposure)"),
    "firm.register.read": _p(Risk.LOW, {LAWYER}, d="Firm owners/admins: matter metadata only, never content"),
    "security.read": _p(Risk.HIGH, {ADMIN}),
    "audit.read": _p(Risk.HIGH, {ADMIN}),
}

# Actions agents may ever trigger themselves. Everything HIGH is absent on purpose.
AGENT_ACTIONS = frozenset({"agent.run", "research.search", "draft.write", "finding.save"})
