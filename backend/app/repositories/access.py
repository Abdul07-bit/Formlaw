"""
Case-level authorisation in one place.

* A lawyer can open a case only if they belong to the case's organization AND are a member of the case.
  Being an organization owner/admin grants NO case access: firm management sees a metadata-only matter register
  (GET /firm/matters) and must be added to a matter by its lead like anyone else.
* A client reaches a case only as a `client` member, and only through portal projections.
* Admins administer the platform; they never read case content (least privilege).
* Anyone else gets 404 — case ids cannot be probed (no IDOR/BOLA oracle).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFound
from ..models import Case, CaseMember
from ..policies.engine import authorize
from ..security.deps import Principal


@dataclass(frozen=True)
class CaseAccess:
    case: Case
    role: str  # lead | member | viewer | client

    @property
    def scope(self) -> tuple[str, str]:
        """(organization_id, case_id) — every repository query filters on both."""
        return self.case.organization_id, self.case.id


def case_role(db: Session, p: Principal, case: Case) -> str | None:
    if case.deleted_at is not None:
        return None
    member_role = db.scalar(select(CaseMember.role).where(CaseMember.case_id == case.id, CaseMember.user_id == p.id))
    if p.role == "client":
        return "client" if member_role == "client" else None
    if p.role != "lawyer" or case.organization_id not in p.org_ids:
        return None
    return member_role if member_role and member_role != "client" else None


def get_case(db: Session, p: Principal, case_id: str, action: str = "case.read") -> CaseAccess:
    case = db.get(Case, case_id)
    role = case_role(db, p, case) if case else None
    if case is None or role is None:
        raise NotFound("Case not found")
    try:
        authorize(action, p.role, case_role=role)
    except Exception:
        # Wrong kind of access (e.g. a client calling a lawyer endpoint) looks identical to "does not exist".
        if role == "client" or action.startswith("portal."):
            raise NotFound("Case not found") from None
        raise
    return CaseAccess(case, role)
