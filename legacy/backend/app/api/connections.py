"""Client–lawyer connections and messages. Only the two parties of a connection can see or use it."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core.errors import Conflict, NotFound
from ...db.base import utcnow
from ...db.session import get_db
from ...models import Connection, Message
from ...policy.risk import authorize
from ...schemas.connections import (ApprovalCreateIn, ApprovalDecisionIn, ApprovalOut, ConversationOut, MessageIn, RespondIn)
from ...security import rate_limit
from ...security.deps import Principal, current_principal, require_professional
from ...services import approvals, audit
from ...services.serializers import conversation_out, iso

router = APIRouter(tags=["connections"])


def _visible(db: Session, p: Principal):
    if p.role == "client":
        return select(Connection).where(Connection.client_id == p.id)
    if p.is_professional and p.lawyer_id:
        return select(Connection).where(Connection.lawyer_id == p.lawyer_id)
    return select(Connection).where(Connection.id == "")  # admins: none


def _get(db: Session, p: Principal, conn_id: str) -> Connection:
    c = db.scalar(_visible(db, p).where(Connection.id == conn_id))
    if not c:
        raise NotFound("Conversation not found")
    return c


@router.get("/connections", response_model=list[ConversationOut])
def list_connections(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return [conversation_out(db, c) for c in db.scalars(_visible(db, p).order_by(Connection.updated_at.desc()))]


@router.post("/connections/{conn_id}/respond", response_model=ConversationOut)
def respond(conn_id: str, body: RespondIn, p: Principal = Depends(require_professional), db: Session = Depends(get_db)):
    authorize("connection.respond", p.role)
    c = _get(db, p, conn_id)
    if c.status != "requested":
        raise Conflict(f"This request is already {c.status}")
    c.status, c.quote, c.responded_at, c.updated_at = ("accepted" if body.accept else "declined"), body.quote, utcnow(), utcnow()
    text = (f"Advocate accepted the brief{f' · proposed fee ₹{body.quote:,}' if body.quote else ''}. Chat is now open." if body.accept
            else "Advocate declined this brief. FormLaw will suggest alternatives.")
    db.add(Message(connection_id=c.id, sender_role="system", text=text))
    audit.record(db, action="connection.respond", result="success", actor=p.user, resource_type="connection", resource_id=c.id, risk="MEDIUM",
                 detail="accepted" if body.accept else "declined")
    db.flush()
    return conversation_out(db, c)


@router.post("/connections/{conn_id}/messages", response_model=ConversationOut, status_code=201)
def send_message(conn_id: str, body: MessageIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    authorize("message.send", p.role)
    rate_limit.hit("write", p.id)
    c = _get(db, p, conn_id)
    if c.status != "accepted":
        raise Conflict("Messaging opens once the advocate accepts the brief", code="not_accepted")
    db.add(Message(connection_id=c.id, sender_role="client" if p.role == "client" else "lawyer", sender_id=p.id, text=body.text.strip()))
    c.updated_at = utcnow()
    db.flush()
    return conversation_out(db, c)


def _approval_out(req, result=None) -> dict:
    return {"id": req.id, "action": req.action, "risk_level": req.risk_level, "resource_type": req.resource_type,
            "resource_id": req.resource_id, "summary": req.summary, "status": req.status, "created_at": iso(req.created_at),
            "decided_at": iso(req.decided_at), "result": result}


@router.post("/approvals", response_model=ApprovalOut, status_code=201, summary="Prepare a HIGH-risk action for explicit approval")
def request_approval(body: ApprovalCreateIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rate_limit.hit("write", p.id)
    return _approval_out(approvals.create(db, p, body.action, body.resource_id, body.params))


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalOut, summary="Approve (execute) or reject a pending action")
def decide(approval_id: str, body: ApprovalDecisionIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    req, result = approvals.decide(db, p, approval_id, body.approve)
    return _approval_out(req, result)


@router.get("/notifications", summary="Derived notifications for the signed-in user")
def notifications(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    items = []
    for c in db.scalars(_visible(db, p).where(or_(Connection.status == "requested", Connection.status == "accepted"))):
        last = db.scalar(select(Message).where(Message.connection_id == c.id).order_by(Message.created_at.desc()).limit(1))
        mine = (p.role == "client" and last and last.sender_role == "client") or (p.is_professional and last and last.sender_role == "lawyer")
        if c.status == "requested" and p.is_professional:
            items.append({"type": "connection_request", "connectionId": c.id, "at": iso(c.created_at)})
        elif last and not mine:
            items.append({"type": "message", "connectionId": c.id, "at": iso(last.created_at)})
    return {"items": items}
