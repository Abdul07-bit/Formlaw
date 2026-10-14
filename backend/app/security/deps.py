"""Authentication + account-role checks as FastAPI dependencies. The backend is the security boundary."""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import Forbidden, Unauthorized
from ..db.session import get_db
from ..models import Lawyer, Membership, User
from . import rate_limit
from .tokens import decode_access_token


@dataclass(frozen=True)
class Principal:
    user: User
    lawyer_id: str | None
    org_ids: frozenset[str] = field(default_factory=frozenset)  # organizations the user belongs to

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def org_id(self) -> str:
        return self.user.organization_id


def load_principal(db: Session, user: User) -> Principal:
    lawyer_id = db.scalar(select(Lawyer.id).where(Lawyer.user_id == user.id)) if user.role == "lawyer" else None
    orgs = frozenset(db.scalars(select(Membership.organization_id).where(Membership.user_id == user.id)))
    return Principal(user=user, lawyer_id=lawyer_id, org_ids=orgs)


def current_principal(request: Request, db: Session = Depends(get_db, scope="function")) -> Principal:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise Unauthorized("Sign in required")
    claims = decode_access_token(header[7:].strip())
    user = db.get(User, claims["sub"])
    if user is None or user.status != "active":
        raise Unauthorized("Account unavailable", code="account_inactive")
    if claims.get("role") != user.role:  # role changes invalidate old tokens
        raise Unauthorized("Session out of date", code="role_changed")
    request.state.actor_id = user.id
    rate_limit.hit("default", user.id)
    return load_principal(db, user)


def require_roles(*roles: str):
    def _dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.role not in roles:
            raise Forbidden("Your role cannot perform this action")
        return p
    return _dep


require_lawyer = require_roles("lawyer")
require_client = require_roles("client")
require_admin = require_roles("admin")
require_compliance = require_roles("compliance")
require_admin_or_compliance = require_roles("admin", "compliance")
