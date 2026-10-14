"""
Advocate verification lifecycle. `transition` is the only code that writes `lawyers.verification_status`; every change is
checked against the allowed transitions and recorded in `verification_events` (append-only).

    NOT_STARTED ─submit─► PENDING ─provider checks─► UNDER_REVIEW ─admin─► VERIFIED ─► EXPIRED (validity ended)
                             └─ check failed ─► REJECTED            └─admin─► REJECTED   ├─► SUSPENDED ─reinstate─► VERIFIED
    REJECTED / EXPIRED ─resubmit (correction / renewal)─► PENDING                         └─ credentials changed ─► PENDING
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import Conflict
from ..db.base import utcnow
from ..domain.enums import LawyerVerification as V
from ..models import Lawyer, VerificationEvent
from ..security.deps import Principal
from . import audit

VALIDITY = timedelta(days=365)

ALLOWED: dict[str, frozenset[str]] = {
    V.NOT_STARTED: frozenset({V.PENDING}),
    V.PENDING: frozenset({V.UNDER_REVIEW, V.REJECTED}),
    V.UNDER_REVIEW: frozenset({V.VERIFIED, V.REJECTED}),
    V.VERIFIED: frozenset({V.EXPIRED, V.SUSPENDED, V.PENDING}),
    V.REJECTED: frozenset({V.PENDING}),
    V.EXPIRED: frozenset({V.PENDING}),
    V.SUSPENDED: frozenset({V.VERIFIED, V.EXPIRED, V.REJECTED}),
}


def transition(db: Session, l: Lawyer, to: str, *, actor: Principal | None, reason: str, submission_id: str | None = None) -> None:
    frm = l.verification_status
    if to not in ALLOWED.get(frm, frozenset()):
        raise Conflict(f"Verification cannot move from {frm} to {to}", code="invalid_verification_transition")
    l.verification_status = to
    if to == V.VERIFIED:
        if frm != V.SUSPENDED:  # reinstatement keeps the original validity window
            l.verified_at, l.verification_expires_at = utcnow(), utcnow() + VALIDITY
    else:
        l.profile_status = "suspended" if to == V.SUSPENDED else "draft"  # only VERIFIED profiles can be public
    db.add(VerificationEvent(lawyer_id=l.id, from_status=frm, to_status=to, actor_id=actor.id if actor else None,
                             actor_role=actor.role if actor else "system", reason=reason[:500], submission_id=submission_id))
    audit.record(db, action="verification.transition", result="success", actor=actor, resource_type="lawyer", resource_id=l.id,
                 risk="HIGH" if to in (V.VERIFIED, V.SUSPENDED, V.REJECTED) else "MEDIUM", detail=f"{frm}->{to}: {reason}"[:300])


def expire_if_due(db: Session, l: Lawyer) -> None:
    if l.verification_status in (V.VERIFIED, V.SUSPENDED) and l.verification_expires_at:
        exp = l.verification_expires_at if l.verification_expires_at.tzinfo else l.verification_expires_at.replace(tzinfo=utcnow().tzinfo)
        if exp < utcnow():
            transition(db, l, V.EXPIRED, actor=None, reason="Verification validity period ended; renewal required")


def history(db: Session, lawyer_id: str) -> list[dict]:
    rows = db.scalars(select(VerificationEvent).where(VerificationEvent.lawyer_id == lawyer_id)
                      .order_by(VerificationEvent.created_at.desc()).limit(50)).all()
    return [{"from": e.from_status, "to": e.to_status, "by": e.actor_role, "reason": e.reason,
             "at": e.created_at.isoformat() if e.created_at else None} for e in rows]
