"""
Case-level authorisation. Every case read/write goes through here, so isolation rules live in one place:

* the case owner (within their organisation) can read and write;
* a lawyer can read a case's brief only through a connection the client approved (requested or accepted),
  and never its raw document text;
* admins administer the platform but cannot read client case files (least privilege);
* anyone else gets 404, so case IDs cannot be probed (no IDOR/BOLA enumeration).
"""
from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFound
from ..models import Case, Connection
from ..security.deps import Principal

Access = Literal["owner", "counsel"]


def case_access(db: Session, p: Principal, case: Case) -> Access | None:
    if case.deleted_at is not None:
        return None
    if p.role == "client" and case.owner_id == p.id and case.organization_id == p.user.organization_id:
        return "owner"
    if p.is_professional and p.lawyer_id:
        accepted = db.scalar(select(Connection.id).where(
            Connection.case_id == case.id, Connection.lawyer_id == p.lawyer_id, Connection.status.in_(("requested", "accepted"))))
        if accepted:
            return "counsel"
    return None


def get_case(db: Session, p: Principal, case_id: str, *, write: bool = False) -> tuple[Case, Access]:
    case = db.get(Case, case_id)
    access = case_access(db, p, case) if case else None
    if case is None or access is None or (write and access != "owner"):
        raise NotFound("Case not found")
    return case, access
