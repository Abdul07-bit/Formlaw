"""Output projections. Lawyer-side and client-side projections are separate functions on purpose."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Case, CaseMember, Document, Lawyer, LawyerPracticeArea, Organization, User)


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def user_out(db: Session, u: User) -> dict[str, Any]:
    lawyer = db.scalar(select(Lawyer).where(Lawyer.user_id == u.id)) if u.role == "lawyer" else None
    org = db.get(Organization, u.organization_id)
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "city": u.city, "lawyer_id": lawyer.id if lawyer else None,
            "organization_id": u.organization_id, "organization_name": org.name if org else "",
            "verification_status": lawyer.verification_status if lawyer else None, "is_demo": u.is_demo}


def case_out(db: Session, c: Case, role: str | None = None) -> dict[str, Any]:
    flags = db.scalars(select(Document.security_flags).where(Document.case_id == c.id)).all()
    docs, flagged = len(flags), sum(1 for f in flags if f)
    return {"id": c.id, "reference": c.reference, "title": c.title, "description": c.description, "matterType": c.matter_type,
            "status": c.status, "jurisdiction": c.jurisdiction, "court": c.court, "clientName": c.client_name, "isDemo": c.is_demo,
            "documentCount": docs, "flaggedDocuments": flagged or 0, "myRole": role, "createdAt": iso(c.created_at), "updatedAt": iso(c.updated_at)}


def document_out(d: Document, *, client_view: bool = False) -> dict[str, Any]:
    out = {"id": d.id, "filename": d.filename, "mimeType": d.mime_type, "size": d.size, "status": d.status, "statusNote": d.status_note,
           "pages": d.pages, "uploadedAt": iso(d.created_at), "source": d.source}
    if not client_view:
        out |= {"docType": d.doc_type, "contentHash": d.content_hash, "metadata": d.meta or {}, "securityFlags": d.security_flags or []}
    return out


def lawyer_out(db: Session, l: Lawyer, *, private: bool = False) -> dict[str, Any]:
    areas = db.execute(select(LawyerPracticeArea.area, LawyerPracticeArea.verified).where(LawyerPracticeArea.lawyer_id == l.id)).all()
    out = {"id": l.id, "name": l.name, "headline": l.headline, "city": l.city, "state": l.state, "jurisdictions": l.jurisdictions,
           "languages": l.languages, "education": l.education, "qualifications": l.qualifications, "bio": l.bio,
           "experienceYears": l.experience_years, "experienceSelfDeclared": True, "acceptingClients": l.accepting_clients,
           "consultationFee": l.consultation_fee, "verificationStatus": l.verification_status,
           "feeRange": {"min": l.fee_range_min, "max": l.fee_range_max} if (l.fee_range_min or l.fee_range_max) else None,
           "feesSelfDeclared": True,
           "verifiedAreas": [a for a, v in areas if v], "practiceAreas": [a for a, _ in areas],
           "judicialStatusVerified": l.judicial_status_verified, "isDemo": l.is_demo}
    if private:
        out |= {"barCouncil": l.bar_council, "enrolmentNumber": l.enrolment_number, "profileStatus": l.profile_status,
                "verifiedAt": iso(l.verified_at), "verificationExpiresAt": iso(l.verification_expires_at)}
    return out


def member_out(db: Session, m: CaseMember) -> dict[str, Any]:
    u = db.get(User, m.user_id)
    return {"userId": m.user_id, "name": u.name if u else "", "email": u.email if u else "", "role": m.role}
