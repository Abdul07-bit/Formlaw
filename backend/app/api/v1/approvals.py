"""High-risk action approvals and notifications."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.errors import NotFound
from ...db.base import utcnow
from ...db.session import get_db
from ...models import Approval, Notification
from ...schemas.workspace import ApprovalIn, DecisionIn
from ...security import rate_limit
from ...security.deps import Principal, current_principal
from ...services import approvals
from ...services.serializers import iso

router = APIRouter(tags=["approvals"])


def _out(a: Approval) -> dict:
    return {"id": a.id, "action": a.action, "risk": a.risk_level, "summary": a.summary, "status": a.status, "resourceId": a.resource_id,
            "caseId": a.case_id, "createdAt": iso(a.created_at), "decidedAt": iso(a.decided_at), "result": a.result}


@router.post("/approvals", status_code=201)
def request_approval(body: ApprovalIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db, scope="function")):
    rate_limit.hit("write", p.id)
    return _out(approvals.create(db, p, body.action, body.resource_id, body.params))


@router.get("/approvals")
def my_approvals(p: Principal = Depends(current_principal), db: Session = Depends(get_db, scope="function")):
    return [_out(a) for a in db.scalars(select(Approval).where(Approval.requester_id == p.id).order_by(Approval.created_at.desc()).limit(50))]


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: str, body: DecisionIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db, scope="function")):
    return _out(approvals.decide(db, p, approval_id, body.approve))


@router.get("/notifications")
def notifications(p: Principal = Depends(current_principal), db: Session = Depends(get_db, scope="function")):
    rows = db.scalars(select(Notification).where(Notification.user_id == p.id).order_by(Notification.created_at.desc()).limit(50))
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read_at is not None,
             "createdAt": iso(n.created_at)} for n in rows]


@router.post("/notifications/{nid}/read")
def read(nid: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db, scope="function")):
    n = db.get(Notification, nid)
    if not n or n.user_id != p.id:
        raise NotFound("Not found")
    n.read_at = utcnow()
    return {"ok": True}
