"""
Platform administration. Admins verify lawyers, draft connection policies and watch security/audit — they never read
case content.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import Conflict, NotFound, Unprocessable
from ...db.base import utcnow
from ...db.session import get_db
from ...domain.enums import LawyerVerification as V
from ...ingestion import coverage
from ...llm.providers import get_embedder, get_router
from ...models import (AgentRun, AuditLog, Case, LawyerPracticeArea, Lawyer, LawyerVerificationCheck, LegalChunk,
                       LegalDocument, Notification, SecurityEvent, User)
from ...policies import connection as connection_policy
from ...policies.engine import authorize
from ...schemas.workspace import AdminNoteIn, ConnectionPolicyIn, VerificationDecisionIn
from ...security.deps import Principal, require_admin
from ...services import connection_policies, verification
from ...services.serializers import iso, lawyer_out

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/verifications")
def queue(p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("verification.decide", p.role)
    out = []
    for l in db.scalars(select(Lawyer).where(Lawyer.verification_status.in_((V.PENDING, V.UNDER_REVIEW))).order_by(Lawyer.updated_at)):
        checks = db.scalars(select(LawyerVerificationCheck).where(LawyerVerificationCheck.lawyer_id == l.id)
                            .order_by(LawyerVerificationCheck.created_at.desc()).limit(10)).all()
        out.append({"lawyer": lawyer_out(db, l, private=True), "history": verification.history(db, l.id), "checks": [
            {"id": c.id, "type": c.verification_type, "status": c.status, "provider": c.provider, "reference": c.provider_reference,
             "result": c.result, "documentName": c.document_name, "submittedAt": iso(c.created_at)} for c in checks]})
    return out


def _lawyer(db: Session, lawyer_id: str) -> Lawyer:
    l = db.get(Lawyer, lawyer_id)
    if not l:
        raise NotFound("Lawyer not found")
    return l


def _notify(db: Session, l: Lawyer, note: str) -> None:
    db.add(Notification(user_id=l.user_id, kind="verification", title=f"Verification {l.verification_status.lower()}", body=note))


@router.post("/verifications/{lawyer_id}/decision")
def decide(lawyer_id: str, body: VerificationDecisionIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("verification.decide", p.role)
    l = _lawyer(db, lawyer_id)
    if l.verification_status != V.UNDER_REVIEW and not (l.verification_status == V.PENDING and not body.approve):
        raise Conflict("No verification awaiting a decision")
    roll = body.bar_roll_check
    if body.approve:
        # VERIFIED must mean a person checked an official roll — not that a demo provider returned "manual_review".
        if roll is None:
            raise Unprocessable("Record the official Bar Council roll check before verifying", code="bar_roll_check_required")
        if not (roll.enrolment_number_matches and roll.name_matches):
            raise Unprocessable("The roll entry must match both the enrolment number and the name", code="bar_roll_mismatch")
        if roll.checked_on > utcnow().date():
            raise Unprocessable("The roll check date cannot be in the future", code="bar_roll_date")
    checks = db.scalars(select(LawyerVerificationCheck).where(LawyerVerificationCheck.lawyer_id == l.id,
                                                              LawyerVerificationCheck.reviewed_at.is_(None))).all()
    for c in checks:
        if c.verification_type == "bar_registration" and roll is not None:
            c.result = (c.result or {}) | {"manualRollCheck": roll.model_dump(mode="json", by_alias=True), "reviewer": p.id}
        c.reviewer_id, c.reviewed_at, c.note = p.id, utcnow(), body.note
        c.status = "passed" if body.approve and c.status != "failed" else "failed"
    if body.approve:
        verification.transition(db, l, V.VERIFIED, actor=p,
                                reason=f"{body.note} | Roll: {roll.source}, ref {roll.reference}, checked {roll.checked_on.isoformat()}")
        # Judicial status only with its own submitted check and an explicit decision.
        l.judicial_status_verified = body.judicial_status and any(c.verification_type == "judicial_status" for c in checks)
        for a in db.scalars(select(LawyerPracticeArea).where(LawyerPracticeArea.lawyer_id == l.id)):
            a.verified = a.area in body.verified_areas
    else:
        verification.transition(db, l, V.REJECTED, actor=p, reason=body.note)
    _notify(db, l, body.note)
    db.flush()
    return lawyer_out(db, l, private=True)


@router.post("/verifications/{lawyer_id}/suspend")
def suspend(lawyer_id: str, body: AdminNoteIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    """E.g. a Bar Council reports the enrolment suspended, or verification evidence is found to be false."""
    authorize("verification.decide", p.role)
    l = _lawyer(db, lawyer_id)
    verification.transition(db, l, V.SUSPENDED, actor=p, reason=body.note)
    _notify(db, l, body.note)
    db.flush()
    return lawyer_out(db, l, private=True)


@router.post("/verifications/{lawyer_id}/reinstate")
def reinstate(lawyer_id: str, body: AdminNoteIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("verification.decide", p.role)
    l = _lawyer(db, lawyer_id)
    if l.verification_status != V.SUSPENDED:
        raise Conflict("Only a suspended verification can be reinstated", code="not_suspended")
    verification.expire_if_due(db, l)  # a suspension does not extend validity
    if l.verification_status == V.SUSPENDED:
        verification.transition(db, l, V.VERIFIED, actor=p, reason=body.note)
    _notify(db, l, body.note)
    db.flush()
    return lawyer_out(db, l, private=True)


@router.get("/lawyers")
def all_lawyers(status: str | None = None, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    """Every advocate account with its verification state (profile data only — no case or client data)."""
    authorize("verification.decide", p.role)
    q = select(Lawyer).order_by(Lawyer.name)
    if status:
        q = q.where(Lawyer.verification_status == status.upper()[:14])
    return [lawyer_out(db, l, private=True) for l in db.scalars(q.limit(500))]


@router.get("/verifications/{lawyer_id}/history")
def verification_history(lawyer_id: str, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("verification.decide", p.role)
    return verification.history(db, _lawyer(db, lawyer_id).id)


# ------------------------------------------------------------------ connection policy (compliance gate)
# Administrators draft policy versions and may revoke one in an emergency. Only a COMPLIANCE reviewer can approve
# (see api/v1/compliance.py).
@router.get("/connection-policies")
def list_policies(p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("connection_policy.read", p.role)
    return connection_policies.listing(db)


@router.post("/connection-policies", status_code=201)
def draft_policy(body: ConnectionPolicyIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("connection_policy.draft", p.role)
    return connection_policies.out(connection_policies.draft(db, p, body))


@router.post("/connection-policies/{policy_id}/revoke")
def revoke_policy(policy_id: str, body: AdminNoteIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    """Emergency switch-off (falls back to the safe default unless another approved version exists)."""
    authorize("connection_policy.revoke", p.role)
    return connection_policies.out(connection_policies.revoke(db, p, policy_id, body.note))

# ------------------------------------------------------------------ legal corpus
@router.get("/corpus/coverage")
def corpus_coverage(start: date | None = None, end: date | None = None, p: Principal = Depends(require_admin),
                    db: Session = Depends(get_db, scope="function")):
    """Measured coverage of the target window, with gaps (same report as `python -m app.ingestion report`)."""
    authorize("audit.read", p.role)
    return coverage.build(db, start, end)


# ------------------------------------------------------------------ observability
@router.get("/security-events")
def security_events(p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("security.read", p.role)
    rows = db.scalars(select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(200)).all()
    return [{"id": s.id, "at": iso(s.created_at), "kind": s.kind, "risk": s.risk, "source": s.source, "snippet": s.snippet,
             "actions": s.actions, "caseId": s.case_id, "runId": s.run_id} for s in rows]


@router.get("/audit")
def audit_log(p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    authorize("audit.read", p.role)
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300)).all()
    return [{"id": r.id, "at": iso(r.created_at), "action": r.action, "result": r.result, "risk": r.risk_level, "actorRole": r.actor_role,
             "resourceType": r.resource_type, "agent": r.agent, "tool": r.tool, "taskId": r.task_id, "latencyMs": r.latency_ms,
             "verification": r.verification_status, "detail": r.detail} for r in rows]


@router.get("/health")
def health(p: Principal = Depends(require_admin), db: Session = Depends(get_db, scope="function")):
    s, r = get_settings(), get_router()
    runs = db.execute(select(AgentRun.status, func.count(AgentRun.id), func.avg(AgentRun.latency_ms)).group_by(AgentRun.status)).all()
    return {"environment": s.env, "database": db.get_bind().dialect.name, "llm": r.name if r else "none (deterministic mode)",
            "embeddings": (e.model if (e := get_embedder()) else "none (keyword retrieval)"), "kycProvider": s.kyc_provider,
            "demoMode": s.demo_mode, "limits": vars(s.limits), "connectionPolicy": connection_policy.effective(db).public(),
            "counts": {"users": db.scalar(select(func.count(User.id))), "cases": db.scalar(select(func.count(Case.id))),
                       "corpusDocuments": db.scalar(select(func.count(LegalDocument.id))), "corpusChunks": db.scalar(select(func.count(LegalChunk.id)))},
            "runs": [{"status": st, "count": n, "avgLatencyMs": int(avg or 0)} for st, n, avg in runs]}
