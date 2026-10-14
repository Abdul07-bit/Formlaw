"""
Compliance review. A COMPLIANCE reviewer is the only role that can approve a ConnectionPolicy; they see policies and the
compliance-related audit trail, never case content, and cannot administer users or verifications.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import AuditLog
from ...policies.engine import authorize
from ...schemas.workspace import AdminNoteIn, PolicyReviewIn
from ...security.deps import Principal, require_compliance
from ...services import connection_policies
from ...services.serializers import iso

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/connection-policies")
def list_policies(p: Principal = Depends(require_compliance), db: Session = Depends(get_db, scope="function")):
    authorize("connection_policy.read", p.role)
    return connection_policies.listing(db)


@router.post("/connection-policies/{policy_id}/review")
def review_policy(policy_id: str, body: PolicyReviewIn, p: Principal = Depends(require_compliance),
                  db: Session = Depends(get_db, scope="function")):
    """Compliance decision point. Separation of duties: the drafter can never approve their own policy."""
    authorize("connection_policy.review", p.role)
    return connection_policies.out(connection_policies.review(db, p, policy_id, body))


@router.post("/connection-policies/{policy_id}/revoke")
def revoke_policy(policy_id: str, body: AdminNoteIn, p: Principal = Depends(require_compliance),
                  db: Session = Depends(get_db, scope="function")):
    authorize("connection_policy.revoke", p.role)
    return connection_policies.out(connection_policies.revoke(db, p, policy_id, body.note))


@router.get("/audit")
def compliance_audit(p: Principal = Depends(require_compliance), db: Session = Depends(get_db, scope="function")):
    """Policy and verification decisions only (no case activity)."""
    authorize("connection_policy.read", p.role)
    rows = db.scalars(select(AuditLog).where(AuditLog.action.like("connection_policy.%") | AuditLog.action.like("verification.%"))
                      .order_by(AuditLog.created_at.desc()).limit(300)).all()
    return [{"id": r.id, "at": iso(r.created_at), "action": r.action, "result": r.result, "actorRole": r.actor_role,
             "detail": r.detail} for r in rows]
