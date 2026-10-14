"""Deterministic policy decisions. The model never decides what is allowed; this module does."""
from __future__ import annotations

from ..core.errors import ApprovalRequired, Forbidden
from .catalog import POLICIES, ActionPolicy


def authorize(action: str, role: str, *, case_role: str | None = None, approved: bool = False) -> ActionPolicy:
    policy = POLICIES.get(action)
    if policy is None:
        raise Forbidden(f"Action '{action}' is not permitted", code="action_not_declared")  # default deny
    if role not in policy.roles:
        raise Forbidden("Your role cannot perform this action")
    if policy.case_roles is not None and case_role not in policy.case_roles:
        raise Forbidden("Your access to this case does not allow this action")
    if policy.requires_approval and not approved:
        raise ApprovalRequired("This is a high-risk action and needs explicit approval",
                               details={"action": action, "risk": policy.risk.value})
    return policy
