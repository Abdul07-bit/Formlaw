"""
ConnectionPolicy lifecycle: administrators draft, compliance reviewers decide, either can revoke.

    DRAFT ─compliance approve─► APPROVED ─(newer approved)─► SUPERSEDED
      └──compliance reject──► REJECTED      └─revoke─► REVOKED

Approval needs a different person from the drafter, a review reference and an attestation that regulatory counsel
reviewed that exact version. Revoking only ever switches features off, so administrators may also do it in an emergency.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import Conflict, Forbidden, NotFound, Unprocessable
from ..db.base import utcnow
from ..models import ConnectionPolicy
from ..policies import connection as connection_policy
from ..schemas.workspace import ConnectionPolicyIn, PolicyReviewIn
from ..security.deps import Principal
from . import audit
from .serializers import iso


def out(r: ConnectionPolicy) -> dict:
    return {"id": r.id, "jurisdiction": r.jurisdiction, "version": r.version, "reviewStatus": r.review_status,
            "publicDiscoveryEnabled": r.public_discovery_enabled, "matchingEnabled": r.matching_enabled,
            "clientRequestsEnabled": r.client_requests_enabled, "showFees": r.show_fees,
            "visibleProfileFields": r.visible_profile_fields, "requiredDisclosures": r.required_disclosures,
            "professionalRules": r.professional_rules, "rationale": r.rationale, "reviewReference": r.review_reference,
            "reviewNote": r.review_note, "draftedBy": r.drafted_by, "reviewedBy": r.reviewed_by, "reviewedAt": iso(r.reviewed_at),
            "createdAt": iso(r.created_at)}


def listing(db: Session) -> dict:
    rows = db.scalars(select(ConnectionPolicy).order_by(ConnectionPolicy.version.desc())).all()
    return {"effective": connection_policy.effective(db).public(), "policies": [out(r) for r in rows],
            "allowedProfileFields": sorted(connection_policy.PUBLIC_PROFILE_FIELDS)}


def _get(db: Session, policy_id: str) -> ConnectionPolicy:
    r = db.get(ConnectionPolicy, policy_id)
    if not r:
        raise NotFound("Policy not found")
    return r


def draft(db: Session, p: Principal, body: ConnectionPolicyIn) -> ConnectionPolicy:
    fields = connection_policy.validate_fields(body.visible_profile_fields)
    if connection_policy.FEE_FIELDS & set(fields) and not body.show_fees:
        raise Unprocessable("Fee fields can only be visible when showFees is enabled", code="field_not_allowed")
    disclosures = [d.strip() for d in body.required_disclosures if d.strip()]
    if (body.public_discovery_enabled or body.matching_enabled or body.client_requests_enabled) and not disclosures:
        raise Unprocessable("A policy that enables a connection feature must define the disclosures shown to clients",
                            code="disclosures_required")
    version = (db.scalar(select(func.max(ConnectionPolicy.version)).where(ConnectionPolicy.jurisdiction == connection_policy.JURISDICTION)) or 0) + 1
    r = ConnectionPolicy(jurisdiction=connection_policy.JURISDICTION, version=version, public_discovery_enabled=body.public_discovery_enabled,
                         matching_enabled=body.matching_enabled, client_requests_enabled=body.client_requests_enabled, show_fees=body.show_fees,
                         visible_profile_fields=fields, required_disclosures=disclosures, professional_rules=body.professional_rules,
                         rationale=body.rationale, review_status="DRAFT", drafted_by=p.id)
    db.add(r)
    db.flush()
    audit.record(db, action="connection_policy.draft", result="success", actor=p, resource_type="connection_policy", resource_id=r.id,
                 risk="HIGH", detail=f"v{version}")
    return r


def review(db: Session, p: Principal, policy_id: str, body: PolicyReviewIn) -> ConnectionPolicy:
    r = _get(db, policy_id)
    if r.review_status != "DRAFT":
        raise Conflict("Only a draft policy can be reviewed")
    if r.drafted_by == p.id:
        raise Forbidden("The person who drafted a policy cannot review it", code="separation_of_duties")
    if body.approve and not body.counsel_reviewed:
        raise Unprocessable("Approval requires confirmation that regulatory counsel reviewed this exact version",
                            code="counsel_review_required")
    r.reviewed_by, r.reviewed_at, r.review_reference, r.review_note = p.id, utcnow(), body.review_reference, body.note
    if body.approve:
        for old in db.scalars(select(ConnectionPolicy).where(ConnectionPolicy.jurisdiction == r.jurisdiction,
                                                             ConnectionPolicy.review_status == "APPROVED")):
            old.review_status = "SUPERSEDED"
        r.review_status = "APPROVED"
    else:
        r.review_status = "REJECTED"
    audit.record(db, action="connection_policy.review", result="success", actor=p, resource_type="connection_policy", resource_id=r.id,
                 risk="HIGH", detail=f"v{r.version} {r.review_status} ref={body.review_reference}")
    db.flush()
    return r


def revoke(db: Session, p: Principal, policy_id: str, note: str) -> ConnectionPolicy:
    r = _get(db, policy_id)
    if r.review_status not in ("APPROVED", "DEMO_ONLY"):
        raise Conflict("Only an approved policy can be revoked")
    r.review_status, r.review_note = "REVOKED", note
    audit.record(db, action="connection_policy.revoke", result="success", actor=p, resource_type="connection_policy", resource_id=r.id,
                 risk="HIGH", detail=f"v{r.version}: {note}")
    db.flush()
    return r
