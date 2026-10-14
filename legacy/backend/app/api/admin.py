"""Admin / security console. Admins verify professionals and watch security; they cannot read client case files."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import Conflict, NotFound, Unprocessable
from ...db.base import utcnow
from ...db.session import engine, get_db
from ...models import AuditLog, KycVerification, Lawyer, LawyerCase, LawyerExpertise, SecurityEvent, User
from ...policy.risk import authorize
from ...schemas.lawyers import KycDecisionIn, LawyerCaseOut, LawyerOut, VerifyCaseIn
from ...security.deps import Principal, require_admin
from ...services import audit
from ...services.serializers import iso, lawyer_case_out, lawyer_out, security_event_out

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/kyc", response_model=list[LawyerOut], summary="Professionals with KYC submissions")
def kyc_queue(p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    ids = db.scalars(select(KycVerification.lawyer_id).distinct()).all()
    lawyers = db.scalars(select(Lawyer).where(Lawyer.id.in_(ids)).order_by(Lawyer.updated_at.desc())).all() if ids else []
    return [lawyer_out(db, l, private=True) for l in lawyers]


@router.post("/kyc/{lawyer_id}/decision", response_model=LawyerOut)
def kyc_decision(lawyer_id: str, body: KycDecisionIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    authorize("kyc.decide", p.role)
    lawyer = db.get(Lawyer, lawyer_id)
    if not lawyer:
        raise NotFound("Lawyer not found")
    if lawyer.verification_status != "pending":
        raise Conflict("There is no pending verification for this professional")
    latest = db.scalar(select(KycVerification).where(KycVerification.lawyer_id == lawyer.id).order_by(KycVerification.created_at.desc()).limit(1))
    checks = db.scalars(select(KycVerification).where(KycVerification.submission_id == latest.submission_id)).all() if latest else []
    if body.approve:
        if any(c.status == "failed" for c in checks):
            raise Unprocessable("A provider check failed; this profile cannot be approved", code="kyc_check_failed")
        if any(c.status == "manual_review" and (c.result or {}).get("demo") for c in checks) and not get_settings().demo_mode:
            raise Unprocessable("Demo verification results cannot be approved outside demo mode", code="demo_provider")
        if not body.note.strip():
            raise Unprocessable("Record what you checked in the review note", code="note_required")
    for c in checks:
        c.reviewer_id, c.reviewed_at, c.note = p.id, utcnow(), body.note[:500]
        if c.status == "manual_review":
            c.status = "passed" if body.approve else "failed"
    lawyer.verification_status = "verified" if body.approve else "rejected"
    lawyer.profile_status = "published" if body.approve else "draft"
    for e in db.scalars(select(LawyerExpertise).where(LawyerExpertise.lawyer_id == lawyer.id)):
        e.verified = body.approve
    audit.record(db, action="kyc.decide", result="success", actor=p.user, resource_type="lawyer", resource_id=lawyer.id, risk="HIGH",
                 verification_status=lawyer.verification_status, detail=body.note)
    db.flush()
    return lawyer_out(db, lawyer, private=True)


@router.get("/lawyer-cases", response_model=list[LawyerCaseOut])
def pending_cases(status: str = Query(default="pending", pattern="^(pending|verified|rejected)$"),
                  p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    return [lawyer_case_out(c) for c in db.scalars(select(LawyerCase).where(LawyerCase.verification_status == status)
                                                   .order_by(LawyerCase.created_at.desc()))]


@router.post("/lawyer-cases/{case_id}/verify", response_model=LawyerCaseOut)
def verify_case(case_id: str, body: VerifyCaseIn, p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    authorize("lawyer_case.verify", p.role)
    c = db.get(LawyerCase, case_id)
    if not c:
        raise NotFound("Case record not found")
    c.verification_status = "verified" if body.approve else "rejected"
    audit.record(db, action="lawyer_case.verify", result="success", actor=p.user, resource_type="lawyer_case", resource_id=c.id, risk="HIGH",
                 verification_status=c.verification_status)
    return lawyer_case_out(c)


@router.get("/security-events")
def security_events(limit: int = Query(default=100, ge=1, le=500), p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    authorize("security.read", p.role)
    return [security_event_out(e) for e in db.scalars(select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit))]


@router.get("/audit")
def audit_logs(limit: int = Query(default=200, ge=1, le=1000), action: str | None = Query(default=None, max_length=60),
               p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    authorize("security.read", p.role)
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action.startswith(action))
    return [{"id": a.id, "at": iso(a.created_at), "taskId": a.task_id, "actorId": a.actor_id, "actorRole": a.actor_role, "action": a.action,
             "resourceType": a.resource_type, "resourceId": a.resource_id, "risk": a.risk_level, "result": a.result, "agent": a.agent,
             "tool": a.tool, "latencyMs": a.latency_ms, "verificationStatus": a.verification_status,
             "securityEventId": a.security_event_id, "detail": a.detail} for a in db.scalars(q)]


@router.get("/users")
def users(p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "status": u.status, "isDemo": u.is_demo,
             "createdAt": iso(u.created_at)} for u in db.scalars(select(User).order_by(User.created_at.desc()).limit(500))]


@router.get("/health")
def system_health(p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    s = get_settings()
    counts = {name: db.scalar(select(func.count()).select_from(model)) for name, model in
              (("users", User), ("lawyers", Lawyer), ("securityEvents", SecurityEvent), ("auditLogs", AuditLog))}
    return {"database": engine().dialect.name, "env": s.env, "demoMode": s.demo_mode, "llmProvider": s.llm_provider,
            "kycProvider": s.kyc_provider, "fileEncryption": bool(s.file_encryption_key), "counts": counts,
            "limits": vars(s.limits)}
