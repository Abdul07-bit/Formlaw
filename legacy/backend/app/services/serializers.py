"""Database rows → API shapes (camelCase via the Out models). Access level decides what is included."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..matching.agent import DISCLAIMER
from ..models import (AnalysisRun, Case, Citation, Claim, Connection, Contradiction, Document, Evidence, KycVerification,
                      Lawyer, LawyerCase, LawyerExpertise, LawyerMatch, Message, MissingInformation, RelatedCase,
                      SecurityEvent, User)

UI_STATUS = {"SUPPORTED": "supported", "PARTIALLY_SUPPORTED": "partial", "CONTRADICTED": "conflicted",
             "UNSUPPORTED": "unsupported", "UNVERIFIED": "unsupported"}


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def user_out(db: Session, u: User) -> dict[str, Any]:
    lawyer_id = db.scalar(select(Lawyer.id).where(Lawyer.user_id == u.id)) if u.role in ("lawyer", "judge") else None
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "city": u.city, "lawyer_id": lawyer_id, "is_demo": u.is_demo}


def document_out(d: Document, include_text: bool) -> dict[str, Any]:
    return {
        "id": d.id, "name": d.filename, "type": d.content_type, "size": d.size, "pages": d.pages,
        "extraction": "live" if d.processing_status in ("extracted", "quarantined") else "backend",
        "processing_status": d.processing_status, "content_hash": d.content_hash,
        "text": d.extracted_text if include_text else "",
    }


def security_event_out(e: SecurityEvent) -> dict[str, Any]:
    return {"id": e.id, "doc_name": e.doc_name, "kind": e.kind, "snippet": e.snippet, "risk": e.risk, "actions": e.actions,
            "at": iso(e.created_at), "case_id": e.case_id}


def analysis_out(db: Session, run: AnalysisRun) -> dict[str, Any] | None:
    if run.status != "completed":
        return None
    docs = {d.id: d.filename for d in db.scalars(select(Document).where(Document.case_id == run.case_id))}
    evidence = list(db.scalars(select(Evidence).where(Evidence.run_id == run.id).order_by(Evidence.label)))
    label_of = {e.id: e.label for e in evidence}
    claims = list(db.scalars(select(Claim).where(Claim.run_id == run.id).order_by(Claim.ordinal)))
    cites: dict[str, list[str]] = {}
    if claims:
        for c in db.scalars(select(Citation).where(Citation.claim_id.in_([c.id for c in claims]))):
            if c.evidence_id:
                cites.setdefault(c.claim_id, []).append(label_of[c.evidence_id])
    contradictions = db.scalars(select(Contradiction).where(Contradiction.run_id == run.id)).all()
    missing = db.scalars(select(MissingInformation).where(MissingInformation.run_id == run.id).order_by(MissingInformation.ordinal)).all()
    matches = db.scalars(select(LawyerMatch).where(LawyerMatch.run_id == run.id).order_by(LawyerMatch.rank)).all()
    related = db.scalars(select(RelatedCase).where(RelatedCase.run_id == run.id).order_by(RelatedCase.similarity.desc())).all()
    events = db.scalars(select(SecurityEvent).where(SecurityEvent.case_id == run.case_id, SecurityEvent.created_at >= run.created_at)).all()
    return {
        "task_id": run.task_id, "area": run.area, "area_confidence": run.area_confidence or 0, "summary": run.summary,
        "facts": [{"id": c.key, "label": c.label, "statement": c.text, "status": UI_STATUS[c.verification_status],
                   "verification_status": c.verification_status, "evidence_ids": cites.get(c.id, [])} for c in claims],
        "evidence": [{"id": e.label, "doc_id": e.document_id, "doc_name": docs.get(e.document_id, ""), "page": e.page,
                      "excerpt": e.text, "highlight": e.highlight, "content_hash": e.content_hash} for e in evidence],
        "contradictions": [{"id": f"C-{i + 1}", "topic": c.topic, "a": {"value": c.claim_a, "evidence_id": label_of[c.evidence_a]},
                            "b": {"value": c.claim_b, "evidence_id": label_of[c.evidence_b]}, "confidence": c.confidence}
                           for i, c in enumerate(contradictions)],
        "missing": [{"id": f"M{i + 1}", "title": m.title, "why": m.description, "action": m.action} for i, m in enumerate(missing)],
        "security": [security_event_out(e) for e in events],
        "related": [{"case_id": r.lawyer_case_id, "similarity": r.similarity, "shared_terms": r.shared_terms} for r in related],
        "matches": [{"lawyer_id": m.lawyer_id, "score": m.score, "reasons": m.reasons, "estimate": (m.estimate_min, m.estimate_max)} for m in matches],
        "draft": {"title": run.draft_title, "body": run.draft_body},
        "verification": run.verification or {"analysed": 0, "supported": 0, "partial": 0, "conflicted": 0, "unsupported": 0, "coverage": 0},
        "trace": run.trace or [],
        "completed_at": iso(run.completed_at) or iso(run.created_at),
        "legal_pipeline": run.legal_pipeline,
        "fee_disclaimer": DISCLAIMER,
    }


def latest_run(db: Session, case_id: str) -> AnalysisRun | None:
    return db.scalar(select(AnalysisRun).where(AnalysisRun.case_id == case_id, AnalysisRun.status == "completed")
                     .order_by(AnalysisRun.created_at.desc()).limit(1))


def case_out(db: Session, case: Case, access: str) -> dict[str, Any]:
    run = latest_run(db, case.id)
    analysis = analysis_out(db, run) if run else None
    if analysis and access == "counsel":
        analysis["security"] = []  # counsel sees the brief, not the client's security log
    connected = db.scalars(select(Connection.lawyer_id).where(Connection.case_id == case.id)).all()
    return {
        "id": case.id, "owner_id": case.owner_id, "title": case.title, "description": case.description, "city": case.city,
        "budget": case.budget if access == "owner" else 0, "status": case.status,
        "documents": [document_out(d, include_text=access == "owner") for d in case.documents],
        "analysis": analysis, "connected_lawyer_ids": list(connected), "created_at": iso(case.created_at),
        "is_demo": case.is_demo, "access": access,
    }


def lawyer_out(db: Session, l: Lawyer, *, private: bool = False) -> dict[str, Any]:
    areas = db.scalars(select(LawyerExpertise.practice_area).where(LawyerExpertise.lawyer_id == l.id)).all()
    out = {
        "id": l.id, "name": l.name, "title": l.title, "role": l.professional_status, "photo_hue": l.photo_hue,
        "initials": "".join(p[0] for p in l.name.replace("Adv.", "").replace("Justice", "").split() if p)[:2].upper(),
        "city": l.city, "state": l.state, "courts": l.courts or [], "bar_council": l.bar_council,
        "enrolment_no": l.bar_or_registration_number, "experience_years": l.experience_years, "practice_areas": list(areas),
        "languages": l.languages or [], "consultation_fee": l.consultation_fee, "hearing_fee": l.hearing_fee,
        "rating": l.rating, "reviews": l.reviews, "cases_handled": l.cases_handled, "response_hours": l.response_hours,
        "bio": l.bio, "kyc": l.verification_status, "profile_status": l.profile_status, "is_demo": l.is_demo,
    }
    if private:
        out["kyc_submission"] = kyc_submission_out(db, l.id)
    return out


def kyc_submission_out(db: Session, lawyer_id: str) -> dict[str, Any] | None:
    latest = db.scalar(select(KycVerification).where(KycVerification.lawyer_id == lawyer_id).order_by(KycVerification.created_at.desc()).limit(1))
    if not latest:
        return None
    checks = db.scalars(select(KycVerification).where(KycVerification.submission_id == latest.submission_id)).all()
    by_type = {c.verification_type: c for c in checks}
    face = by_type.get("face_match")
    idc = by_type.get("government_id")
    deg = by_type.get("qualification")
    reviewed = max((c.reviewed_at for c in checks if c.reviewed_at), default=None)
    return {
        "degree_certificate": deg.document_name if deg else None, "id_card": idc.document_name if idc else None,
        "id_type": (idc.result or {}).get("id_type") if idc else None,
        "face_match_score": (face.result or {}).get("score") if face else None,
        "liveness_passed": (face.result or {}).get("liveness") if face else None,
        "provider": latest.provider,
        "checks": [{"type": c.verification_type, "status": c.status, "provider": c.provider, "reference": c.provider_reference,
                    "demo": bool((c.result or {}).get("demo"))} for c in checks],
        "submitted_at": iso(min(c.created_at for c in checks)), "reviewed_at": iso(reviewed),
        "review_note": next((c.note for c in checks if c.note), None),
    }


def lawyer_case_out(c: LawyerCase) -> dict[str, Any]:
    return {"id": c.id, "lawyer_id": c.lawyer_id, "title": c.case_reference, "area": c.legal_category, "court": c.court,
            "year": c.year, "outcome": c.outcome, "sections": c.sections or [], "summary": c.summary, "keywords": c.keywords or [],
            "duration_months": c.duration_months, "verified": c.verification_status == "verified",
            "verification_status": c.verification_status, "is_demo": c.is_demo}


def conversation_out(db: Session, c: Connection) -> dict[str, Any]:
    case = db.get(Case, c.case_id)
    client = db.get(User, c.client_id)
    msgs = db.scalars(select(Message).where(Message.connection_id == c.id).order_by(Message.created_at)).all()
    return {
        "id": c.id, "case_id": c.case_id, "case_title": case.title if case else "", "client_id": c.client_id,
        "client_name": client.name if client else "Client", "lawyer_id": c.lawyer_id, "status": c.status, "quote": c.quote,
        "messages": [{"id": m.id, "from": m.sender_role, "text": m.text, "at": iso(m.created_at)} for m in msgs],
        "updated_at": iso(c.updated_at),
    }
