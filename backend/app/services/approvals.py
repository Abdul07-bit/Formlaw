"""
Human approval for HIGH-risk actions:

    REQUEST → RISK CLASSIFICATION → POLICY CHECK → HUMAN APPROVAL → EXECUTE (re-validated) → VERIFY → AUDIT

The approval records exactly what will happen ("Send update 'Hearing moved' to Priya Sharma"). Nothing executes until
the responsible person approves that exact record, and the action is re-validated at execution time.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import Conflict, NotFound, Unprocessable
from ..db.base import utcnow
from ..models import Approval, CaseMember, ClientUpdate, Connection, Consent, Document, Draft, Intake, Lawyer, Notification, User
from ..policies import connection as connection_policy
from ..policies.catalog import POLICIES
from ..policies.engine import authorize
from ..repositories.access import get_case
from ..retrieval import case_index
from ..security.deps import Principal
from . import audit, conflicts
from .storage import storage


def _client_members(db: Session, case_id: str) -> list[User]:
    ids = db.scalars(select(CaseMember.user_id).where(CaseMember.case_id == case_id, CaseMember.role == "client")).all()
    return [u for u in (db.get(User, i) for i in ids) if u]


def _describe(db: Session, p: Principal, action: str, resource_id: str, params: dict[str, str]) -> tuple[str, str, str | None, str | None]:
    """Validate now and describe precisely. Returns (resource_type, summary, organization_id, case_id)."""
    if action == "client_update.send":
        a = get_case(db, p, resource_id, "case.update")
        authorize(action, p.role, case_role=a.role, approved=True)
        if not params.get("title") or not params.get("body"):
            raise Unprocessable("An update needs a title and a body")
        clients = _client_members(db, resource_id)
        if not clients:
            raise Unprocessable("This case has no client with portal access", code="no_client")
        return "case", f"Send update “{params['title'][:80]}” to {', '.join(c.name for c in clients)} via the client portal.", a.case.organization_id, a.case.id
    if action == "draft.share":
        d = db.get(Draft, resource_id)
        if not d:
            raise NotFound("Draft not found")
        a = get_case(db, p, d.case_id, "case.update")
        authorize(action, p.role, case_role=a.role, approved=True)
        if d.status != "approved":
            raise Unprocessable("Approve the draft before sharing it", code="draft_not_approved")
        clients = _client_members(db, d.case_id)
        if not clients:
            raise Unprocessable("This case has no client with portal access", code="no_client")
        return "draft", f"Share the approved draft “{d.title[:80]}” with {', '.join(c.name for c in clients)}.", d.organization_id, d.case_id
    if action == "case.delete":
        a = get_case(db, p, resource_id, "case.update")
        authorize(action, p.role, case_role=a.role, approved=True)
        return "case", f"Delete the case “{a.case.title}” ({a.case.reference}) and all its documents and findings.", a.case.organization_id, a.case.id
    if action == "document.delete":
        d = db.get(Document, resource_id)
        if not d:
            raise NotFound("Document not found")
        a = get_case(db, p, d.case_id, "case.update")
        authorize(action, p.role, case_role=a.role, approved=True)
        return "document", f"Permanently delete “{d.filename}” and the evidence derived from it.", d.organization_id, d.case_id
    if action == "connection.request":
        authorize(action, p.role, approved=True)
        policy = connection_policy.require(db, "client_requests")
        if params.get("policyVersion") != str(policy.version) or params.get("disclosureHash") != policy.disclosure_hash:
            raise Conflict("The connection policy or its disclosures changed. Review the current disclosures and try again.",
                           code="policy_changed", details=policy.public())
        intake = db.get(Intake, resource_id)
        if not intake or intake.client_id != p.id:
            raise NotFound("Matter not found")
        lawyer = db.get(Lawyer, params.get("lawyerId", ""))
        if not lawyer or lawyer.verification_status != "VERIFIED" or lawyer.profile_status != "published":
            raise Unprocessable("You can only contact verified lawyers", code="lawyer_not_verified")
        if db.scalar(select(Connection.id).where(Connection.intake_id == intake.id, Connection.lawyer_id == lawyer.id)):
            raise Conflict("You have already contacted this lawyer")
        return "intake", (f"Share your matter summary “{intake.title[:80]}” (and the number of documents you uploaded) with {lawyer.name}. "
                          "Your documents are shared only if they accept."), intake.organization_id, None
    raise Unprocessable("Unknown action", code="unknown_action")


def create(db: Session, p: Principal, action: str, resource_id: str, params: dict[str, str]) -> Approval:
    rtype, summary, org, case_id = _describe(db, p, action, resource_id, params)
    req = Approval(organization_id=org, case_id=case_id, requester_id=p.id, action=action, risk_level=POLICIES[action].risk.value,
                   resource_type=rtype, resource_id=resource_id, payload={k: str(v)[:8000] for k, v in params.items()}, summary=summary)
    db.add(req)
    db.flush()
    audit.record(db, action=f"approval.requested:{action}", result="pending", actor=p, resource_type=rtype, resource_id=resource_id,
                 risk="HIGH", organization_id=org, case_id=case_id, detail=summary)
    return req


def decide(db: Session, p: Principal, approval_id: str, approve: bool) -> Approval:
    req = db.get(Approval, approval_id)
    if not req or req.requester_id != p.id:
        raise NotFound("Approval not found")
    if req.status != "pending":
        raise Conflict("This approval has already been decided")
    req.decided_by, req.decided_at = p.id, utcnow()
    if not approve:
        req.status = "rejected"
        audit.record(db, action=f"approval.rejected:{req.action}", result="denied", actor=p, resource_type=req.resource_type,
                     resource_id=req.resource_id, risk="HIGH", organization_id=req.organization_id, case_id=req.case_id)
        return req
    _describe(db, p, req.action, req.resource_id, req.payload)  # re-validate: state may have changed since the request
    req.status, req.result = "executed", _execute(db, p, req)
    audit.record(db, action=f"approval.executed:{req.action}", result="success", actor=p, resource_type=req.resource_type,
                 resource_id=req.resource_id, risk="HIGH", organization_id=req.organization_id, case_id=req.case_id, detail=req.summary)
    return req


def _notify(db: Session, user_id: str, kind: str, title: str, body: str = "", link: str | None = None) -> None:
    db.add(Notification(user_id=user_id, kind=kind, title=title[:200], body=body[:2000], link=link))


def _execute(db: Session, p: Principal, req: Approval) -> dict[str, Any]:
    a = req.action
    if a in ("client_update.send", "draft.share"):
        if a == "draft.share":
            d = db.get(Draft, req.resource_id)
            title, body, case_id = d.title, d.body, d.case_id
            d.status = "shared"
        else:
            title, body, case_id = req.payload["title"], req.payload["body"], req.resource_id
        u = ClientUpdate(case_id=case_id, author_id=p.id, approval_id=req.id, title=title[:200], body=body)
        db.add(u)
        for c in _client_members(db, case_id):
            _notify(db, c.id, "client_update", f"Update from your lawyer: {title}", link=f"/portal/matters/{case_id}")
        db.flush()
        return {"clientUpdateId": u.id}
    if a == "case.delete":
        a_ = get_case(db, p, req.resource_id, "case.update")
        a_.case.deleted_at = utcnow()
        return {"deleted": True}
    if a == "document.delete":
        d = db.get(Document, req.resource_id)
        if d.storage_key:
            storage().delete(d.storage_key)
        case_id = d.case_id
        db.delete(d)
        db.flush()
        case_index.invalidate(case_id)
        return {"deleted": True}
    if a == "connection.request":
        intake = db.get(Intake, req.resource_id)
        lawyer = db.get(Lawyer, req.payload["lawyerId"])
        conn = Connection(intake_id=intake.id, client_id=p.id, lawyer_id=lawyer.id, client_note=req.payload.get("note", "")[:1000])
        db.add(conn)
        policy = connection_policy.effective(db)  # re-validated by _describe immediately before execution
        db.add(Consent(user_id=p.id, purpose="connection.share_intake", subject_type="intake", subject_id=intake.id,
                       recipient_type="lawyer", recipient_id=lawyer.id, policy_id=policy.policy_id, disclosures=list(policy.disclosures),
                       disclosure_hash=policy.disclosure_hash, approval_id=req.id,
                       notes="Shares the matter title, the structured intake summary, urgency, city and the number of uploaded "
                             "documents. Document contents are copied into a case only if the advocate accepts."))
        intake.status = "matched" if intake.status == "submitted" else intake.status
        # The advocate's notification must not carry the matter title: they see details only after a conflict check.
        _notify(db, lawyer.user_id, "client_request", "New client request — conflict check needed", link="/requests")
        db.flush()
        conflicts.ensure(db, conn)
        return {"connectionId": conn.id}
    raise Unprocessable("Unknown action")
