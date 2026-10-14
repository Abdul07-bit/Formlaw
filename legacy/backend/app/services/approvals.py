"""
Human approval for HIGH-risk actions. The request records exactly what will happen; nothing executes
until the responsible person approves it, and the executed result is audited.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import Conflict, NotFound, Unprocessable
from ..db.base import utcnow
from ..models import ApprovalRequest, Connection, Document, Lawyer, Message
from ..policy.risk import authorize
from ..security.deps import Principal
from . import audit
from .access import get_case
from .serializers import latest_run
from .storage import storage


def _plan(db: Session, p: Principal, action: str, resource_id: str, params: dict[str, str]) -> tuple[str, str, str]:
    """Validate the request now and describe it. Returns (resource_type, summary, case_id)."""
    if action in ("connection.request", "draft.share", "case.delete"):
        case, _ = get_case(db, p, resource_id, write=True)
        if action == "connection.request":
            lawyer = db.get(Lawyer, params.get("lawyerId", ""))
            if not lawyer or lawyer.verification_status != "verified" or lawyer.profile_status != "published":
                raise Unprocessable("You can only connect with KYC-verified advocates", code="lawyer_not_verified")
            if not latest_run(db, case.id):
                raise Unprocessable("Run the case review before sharing a brief", code="no_review")
            return "case", f"Share the evidence brief for “{case.title}” with {lawyer.name} (external communication).", case.id
        if action == "draft.share":
            conn = db.get(Connection, params.get("connectionId", ""))
            if not conn or conn.case_id != case.id or conn.status != "accepted":
                raise Unprocessable("The draft can only be shared on an accepted connection for this case", code="no_connection")
            lawyer = db.get(Lawyer, conn.lawyer_id)
            return "case", f"Send the current draft for “{case.title}” to {lawyer.name if lawyer else 'counsel'} (external communication).", case.id
        return "case", f"Permanently delete the case “{case.title}” and all its documents.", case.id
    if action == "document.delete":
        doc = db.get(Document, resource_id)
        if not doc:
            raise NotFound("Document not found")
        get_case(db, p, doc.case_id, write=True)
        return "document", f"Permanently delete the document “{doc.filename}”.", doc.case_id
    raise Unprocessable("Unknown action", code="unknown_action")


def create(db: Session, p: Principal, action: str, resource_id: str, params: dict[str, str]) -> ApprovalRequest:
    policy = authorize(action, p.role, approved=True)  # role/policy check now; approval comes next
    rtype, summary, _ = _plan(db, p, action, resource_id, params)
    req = ApprovalRequest(requester_id=p.id, action=action, risk_level=policy.risk, resource_type=rtype, resource_id=resource_id,
                          payload={k: str(v)[:2000] for k, v in params.items()}, summary=summary)
    db.add(req)
    db.flush()
    audit.record(db, action=f"approval.requested:{action}", result="success", actor=p.user, resource_type=rtype,
                 resource_id=resource_id, risk=policy.risk, detail=summary)
    return req


def decide(db: Session, p: Principal, approval_id: str, approve: bool) -> tuple[ApprovalRequest, dict[str, Any] | None]:
    req = db.get(ApprovalRequest, approval_id)
    if not req or req.requester_id != p.id:
        raise NotFound("Approval request not found")
    if req.status != "pending":
        raise Conflict(f"This request is already {req.status}")
    req.decided_by, req.decided_at = p.id, utcnow()
    if not approve:
        req.status = "rejected"
        audit.record(db, action=f"approval.rejected:{req.action}", result="success", actor=p.user, resource_type=req.resource_type,
                     resource_id=req.resource_id, risk=req.risk_level)
        return req, None
    authorize(req.action, p.role, approved=True)
    _plan(db, p, req.action, req.resource_id, req.payload)  # re-validate: state may have changed since the request
    req.status = "approved"
    result = EXECUTORS[req.action](db, p, req)
    req.status = "executed"
    audit.record(db, action=req.action, result="success", actor=p.user, resource_type=req.resource_type, resource_id=req.resource_id,
                 risk=req.risk_level, detail=f"approved request {req.id}")
    return req, result


def _connect(db: Session, p: Principal, req: ApprovalRequest) -> dict[str, Any]:
    case, _ = get_case(db, p, req.resource_id, write=True)
    lawyer_id = req.payload["lawyerId"]
    existing = db.scalar(select(Connection).where(Connection.case_id == case.id, Connection.lawyer_id == lawyer_id))
    if existing:
        return {"connectionId": existing.id}
    run = latest_run(db, case.id)
    conn = Connection(case_id=case.id, client_id=p.id, lawyer_id=lawyer_id)
    db.add(conn)
    db.flush()
    docs = len(case.documents)
    db.add(Message(connection_id=conn.id, sender_role="system",
                   text=f"Case brief shared securely: {run.area if run else ''} matter · {docs} documents · evidence summary attached."))
    note = (req.payload.get("note") or "").strip()[:4000]
    if note:
        db.add(Message(connection_id=conn.id, sender_role="client", sender_id=p.id, text=note))
    return {"connectionId": conn.id}


def _share_draft(db: Session, p: Principal, req: ApprovalRequest) -> dict[str, Any]:
    conn = db.get(Connection, req.payload["connectionId"])
    run = latest_run(db, req.resource_id)
    assert conn is not None
    db.add(Message(connection_id=conn.id, sender_role="system",
                   text=f"Draft shared by the client after approval: {run.draft_title if run else 'Draft'}.\n\n{run.draft_body if run else ''}"[:4000]))
    return {"connectionId": conn.id}


def _delete_case(db: Session, p: Principal, req: ApprovalRequest) -> dict[str, Any]:
    case, _ = get_case(db, p, req.resource_id, write=True)
    for d in case.documents:
        if d.storage_location:
            storage().delete(d.storage_location)
        d.extracted_text, d.storage_location = "", None
    case.deleted_at = utcnow()
    return {"deleted": case.id}


def _delete_document(db: Session, p: Principal, req: ApprovalRequest) -> dict[str, Any]:
    doc = db.get(Document, req.resource_id)
    assert doc is not None
    if doc.storage_location:
        storage().delete(doc.storage_location)
    db.delete(doc)
    return {"deleted": req.resource_id}


EXECUTORS: dict[str, Callable[[Session, Principal, ApprovalRequest], dict[str, Any]]] = {
    "connection.request": _connect, "draft.share": _share_draft, "case.delete": _delete_case, "document.delete": _delete_document,
}
