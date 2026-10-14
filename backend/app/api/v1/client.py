"""
Client portal + intake/matching + lawyer requests + lawyer↔client messaging.

Clients only ever receive client-safe projections: matter status, lawyer-approved updates, messages and their own
uploads. Agent traces, claims, research, drafts and lawyer notes are never exposed here.

Matching and client→advocate requests are advocate discovery, restricted by Indian professional rules. They run only when
the current ConnectionPolicy (policies/connection.py) enables them; the default is off.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...agents.intake.agent import structure
from ...agents.matching.agent import DISCLAIMER, Candidate, match
from ...core.config import get_settings
from ...core.errors import Conflict, NotFound, TooLarge, Unprocessable
from ...db.base import utcnow
from ...db.session import get_db
from ...ingestion.case_documents import ingest, sha256
from ...models import (Case, CaseMember, ClientUpdate, Connection, Document, Intake, IntakeDocument, Lawyer, LawyerMatch,
                       LawyerPracticeArea, Message, Notification, User)
from ...policies import connection as connection_policy
from ...policies.engine import authorize
from ...repositories.access import get_case
from ...retrieval import case_index
from ...schemas.workspace import ConflictDecisionIn, ConnectIn, IntakeIn, IntakePatch, MessageIn, RespondIn
from ...security import rate_limit
from ...security.deps import Principal, require_client, require_lawyer
from ...security.files import validate_upload
from ...services import approvals, audit, client_review, conflicts
from ...services.serializers import document_out, iso, lawyer_out
from ...services.storage import storage
from .cases import next_reference

router = APIRouter(tags=["client"])


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


def _intake_out(db: Session, i: Intake) -> dict:
    docs = db.scalars(select(IntakeDocument).where(IntakeDocument.intake_id == i.id)).all()
    conns = db.scalars(select(Connection).where(Connection.intake_id == i.id)).all()
    newest = max((_aware(d.created_at) for d in docs), default=None)
    stale = bool(i.review) and newest is not None and _aware(i.reviewed_at) is not None and newest > _aware(i.reviewed_at)
    return {"id": i.id, "title": i.title, "description": i.description, "status": i.status, "matterType": i.matter_type,
            "jurisdiction": i.jurisdiction, "city": i.city, "urgency": i.urgency, "structured": i.structured, "createdAt": iso(i.created_at),
            "declaredParties": i.declared_parties or [], "budgetMax": i.budget_max,
            "review": i.review, "reviewedAt": iso(i.reviewed_at), "reviewStale": stale or (bool(i.review) and len(docs) != i.review.get("summary", {}).get("documents")),
            "securityFlags": i.security_flags,
            "documents": [{"id": d.id, "filename": d.filename, "size": d.size, "uploadedAt": iso(d.created_at)} for d in docs],
            "connections": [{"id": c.id, "lawyerId": c.lawyer_id, "lawyerName": (db.get(Lawyer, c.lawyer_id) or Lawyer(name="")).name,
                             "status": c.status, "caseId": c.case_id, "lawyerNote": c.lawyer_note} for c in conns]}


def _my_intake(db: Session, p: Principal, intake_id: str) -> Intake:
    i = db.get(Intake, intake_id)
    if not i or i.client_id != p.id:
        raise NotFound("Matter not found")
    return i


@router.post("/intakes", status_code=201)
def create_intake(body: IntakeIn, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    authorize("intake.create", p.role)
    rate_limit.hit("agent", p.id)
    data, engine, flags = structure(body.description, body.answers)
    i = Intake(client_id=p.id, organization_id=p.org_id, title=body.title, description=body.description, answers=body.answers,
               structured=data | {"engine": engine}, matter_type=data["legal_domain"], jurisdiction=data.get("jurisdiction", ""),
               city=body.city or p.user.city or "", urgency=data["urgency"], language=body.language, security_flags=flags,
               declared_parties=list(dict.fromkeys(x.strip() for x in body.other_parties if x.strip())), budget_max=body.budget_max)
    db.add(i)
    db.flush()
    audit.record(db, action="intake.create", result="success", actor=p, resource_type="intake", resource_id=i.id, risk="MEDIUM",
                 agent="Client Intake Agent", detail=f"domain={i.matter_type} engine={engine}")
    return _intake_out(db, i)


@router.get("/intakes")
def my_intakes(p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    return [_intake_out(db, i) for i in db.scalars(select(Intake).where(Intake.client_id == p.id).order_by(Intake.created_at.desc()))]


@router.get("/intakes/{intake_id}")
def get_intake(intake_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    return _intake_out(db, _my_intake(db, p, intake_id))


@router.post("/intakes/{intake_id}/documents", status_code=201)
async def intake_documents(intake_id: str, files: list[UploadFile] = File(...), p: Principal = Depends(require_client),
                           db: Session = Depends(get_db, scope="function")):
    i = _my_intake(db, p, intake_id)
    rate_limit.hit("upload", p.id, cost=len(files))
    limit = get_settings().max_upload_bytes
    for f in files[:10]:
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise TooLarge("File too large")
        v = validate_upload(f.filename or "", f.content_type, data, limit)
        db.add(IntakeDocument(intake_id=i.id, filename=v.display_name, mime_type=v.content_type, size=len(data),
                              content_hash=sha256(data), storage_key=storage().put(data)))
    db.flush()
    return _intake_out(db, i)


@router.patch("/intakes/{intake_id}")
def update_intake(intake_id: str, body: IntakePatch, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    i = _my_intake(db, p, intake_id)
    data = body.model_dump(exclude_unset=True)
    if "budget_max" in data:
        i.budget_max = data["budget_max"]
    if data.get("other_parties") is not None:
        if db.scalar(select(Connection.id).where(Connection.intake_id == i.id)):
            # Conflict checks already ran on the names the advocate was given; changing them later would bypass that.
            raise Conflict("Other parties can't be changed after you've contacted an advocate", code="parties_locked")
        i.declared_parties = list(dict.fromkeys(x.strip() for x in data["other_parties"] if x.strip()))
    db.flush()
    return _intake_out(db, i)


@router.delete("/intakes/{intake_id}/documents/{document_id}")
def delete_intake_document(intake_id: str, document_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    """Clients control their own uploads. Copies already in an advocate's case are the advocate's record and stay there."""
    i = _my_intake(db, p, intake_id)
    d = db.get(IntakeDocument, document_id)
    if not d or d.intake_id != i.id:
        raise NotFound("Document not found")
    storage().delete(d.storage_key)
    db.delete(d)
    audit.record(db, action="intake.document.delete", result="success", actor=p, resource_type="intake", resource_id=i.id, risk="MEDIUM")
    db.flush()
    return _intake_out(db, i)


@router.post("/intakes/{intake_id}/review")
def review_intake(intake_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    """Organise the client's own files: what each is, a dated timeline, conflicting dates and missing documents."""
    i = _my_intake(db, p, intake_id)
    rate_limit.hit("agent", p.id)
    out = client_review.review(db, i, max_bytes=get_settings().max_upload_bytes)
    audit.record(db, action="intake.review", result="success", actor=p, resource_type="intake", resource_id=i.id, risk="LOW",
                 detail=f"{out['summary']['documents']} docs, {out['summary']['conflicts']} conflicts, {out['summary']['missing']} missing")
    db.flush()
    return _intake_out(db, i)


def budget_fit(budget: int | None, l: Lawyer) -> str | None:
    """How the advocate's self-declared fee range compares with the client's stated budget (never a ranking)."""
    if not budget:
        return None
    lo, hi = l.fee_range_min, l.fee_range_max
    if lo is None and hi is None:
        return "not_declared"
    if (hi or lo) <= budget:
        return "within"
    if (lo or 0) <= budget:
        return "partly"
    return "above"


@router.get("/connection-policy")
def current_connection_policy(db: Session = Depends(get_db, scope="function")):
    """Which connection features are available, why, and the disclosures a client must see before sharing a matter."""
    return connection_policy.effective(db).public()


@router.post("/matching")
def matching(body: dict, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    policy = connection_policy.require(db, "matching")
    intake_id = str(body.get("intakeId", ""))[:36]
    i = _my_intake(db, p, intake_id)
    lawyers = db.scalars(select(Lawyer).where(Lawyer.verification_status == "VERIFIED", Lawyer.profile_status == "published")).all()
    cands = []
    for l in lawyers:
        areas = frozenset(db.scalars(select(LawyerPracticeArea.area).where(LawyerPracticeArea.lawyer_id == l.id, LawyerPracticeArea.verified)))
        led = db.scalar(select(func.count(Case.id)).join(CaseMember, CaseMember.case_id == Case.id).where(
            CaseMember.user_id == l.user_id, CaseMember.role == "lead", Case.matter_type == i.matter_type, Case.is_demo.is_(False))) or 0
        cands.append(Candidate(l.id, l.name, l.city, l.state, tuple(l.jurisdictions or []), areas, tuple(l.languages or []),
                               l.experience_years, l.accepting_clients, led))
    matches = match(i.matter_type or "other", i.city, i.jurisdiction, i.language, i.structured.get("complexity", "medium"), cands)
    db.query(LawyerMatch).filter(LawyerMatch.intake_id == i.id).delete()
    for m in matches:
        db.add(LawyerMatch(intake_id=i.id, lawyer_id=m.lawyer_id, rank=m.rank, reasons=m.reasons, considerations=m.considerations))
    audit.record(db, action="matching.run", result="success", actor=p, resource_type="intake", resource_id=i.id,
                 agent="Case Matching Agent", detail=f"{len(matches)} verified lawyers")
    by_id = {l.id: l for l in lawyers}
    # Fees (and therefore budget fit) only when the compliance-reviewed policy allows fees to be shown.
    fit = (lambda l: budget_fit(i.budget_max, l)) if policy.show_fees else (lambda l: None)
    return {"disclaimer": DISCLAIMER, "policy": policy.public(), "budgetMax": i.budget_max,
            "matches": [{"rank": m.rank, "reasons": m.reasons, "considerations": m.considerations, "budgetFit": fit(by_id[m.lawyer_id]),
                         "lawyer": connection_policy.project_lawyer(policy, lawyer_out(db, by_id[m.lawyer_id]))} for m in matches],
            "note": None if matches else "No verified lawyer is available for this matter yet."}


@router.post("/intakes/{intake_id}/connect", status_code=201)
def connect(intake_id: str, body: ConnectIn, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    """Sharing the matter with a lawyer is HIGH risk: this creates an approval the client must confirm."""
    connection_policy.require(db, "client_requests")
    _my_intake(db, p, intake_id)
    a = approvals.create(db, p, "connection.request", intake_id, {"lawyerId": body.lawyer_id, "note": body.note,
                                                                 "policyVersion": str(body.policy_version),
                                                                 "disclosureHash": body.disclosure_hash})
    return {"approvalId": a.id, "summary": a.summary, "status": a.status}


# ------------------------------------------------------------ lawyer side
@router.get("/requests")
def requests(p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    """
    Until the advocate clears the conflict check they see only what a conflict check needs: the names involved, the
    matter type, city and urgency. The summary, title, documents count and the client's note stay hidden.
    """
    conns = db.scalars(select(Connection).where(Connection.lawyer_id == p.lawyer_id).order_by(Connection.created_at.desc())).all()
    out = []
    for c in conns:
        i = db.get(Intake, c.intake_id)
        chk = conflicts.ensure(db, c)
        row = {"id": c.id, "status": c.status, "caseId": c.case_id, "createdAt": iso(c.created_at), "conflictCheck": conflicts.out(chk),
               "intake": {"matterType": i.matter_type, "urgency": i.urgency, "city": i.city}}
        if chk.status == "CLEARED":
            client = db.get(User, c.client_id)
            row |= {"clientName": client.name if client else "", "note": c.client_note, "budgetMax": i.budget_max}
            row["intake"] |= {"title": i.title, "structured": i.structured, "securityFlags": i.security_flags,
                              "documents": len(db.scalars(select(IntakeDocument.id).where(IntakeDocument.intake_id == i.id)).all())}
        out.append(row)
    return out


@router.post("/requests/{connection_id}/conflict-check")
def conflict_check(connection_id: str, body: ConflictDecisionIn, p: Principal = Depends(require_lawyer),
                   db: Session = Depends(get_db, scope="function")):
    authorize("connection.respond", p.role)
    c = db.get(Connection, connection_id)
    if not c or c.lawyer_id != p.lawyer_id:
        raise NotFound("Request not found")
    if c.status != "requested":
        raise Conflict("Already answered")
    return conflicts.out(conflicts.decide(db, p, c, body.clear, body.note))


@router.post("/requests/{connection_id}/respond")
def respond(connection_id: str, body: RespondIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    authorize("connection.respond", p.role)
    c = db.get(Connection, connection_id)
    if not c or c.lawyer_id != p.lawyer_id:
        raise NotFound("Request not found")
    if c.status != "requested":
        raise Conflict("Already answered")
    if body.accept:  # declining is always possible; taking on a new engagement needs the policy in force
        connection_policy.require(db, "client_requests")
        if conflicts.ensure(db, c).status != "CLEARED":
            raise Conflict("Complete the conflict check before accepting", code="conflict_check_required")
    c.status, c.lawyer_note, c.responded_at = ("accepted" if body.accept else "declined"), body.note, utcnow()
    i = db.get(Intake, c.intake_id)
    if body.accept:
        client = db.get(User, c.client_id)
        case = Case(organization_id=p.org_id, created_by=p.id, reference=next_reference(db, p.org_id), title=i.title,
                    description=i.structured.get("problem", i.description[:2000]), matter_type=i.matter_type or "other",
                    jurisdiction=i.jurisdiction, client_name=client.name if client else "", intake_id=i.id)
        db.add(case)
        db.flush()
        db.add_all([CaseMember(case_id=case.id, user_id=p.id, role="lead", added_by=p.id),
                    CaseMember(case_id=case.id, user_id=c.client_id, role="client", added_by=p.id)])
        for d in db.scalars(select(IntakeDocument).where(IntakeDocument.intake_id == i.id)):
            try:
                ingest(db, organization_id=p.org_id, case_id=case.id, uploaded_by=c.client_id, filename=d.filename,
                       declared_type=d.mime_type, data=storage().get(d.storage_key), source="intake")
            except Exception as e:  # one unreadable file must not block the case
                audit.record(db, action="document.ingest", result="error", resource_type="intake_document", resource_id=d.id,
                             organization_id=p.org_id, case_id=case.id, detail=type(e).__name__)
        c.case_id, i.status = case.id, "connected"
    db.add(Notification(user_id=c.client_id, kind="connection", title=f"{'Accepted' if body.accept else 'Declined'}: {i.title}",
                        link="/portal"))
    audit.record(db, action="connection.respond", result="success", actor=p, resource_type="connection", resource_id=c.id, risk="MEDIUM",
                 organization_id=p.org_id, case_id=c.case_id, detail=c.status)
    db.flush()
    return {"id": c.id, "status": c.status, "caseId": c.case_id}


@router.get("/cases/{case_id}/messages")
def lawyer_messages(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    get_case(db, p, case_id)
    return _messages(db, case_id)


@router.post("/cases/{case_id}/messages", status_code=201)
def lawyer_send(case_id: str, body: MessageIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "message.send")
    return _send(db, p, a.case.id, body.body)


# ----------------------------------------------------------------- portal
@router.get("/portal/cases")
def portal_cases(p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    ids = db.scalars(select(CaseMember.case_id).where(CaseMember.user_id == p.id, CaseMember.role == "client")).all()
    return [_portal_case(db, c) for c in (db.get(Case, i) for i in ids) if c and c.deleted_at is None]


def _portal_case(db: Session, c: Case) -> dict:
    lead_ids = db.scalars(select(CaseMember.user_id).where(CaseMember.case_id == c.id, CaseMember.role == "lead")).all()
    return {"id": c.id, "reference": c.reference, "title": c.title, "status": c.status, "matterType": c.matter_type,
            "lawyers": [u.name for u in (db.get(User, i) for i in lead_ids) if u], "updatedAt": iso(c.updated_at)}


@router.get("/portal/cases/{case_id}")
def portal_case(case_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "portal.read")
    updates = db.scalars(select(ClientUpdate).where(ClientUpdate.case_id == case_id).order_by(ClientUpdate.created_at.desc())).all()
    docs = db.scalars(select(Document).where(Document.case_id == case_id, Document.source.in_(("client_upload", "intake")))).all()
    return _portal_case(db, a.case) | {
        "updates": [{"id": u.id, "title": u.title, "body": u.body, "createdAt": iso(u.created_at)} for u in updates],
        "documents": [document_out(d, client_view=True) for d in docs], "messages": _messages(db, case_id)}


@router.get("/portal/cases/{case_id}/messages")
def portal_messages(case_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    get_case(db, p, case_id, "portal.read")
    return _messages(db, case_id)


@router.post("/portal/cases/{case_id}/messages", status_code=201)
def portal_send(case_id: str, body: MessageIn, p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    get_case(db, p, case_id, "portal.read")
    authorize("message.send", p.role, case_role="client")
    return _send(db, p, case_id, body.body)


@router.post("/portal/cases/{case_id}/documents", status_code=201)
async def portal_upload(case_id: str, files: list[UploadFile] = File(...), p: Principal = Depends(require_client), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "portal.read")
    authorize("portal.document.upload", p.role, case_role="client")
    rate_limit.hit("upload", p.id, cost=len(files))
    limit, out = get_settings().max_upload_bytes, []
    for f in files[:10]:
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise TooLarge("File too large")
        d = ingest(db, organization_id=a.case.organization_id, case_id=case_id, uploaded_by=p.id, filename=f.filename or "document",
                   declared_type=f.content_type, data=data, source="client_upload")
        out.append(document_out(d, client_view=True))
    case_index.invalidate(case_id)
    for uid in db.scalars(select(CaseMember.user_id).where(CaseMember.case_id == case_id, CaseMember.role == "lead")):
        db.add(Notification(user_id=uid, kind="client_upload", title=f"Client uploaded {len(out)} document(s) to {a.case.title}",
                            link=f"/cases/{case_id}"))
    return out


def _messages(db: Session, case_id: str) -> list[dict]:
    rows = db.scalars(select(Message).where(Message.case_id == case_id).order_by(Message.created_at)).all()
    return [{"id": m.id, "senderId": m.sender_id, "senderName": (db.get(User, m.sender_id) or User(name="")).name,
             "senderRole": (db.get(User, m.sender_id) or User(role="")).role, "body": m.body, "createdAt": iso(m.created_at)} for m in rows]


def _send(db: Session, p: Principal, case_id: str, body: str) -> dict:
    rate_limit.hit("write", p.id)
    if not body.strip():
        raise Unprocessable("Empty message")
    m = Message(case_id=case_id, sender_id=p.id, body=body.strip())
    db.add(m)
    others = db.scalars(select(CaseMember.user_id).where(CaseMember.case_id == case_id, CaseMember.user_id != p.id,
                                                         CaseMember.role.in_(("client", "lead")))).all()
    for uid in others:
        db.add(Notification(user_id=uid, kind="message", title=f"New message from {p.user.name}",
                            link=f"/portal/matters/{case_id}" if p.role == "lawyer" else f"/cases/{case_id}"))
    db.flush()
    return {"id": m.id}
