"""
Lawyer KYC. The lawyer submits documents; the server runs the configured KycProvider; only an admin
decision (POST /admin/kyc/{id}/decision) can mark a profile verified. No client input sets "verified".
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import Conflict, NotFound, TooLarge
from ...db.base import new_id
from ...db.session import get_db
from ...kyc.provider import get_kyc_provider
from ...models import KycVerification, Lawyer
from ...policy.risk import authorize
from ...schemas.lawyers import LawyerOut
from ...security import rate_limit
from ...security.deps import Principal, require_professional
from ...security.files import validate_upload
from ...services import audit
from ...services.serializers import lawyer_out
from ...services.storage import storage

router = APIRouter(prefix="/kyc", tags=["kyc"])
DOC_TYPES = {"pdf", "png", "jpg", "jpeg"}
IMAGE_TYPES = {"png", "jpg", "jpeg"}


async def _read(f: UploadFile, allowed: set[str]) -> tuple[bytes, str]:
    limit = get_settings().max_upload_bytes
    data = await f.read(limit + 1)
    if len(data) > limit:
        raise TooLarge("File too large")
    v = validate_upload(f.filename or "", f.content_type, data, limit, allowed=allowed)
    return data, v.display_name


@router.post("/submissions", response_model=LawyerOut, status_code=201)
async def submit(
    id_type: Literal["Bar Council ID", "Aadhaar", "PAN", "Passport"] = Form(..., alias="idType"),
    degree_certificate: UploadFile = File(..., alias="degreeCertificate"),
    id_card: UploadFile = File(..., alias="idCard"),
    selfie: UploadFile = File(...),
    p: Principal = Depends(require_professional),
    db: Session = Depends(get_db),
):
    authorize("kyc.submit", p.role)
    rate_limit.hit("upload", p.id, cost=3)
    lawyer = db.get(Lawyer, p.lawyer_id) if p.lawyer_id else None
    if not lawyer:
        raise NotFound("Lawyer profile not found")
    if lawyer.verification_status == "pending":
        raise Conflict("A verification is already under review", code="kyc_pending")

    degree, degree_name = await _read(degree_certificate, DOC_TYPES)
    idcard, id_name = await _read(id_card, DOC_TYPES)
    face, _ = await _read(selfie, IMAGE_TYPES)

    provider = get_kyc_provider()
    sub = new_id()
    checks = [
        ("qualification", provider.verify_qualification(document=degree), storage().put(degree), degree_name),
        ("government_id", provider.verify_government_id(id_type=id_type, document=idcard), storage().put(idcard), id_name),
        ("professional_registration", provider.verify_professional_registration(
            bar_council=lawyer.bar_council, enrolment_no=lawyer.bar_or_registration_number, name=lawyer.name), None, None),
        # Biometrics: the selfie goes to the provider and is then discarded — only the outcome is stored.
        ("face_match", provider.verify_face(selfie=face, id_document=idcard), None, None),
    ]
    if lawyer.professional_status == "judge":
        checks.append(("judicial_status", provider.verify_judicial_status(name=lawyer.name, court=", ".join(lawyer.courts or [])), None, None))
    del face

    for vtype, res, ref, name in checks:
        result = dict(res.result)
        if vtype == "government_id":
            result["id_type"] = id_type
        db.add(KycVerification(lawyer_id=lawyer.id, submission_id=sub, verification_type=vtype, status=res.status, provider=provider.name,
                               provider_reference=res.reference, result=result, document_ref=ref, document_name=name))
    lawyer.verification_status = "pending"
    audit.record(db, action="kyc.submit", result="success", actor=p.user, resource_type="lawyer", resource_id=lawyer.id, risk="MEDIUM",
                 detail=f"provider={provider.name}")
    db.flush()
    return lawyer_out(db, lawyer, private=True)
