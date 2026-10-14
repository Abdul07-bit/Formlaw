"""
Lawyer profile, verification (KYC) and the policy-gated directory.

Verification status is written only by `services.verification.transition`: submission → PENDING → provider checks →
UNDER_REVIEW → admin decision → VERIFIED (with expiry) / REJECTED; admins may also SUSPEND and reinstate. No input field
can set it. Judicial status needs its own check and an explicit admin decision; uploading an ID never makes anyone a judge.
No biometric (selfie / face-match) data is collected.

The directory is advocate discovery, which Indian professional rules restrict: it is served only when the current
ConnectionPolicy enables public discovery, and only with the profile fields that policy allows.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import Conflict, NotFound, TooLarge, Unprocessable
from ...db.base import new_id
from ...db.session import get_db
from ...domain.enums import LawyerVerification as V
from ...kyc.providers import get_kyc_provider
from ...models import Lawyer, LawyerPracticeArea, LawyerVerificationCheck
from ...policies import connection as connection_policy
from ...policies.engine import authorize
from ...schemas.workspace import LawyerProfileIn
from ...security import rate_limit
from ...security.deps import Principal, require_lawyer
from ...security.files import validate_upload
from ...security.injection import kinds_in
from ...services import audit, verification
from ...services.serializers import iso, lawyer_out
from ...services.storage import storage

router = APIRouter(tags=["lawyers"])


def _mine(db: Session, p: Principal) -> Lawyer:
    l = db.get(Lawyer, p.lawyer_id) if p.lawyer_id else None
    if not l:
        raise NotFound("Lawyer profile not found")
    verification.expire_if_due(db, l)
    return l


@router.get("/lawyers/profile")
def my_profile(p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    return lawyer_out(db, _mine(db, p), private=True)


@router.put("/lawyers/profile")
def update_profile(body: LawyerProfileIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    authorize("profile.update", p.role)
    rate_limit.hit("write", p.id)
    l = _mine(db, p)
    data = body.model_dump(exclude_unset=True)
    if kinds_in(data.get("bio") or "") or kinds_in(data.get("headline") or ""):
        raise Unprocessable("The profile contains instruction-like text and was rejected", code="unsafe_content")
    publish = data.pop("publish", None)
    areas = data.pop("practice_areas", None)
    credentials_changed = any(k in data and data[k] != getattr(l, k) for k in ("bar_council", "enrolment_number", "name"))
    for k, v in data.items():
        setattr(l, k, v)
    if areas is not None:
        verified = set(db.scalars(select(LawyerPracticeArea.area).where(LawyerPracticeArea.lawyer_id == l.id, LawyerPracticeArea.verified)))
        db.execute(delete(LawyerPracticeArea).where(LawyerPracticeArea.lawyer_id == l.id))
        for a in dict.fromkeys(areas):
            db.add(LawyerPracticeArea(lawyer_id=l.id, area=a, verified=a in verified))  # new areas start unverified
    if credentials_changed and l.verification_status == V.VERIFIED:
        verification.transition(db, l, V.PENDING, actor=p, reason="Credentials changed; re-verification required")
    if publish is not None:
        if publish and l.verification_status != V.VERIFIED:
            raise Unprocessable("Only verified profiles can be published", code="not_verified")
        l.profile_status = "published" if publish else "draft"
    audit.record(db, action="profile.update", result="success", actor=p, resource_type="lawyer", resource_id=l.id, risk="MEDIUM")
    db.flush()
    return lawyer_out(db, l, private=True)


async def _read(f: UploadFile, allowed: set[str]) -> tuple[bytes, str]:
    limit = get_settings().max_upload_bytes
    data = await f.read(limit + 1)
    if len(data) > limit:
        raise TooLarge("File too large")
    return data, validate_upload(f.filename or "", f.content_type, data, limit, allowed=allowed).display_name


@router.post("/lawyers/verification", status_code=201)
async def submit_verification(
    id_type: Literal["Bar Council ID", "Aadhaar", "PAN", "Passport"] = Form(..., alias="idType"),
    government_id: UploadFile = File(..., alias="governmentId"),
    qualification: UploadFile = File(...),
    judicial_court: str = Form(default="", alias="judicialCourt", max_length=160),
    p: Principal = Depends(require_lawyer),
    db: Session = Depends(get_db, scope="function"),
):
    authorize("verification.submit", p.role)
    rate_limit.hit("upload", p.id, cost=2)
    l = _mine(db, p)
    if l.verification_status in (V.PENDING, V.UNDER_REVIEW):
        raise Conflict("A verification is already in progress", code="verification_pending")
    if l.verification_status == V.SUSPENDED:
        raise Conflict("Your verification is suspended. Contact FormLaw to request a review.", code="verification_suspended")
    if not l.bar_council or not l.enrolment_number:
        raise Unprocessable("Add your Bar Council and enrolment number to your profile first", code="profile_incomplete")
    gov, gov_name = await _read(government_id, {"pdf", "png", "jpg", "jpeg"})
    qual, qual_name = await _read(qualification, {"pdf", "png", "jpg", "jpeg"})
    provider, sub = get_kyc_provider(), new_id()
    verification.transition(db, l, V.PENDING, actor=p, reason="Verification documents submitted", submission_id=sub)
    checks = [
        ("government_id", provider.verify_government_id(id_type=id_type, document=gov), storage().put(gov), gov_name),
        ("qualification", provider.verify_qualification(document=qual), storage().put(qual), qual_name),
        ("bar_registration", provider.verify_professional_registration(bar_council=l.bar_council, enrolment_no=l.enrolment_number, name=l.name), None, None),
    ]
    if judicial_court.strip():
        checks.append(("judicial_status", provider.verify_judicial_status(name=l.name, court=judicial_court.strip()), None, None))
    for vtype, res, key, name in checks:
        db.add(LawyerVerificationCheck(lawyer_id=l.id, submission_id=sub, verification_type=vtype, status=res.status, provider=provider.name,
                                       provider_reference=res.reference, result=res.result, document_key=key, document_name=name))
    failed = [c[0] for c in checks if c[1].status == "failed"]
    if failed:
        verification.transition(db, l, V.REJECTED, actor=None, reason=f"Provider check failed: {', '.join(failed)}", submission_id=sub)
    else:
        verification.transition(db, l, V.UNDER_REVIEW, actor=None, reason=f"Provider checks recorded ({provider.name}); awaiting reviewer",
                                submission_id=sub)
    audit.record(db, action="verification.submit", result="success", actor=p, resource_type="lawyer", resource_id=l.id, risk="MEDIUM",
                 detail=f"submission {sub}: {l.verification_status}")
    db.flush()
    return lawyer_out(db, l, private=True)


@router.get("/lawyers/verification")
def my_verification(p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    l = _mine(db, p)
    rows = db.scalars(select(LawyerVerificationCheck).where(LawyerVerificationCheck.lawyer_id == l.id)
                      .order_by(LawyerVerificationCheck.created_at.desc()).limit(20)).all()
    return {"status": l.verification_status, "expiresAt": iso(l.verification_expires_at), "checks": [
        {"type": c.verification_type, "status": c.status, "provider": c.provider, "note": c.note, "submittedAt": iso(c.created_at),
         "demo": bool((c.result or {}).get("demo"))} for c in rows], "history": verification.history(db, l.id)}


def _listed(db: Session, l: Lawyer | None) -> bool:
    if not l or l.verification_status != V.VERIFIED or l.profile_status != "published":
        return False
    verification.expire_if_due(db, l)
    return l.verification_status == V.VERIFIED


@router.get("/lawyers")
def directory(area: str | None = None, city: str | None = None, db: Session = Depends(get_db, scope="function")):
    policy = connection_policy.require(db, "public_discovery")
    rows = db.scalars(select(Lawyer).where(Lawyer.verification_status == V.VERIFIED, Lawyer.profile_status == "published")
                      .order_by(Lawyer.name)).all()  # alphabetical: no ranking, promotion or paid placement
    out = []
    for l in rows:
        if not _listed(db, l):
            continue
        o = lawyer_out(db, l)
        if (not area or area in o["verifiedAreas"]) and (not city or l.city.lower() == city.lower()):
            out.append(connection_policy.project_lawyer(policy, o))
    return out


@router.get("/lawyers/{lawyer_id}")
def public_profile(lawyer_id: str, db: Session = Depends(get_db, scope="function")):
    policy = connection_policy.require(db, "public_discovery")
    l = db.get(Lawyer, lawyer_id)
    if not _listed(db, l):
        raise NotFound("Lawyer not found")
    return connection_policy.project_lawyer(policy, lawyer_out(db, l))
