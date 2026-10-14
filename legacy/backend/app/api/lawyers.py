from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable
from ...db.session import get_db
from ...models import Lawyer, LawyerCase, LawyerExpertise
from ...policy.risk import authorize
from ...schemas.lawyers import LawyerCaseIn, LawyerCaseOut, LawyerOut, LawyerProfileIn
from ...security import rate_limit
from ...security.deps import Principal, require_professional
from ...security.injection import kinds_in
from ...services import audit
from ...services.serializers import lawyer_case_out, lawyer_out

router = APIRouter(tags=["lawyers"])

# Client-identifying data must never enter a lawyer's public case history.
PII = re.compile(r"[\w.+-]+@[\w-]+\.\w+|\b(?:\+?91[\s-]?)?[6-9]\d{9}\b|\b\d{4}\s?\d{4}\s?\d{4}\b|\b[A-Z]{5}\d{4}[A-Z]\b")


@router.get("/lawyers", response_model=list[LawyerOut], summary="Public directory: KYC-verified, published profiles only")
def directory(area: str | None = Query(default=None, max_length=40), city: str | None = Query(default=None, max_length=80),
              db: Session = Depends(get_db)):
    q = select(Lawyer).where(Lawyer.verification_status == "verified", Lawyer.profile_status == "published")
    if city:
        q = q.where(Lawyer.city == city)
    lawyers = db.scalars(q.order_by(Lawyer.experience_years.desc())).all()
    out = [lawyer_out(db, l) for l in lawyers]
    return [l for l in out if not area or area in l["practice_areas"]]


@router.get("/lawyers/me", response_model=LawyerOut)
def my_profile(p: Principal = Depends(require_professional), db: Session = Depends(get_db)):
    return lawyer_out(db, _mine(db, p), private=True)


@router.patch("/lawyers/me", response_model=LawyerOut)
def update_profile(body: LawyerProfileIn, p: Principal = Depends(require_professional), db: Session = Depends(get_db)):
    authorize("profile.update", p.role)
    rate_limit.hit("write", p.id)
    l = _mine(db, p)
    data = body.model_dump(exclude_unset=True)
    if "bio" in data and kinds_in(data["bio"] or ""):
        raise Unprocessable("The bio contains instruction-like text and was rejected", code="unsafe_content")
    verified_fields_changed = any(k in data and data[k] != getattr(l, k, None) for k in ("bar_council", "experience_years"))
    if "enrolment_no" in data and data["enrolment_no"] != l.bar_or_registration_number:
        l.bar_or_registration_number = data.pop("enrolment_no") or ""
        verified_fields_changed = True
    data.pop("enrolment_no", None)
    areas = data.pop("practice_areas", None)
    for k, v in data.items():
        setattr(l, k, v)
    if areas is not None:
        db.execute(delete(LawyerExpertise).where(LawyerExpertise.lawyer_id == l.id))
        for a in dict.fromkeys(areas):
            # Self-declared expertise is unverified until an admin approves KYC.
            db.add(LawyerExpertise(lawyer_id=l.id, practice_area=a, jurisdiction=l.state, verified=False))
        verified_fields_changed = True
    if verified_fields_changed and l.verification_status == "verified":
        # Changing credentials re-opens verification; the profile leaves the public directory meanwhile.
        l.verification_status, l.profile_status = "pending", "draft"
    audit.record(db, action="profile.update", result="success", actor=p.user, resource_type="lawyer", resource_id=l.id, risk="MEDIUM")
    db.flush()
    return lawyer_out(db, l, private=True)


@router.get("/lawyers/{lawyer_id}", response_model=LawyerOut)
def public_profile(lawyer_id: str, db: Session = Depends(get_db)):
    l = db.get(Lawyer, lawyer_id)
    if not l or l.verification_status != "verified" or l.profile_status != "published":
        raise NotFound("Lawyer not found")
    return lawyer_out(db, l)


@router.get("/lawyer-cases", response_model=list[LawyerCaseOut], summary="Verified, anonymised case history (public)")
def verified_cases(db: Session = Depends(get_db)):
    return [lawyer_case_out(c) for c in db.scalars(select(LawyerCase).where(LawyerCase.verification_status == "verified")
                                                   .order_by(LawyerCase.year.desc()))]


@router.get("/lawyers/me/cases", response_model=list[LawyerCaseOut])
def my_cases(p: Principal = Depends(require_professional), db: Session = Depends(get_db)):
    l = _mine(db, p)
    return [lawyer_case_out(c) for c in db.scalars(select(LawyerCase).where(LawyerCase.lawyer_id == l.id).order_by(LawyerCase.created_at.desc()))]


@router.post("/lawyers/me/cases", response_model=LawyerCaseOut, status_code=201)
def submit_case(body: LawyerCaseIn, p: Principal = Depends(require_professional), db: Session = Depends(get_db)):
    authorize("lawyer_case.submit", p.role)
    rate_limit.hit("write", p.id)
    l = _mine(db, p)
    text = " ".join([body.title, body.summary, *body.keywords])
    if PII.search(text):
        raise Unprocessable("Remove client-identifying details (emails, phone, Aadhaar or PAN numbers) before submitting", code="pii_detected")
    if kinds_in(text):
        raise Unprocessable("The submission contains instruction-like text and was rejected", code="unsafe_content")
    rec = LawyerCase(lawyer_id=l.id, case_reference=body.title, legal_category=body.area, court=body.court, jurisdiction=l.state,
                     year=body.year, outcome=body.outcome, sections=body.sections, summary=body.summary,
                     keywords=[k.lower()[:40] for k in body.keywords], duration_months=body.duration_months)
    db.add(rec)
    db.flush()
    audit.record(db, action="lawyer_case.submit", result="success", actor=p.user, resource_type="lawyer_case", resource_id=rec.id, risk="MEDIUM")
    return lawyer_case_out(rec)


def _mine(db: Session, p: Principal) -> Lawyer:
    l = db.get(Lawyer, p.lawyer_id) if p.lawyer_id else None
    if not l:
        raise NotFound("Lawyer profile not found")
    return l
