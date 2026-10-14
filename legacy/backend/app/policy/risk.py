"""
High-risk action policy:

    REQUEST → RISK CLASSIFICATION → POLICY CHECK → PERMISSION CHECK → HUMAN APPROVAL (if required)
            → EXECUTION → VERIFICATION → AUDIT

Every state-changing action the platform (or an agent) can take is declared here with its risk level
and the roles allowed to perform it. Anything not declared is denied.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..core.errors import ApprovalRequired, Forbidden

Risk = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class ActionPolicy:
    risk: Risk
    roles: frozenset[str]
    requires_approval: bool = False


POLICIES: dict[str, ActionPolicy] = {
    # LOW — read / search / analyse
    "case.read": ActionPolicy("LOW", frozenset({"client", "lawyer", "judge"})),
    "case.review": ActionPolicy("LOW", frozenset({"client"})),
    "research.search": ActionPolicy("LOW", frozenset({"client", "lawyer", "judge"})),
    "chat.ask": ActionPolicy("LOW", frozenset({"client", "lawyer", "judge"})),
    # MEDIUM — create / internal edits / internal notifications
    "case.create": ActionPolicy("MEDIUM", frozenset({"client"})),
    "document.upload": ActionPolicy("MEDIUM", frozenset({"client"})),
    "draft.create": ActionPolicy("MEDIUM", frozenset({"client"})),
    "profile.update": ActionPolicy("MEDIUM", frozenset({"lawyer", "judge"})),
    "lawyer_case.submit": ActionPolicy("MEDIUM", frozenset({"lawyer", "judge"})),
    "kyc.submit": ActionPolicy("MEDIUM", frozenset({"lawyer", "judge"})),
    "connection.respond": ActionPolicy("MEDIUM", frozenset({"lawyer", "judge"})),
    "message.send": ActionPolicy("MEDIUM", frozenset({"client", "lawyer", "judge"})),
    # HIGH — external communication, deletion, sensitive data, verification decisions
    "connection.request": ActionPolicy("HIGH", frozenset({"client"}), requires_approval=True),  # shares the case brief
    "draft.share": ActionPolicy("HIGH", frozenset({"client"}), requires_approval=True),
    "case.delete": ActionPolicy("HIGH", frozenset({"client"}), requires_approval=True),
    "document.delete": ActionPolicy("HIGH", frozenset({"client"}), requires_approval=True),
    "kyc.decide": ActionPolicy("HIGH", frozenset({"admin"})),
    "lawyer_case.verify": ActionPolicy("HIGH", frozenset({"admin"})),
    "security.read": ActionPolicy("HIGH", frozenset({"admin"})),
}


def authorize(action: str, role: str, *, approved: bool = False) -> ActionPolicy:
    policy = POLICIES.get(action)
    if policy is None:
        raise Forbidden(f"Action '{action}' is not permitted")  # default deny
    if role not in policy.roles:
        raise Forbidden("Your role cannot perform this action")
    if policy.requires_approval and not approved:
        raise ApprovalRequired("This is a high-risk action and needs your explicit approval",
                               details={"action": action, "risk": policy.risk})
    return policy
