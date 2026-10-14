"""Case workspace views and the lawyer's review actions on AI-produced knowledge."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.errors import NotFound
from ...db.base import utcnow
from ...db.session import get_db
from ...models import (AgentRun, AuditLog, Citation, Claim, Contradiction, Document, Draft, Evidence, LegalAuthority,
                       MissingInformation, SavedFinding, SecurityEvent, Task, TimelineEvent, ToolCall)
from ...repositories.access import get_case
from ...schemas.workspace import DraftPatch, FindingIn, ReviewIn, StatusIn, TaskIn, TaskPatch
from ...security.deps import Principal, require_lawyer
from ...services import audit
from ...services.serializers import iso

router = APIRouter(tags=["knowledge"])


def _ev(db: Session, eid: str | None) -> dict[str, Any] | None:
    if not eid:
        return None
    e = db.get(Evidence, eid)
    if not e:
        return None
    d = db.get(Document, e.document_id)
    return {"evidenceId": e.id, "chunkId": e.chunk_id, "documentId": e.document_id, "documentName": d.filename if d else "",
            "page": e.page, "paragraph": e.paragraph, "section": e.section, "quote": e.quote}


def _scoped(db: Session, model, case_id: str, org_id: str):
    return select(model).where(model.case_id == case_id, model.organization_id == org_id)


@router.get("/cases/{case_id}/overview")
def overview(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    org = a.case.organization_id
    cnt = lambda m, *w: len(db.scalars(_scoped(db, m, case_id, org).where(*w)).all())  # noqa: E731
    return {"documents": len(db.scalars(select(Document.id).where(Document.case_id == case_id)).all()),
            "claims": cnt(Claim), "unverified": cnt(Claim, Claim.status.in_(("UNSUPPORTED", "UNVERIFIED", "CONTRADICTED"))),
            "contradictions": cnt(Contradiction, Contradiction.status == "open"),
            "missing": cnt(MissingInformation, MissingInformation.status == "open"), "timeline": cnt(TimelineEvent),
            "authorities": cnt(LegalAuthority), "drafts": cnt(Draft), "openTasks": cnt(Task, Task.status == "open"),
            "securityEvents": len(db.scalars(select(SecurityEvent.id).where(SecurityEvent.case_id == case_id)).all()),
            "runs": len(db.scalars(select(AgentRun.id).where(AgentRun.case_id == case_id)).all())}


@router.get("/cases/{case_id}/evidence")
def evidence(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    rows = db.scalars(_scoped(db, Evidence, case_id, a.case.organization_id).order_by(Evidence.created_at.desc())).all()
    return [_ev(db, e.id) | {"contentHash": e.content_hash, "createdAt": iso(e.created_at)} for e in rows]


@router.get("/cases/{case_id}/claims")
def claims(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    out = []
    for c in db.scalars(_scoped(db, Claim, case_id, a.case.organization_id).order_by(Claim.created_at)):
        cites = db.scalars(select(Citation).where(Citation.claim_id == c.id)).all()
        out.append({"id": c.id, "text": c.text, "kind": c.kind, "agent": c.agent, "status": c.status, "confidence": c.confidence,
                    "reason": c.reason, "reviewStatus": c.review_status, "reviewNote": c.review_note,
                    "citations": [x for x in (_ev(db, ci.evidence_id) for ci in cites) if x]})
    return out


@router.get("/cases/{case_id}/contradictions")
def contradictions(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [{"id": x.id, "topic": x.topic, "nature": x.nature, "confidence": x.confidence, "status": x.status,
             "statementA": x.statement_a, "statementB": x.statement_b, "a": _ev(db, x.evidence_a_id), "b": _ev(db, x.evidence_b_id),
             "provenance": x.provenance, "resolutionNote": x.resolution_note}
            for x in db.scalars(_scoped(db, Contradiction, case_id, a.case.organization_id).order_by(Contradiction.created_at))]


@router.get("/cases/{case_id}/missing-information")
def missing(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [{"id": m.id, "title": m.title, "why": m.why_needed, "basis": m.basis, "importance": m.importance, "status": m.status,
             "citation": _ev(db, m.evidence_id)}
            for m in db.scalars(_scoped(db, MissingInformation, case_id, a.case.organization_id).order_by(MissingInformation.created_at))]


@router.get("/cases/{case_id}/timeline")
def timeline(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    rows = db.scalars(_scoped(db, TimelineEvent, case_id, a.case.organization_id)).all()
    rows.sort(key=lambda t: (t.event_date.isoformat() if t.event_date else "9999", t.created_at))
    return [{"id": t.id, "date": t.event_date.isoformat() if t.event_date else None, "dateText": t.date_text,
             "description": t.description, "eventType": t.event_type, "status": t.status, "citation": _ev(db, t.evidence_id)} for t in rows]


@router.get("/cases/{case_id}/authorities")
def authorities(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [{"id": x.id, "type": x.authority_type, "title": x.title, "citation": x.citation, "court": x.court,
             "date": x.decision_date.isoformat() if x.decision_date else None, "page": x.page, "quote": x.quote, "issue": x.issue,
             "source": x.source_name, "sourceUrl": x.source_url, "license": x.license, "contentHash": x.content_hash,
             "reviewStatus": x.review_status}
            for x in db.scalars(_scoped(db, LegalAuthority, case_id, a.case.organization_id).order_by(LegalAuthority.created_at.desc()))]


# ------------------------------------------------------------ lawyer review
def _owned(db: Session, p: Principal, model, item_id: str):
    row = db.get(model, item_id)
    if not row:
        raise NotFound("Not found")
    get_case(db, p, row.case_id, "knowledge.review")
    return row


@router.patch("/claims/{claim_id}")
def review_claim(claim_id: str, body: ReviewIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    c = _owned(db, p, Claim, claim_id)
    c.review_status, c.review_note, c.reviewed_by, c.reviewed_at = body.decision, body.note or None, p.id, utcnow()
    audit.record(db, action="knowledge.review", result="success", actor=p, resource_type="claim", resource_id=c.id, risk="MEDIUM",
                 organization_id=c.organization_id, case_id=c.case_id, detail=body.decision)
    return {"id": c.id, "reviewStatus": c.review_status}


@router.patch("/contradictions/{item_id}")
def review_contradiction(item_id: str, body: StatusIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    x = _owned(db, p, Contradiction, item_id)
    x.status = "resolved" if body.status == "resolved" else "dismissed" if body.status == "dismissed" else "open"
    x.resolution_note = body.note or None
    audit.record(db, action="knowledge.review", result="success", actor=p, resource_type="contradiction", resource_id=x.id,
                 risk="MEDIUM", organization_id=x.organization_id, case_id=x.case_id, detail=x.status)
    return {"id": x.id, "status": x.status}


@router.patch("/missing-information/{item_id}")
def review_missing(item_id: str, body: StatusIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    m = _owned(db, p, MissingInformation, item_id)
    m.status = body.status
    audit.record(db, action="knowledge.review", result="success", actor=p, resource_type="missing_information", resource_id=m.id,
                 risk="MEDIUM", organization_id=m.organization_id, case_id=m.case_id, detail=m.status)
    return {"id": m.id, "status": m.status}


# ------------------------------------------------------- findings & tasks
@router.get("/cases/{case_id}/findings")
def findings(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [{"id": f.id, "title": f.title, "content": f.content, "note": f.note, "messageId": f.message_id, "createdAt": iso(f.created_at)}
            for f in db.scalars(_scoped(db, SavedFinding, case_id, a.case.organization_id).order_by(SavedFinding.created_at.desc()))]


@router.post("/cases/{case_id}/findings", status_code=201)
def save_finding(case_id: str, body: FindingIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "finding.save")
    f = SavedFinding(case_id=case_id, organization_id=a.case.organization_id, user_id=p.id, title=body.title, content=body.content,
                     message_id=body.message_id, note=body.note)
    db.add(f)
    db.flush()
    return {"id": f.id}


@router.get("/cases/{case_id}/tasks")
def tasks(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [{"id": t.id, "title": t.title, "status": t.status, "dueDate": t.due_date.isoformat() if t.due_date else None,
             "source": t.source, "createdAt": iso(t.created_at)}
            for t in db.scalars(_scoped(db, Task, case_id, a.case.organization_id).order_by(Task.status.desc(), Task.created_at))]


@router.post("/cases/{case_id}/tasks", status_code=201)
def add_task(case_id: str, body: TaskIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "task.write")
    t = Task(case_id=case_id, organization_id=a.case.organization_id, title=body.title, due_date=body.due_date, source=body.source,
             created_by=p.id)
    db.add(t)
    db.flush()
    return {"id": t.id}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskPatch, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    t = db.get(Task, task_id)
    if not t:
        raise NotFound("Task not found")
    get_case(db, p, t.case_id, "task.write")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    return {"id": t.id, "status": t.status}


# ------------------------------------------------------------------ drafts
def _draft_out(d: Draft) -> dict[str, Any]:
    return {"id": d.id, "kind": d.kind, "title": d.title, "sections": d.sections, "body": d.body, "status": d.status,
            "version": d.version, "createdAt": iso(d.created_at), "updatedAt": iso(d.updated_at), "approvedAt": iso(d.approved_at)}


@router.get("/cases/{case_id}/drafts")
def drafts(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [_draft_out(d) for d in db.scalars(_scoped(db, Draft, case_id, a.case.organization_id).order_by(Draft.created_at.desc()))]


@router.get("/drafts/{draft_id}")
def draft(draft_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    d = db.get(Draft, draft_id)
    if not d:
        raise NotFound("Draft not found")
    get_case(db, p, d.case_id)
    return _draft_out(d)


@router.patch("/drafts/{draft_id}")
def edit_draft(draft_id: str, body: DraftPatch, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    d = db.get(Draft, draft_id)
    if not d:
        raise NotFound("Draft not found")
    get_case(db, p, d.case_id, "draft.write")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    d.version, d.updated_at = d.version + 1, utcnow()
    if d.status == "approved":
        d.status = "draft"  # edits re-open approval
    return _draft_out(d)


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    d = db.get(Draft, draft_id)
    if not d:
        raise NotFound("Draft not found")
    get_case(db, p, d.case_id, "draft.approve")
    d.status, d.approved_by, d.approved_at = "approved", p.id, utcnow()
    audit.record(db, action="draft.approve", result="success", actor=p, resource_type="draft", resource_id=d.id, risk="MEDIUM",
                 organization_id=d.organization_id, case_id=d.case_id)
    return _draft_out(d)


# --------------------------------------------------------- activity / audit
@router.get("/cases/{case_id}/activity")
def activity(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    runs = db.scalars(select(AgentRun).where(AgentRun.case_id == case_id, AgentRun.organization_id == a.case.organization_id)
                      .order_by(AgentRun.created_at.desc()).limit(50)).all()
    out = []
    for r in runs:
        calls = db.scalars(select(ToolCall).where(ToolCall.run_id == r.id)).all()
        out.append({"id": r.id, "taskId": r.task_id, "goal": r.goal, "intent": r.intent, "status": r.status, "engine": r.engine,
                    "steps": r.steps, "toolCalls": r.tool_calls, "replans": r.replans, "tokens": r.tokens, "latencyMs": r.latency_ms,
                    "createdAt": iso(r.created_at), "plan": r.plan,
                    "tools": [{"agent": c.agent, "tool": c.tool, "status": c.status, "latencyMs": c.latency_ms, "risk": c.risk,
                               "model": c.model} for c in calls]})
    return out


@router.get("/cases/{case_id}/audit")
def case_audit(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    rows = db.scalars(select(AuditLog).where(AuditLog.case_id == case_id, AuditLog.organization_id == a.case.organization_id)
                      .order_by(AuditLog.created_at.desc()).limit(200)).all()
    sec = db.scalars(select(SecurityEvent).where(SecurityEvent.case_id == case_id).order_by(SecurityEvent.created_at.desc())).all()
    return {"audit": [{"id": r.id, "at": iso(r.created_at), "action": r.action, "result": r.result, "risk": r.risk_level, "agent": r.agent,
                       "taskId": r.task_id, "detail": r.detail, "actorRole": r.actor_role} for r in rows],
            "security": [{"id": s.id, "at": iso(s.created_at), "kind": s.kind, "source": s.source, "snippet": s.snippet,
                          "actions": s.actions, "risk": s.risk} for s in sec]}
