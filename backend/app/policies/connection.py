"""
ConnectionPolicy: the compliance gate in front of advocate discovery, matching and client→advocate requests.

    effective policy = latest APPROVED policy for the jurisdiction
                       (or, in DEMO_MODE only, the latest DEMO_ONLY policy)
                       else SAFE_DEFAULT — every connection feature off.

The decision of whether a feature is lawful is a human compliance decision recorded on the policy row; this module only
enforces that decision. Paid promotion, paid placement, ranking by outcomes and referral fees are not configurable:
FormLaw has no code path for them.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import Forbidden, Unprocessable
from ..models import ConnectionPolicy

Feature = Literal["public_discovery", "matching", "client_requests"]
JURISDICTION = "IN"

# Lawyer profile fields a policy may choose to show. Anything else is never public.
PUBLIC_PROFILE_FIELDS = frozenset({
    "headline", "city", "state", "jurisdictions", "languages", "education", "qualifications", "bio", "experienceYears",
    "acceptingClients", "verifiedAreas", "practiceAreas", "judicialStatusVerified", "consultationFee", "feeRange",
})
FEE_FIELDS = frozenset({"consultationFee", "feeRange"})
# Always present so a client can tell who the advocate is and what FormLaw has (and has not) verified.
ALWAYS_SHOWN = ("id", "name", "verificationStatus", "isDemo", "experienceSelfDeclared", "feesSelfDeclared")


@dataclass(frozen=True)
class EffectivePolicy:
    source: Literal["default", "approved", "demo"]
    policy_id: str | None = None
    version: int = 0
    public_discovery: bool = False
    matching: bool = False
    client_requests: bool = False
    show_fees: bool = False
    visible_fields: frozenset[str] = field(default_factory=frozenset)
    disclosures: tuple[str, ...] = ()
    professional_rules: tuple[str, ...] = ()
    review_reference: str | None = None

    def enabled(self, feature: Feature) -> bool:
        return bool(getattr(self, feature))

    @property
    def disclosure_hash(self) -> str:
        return hashlib.sha256(json.dumps(list(self.disclosures), ensure_ascii=False).encode()).hexdigest()

    def public(self) -> dict:
        """What any visitor may know about the current policy (no reviewer identities)."""
        label = {"default": "Connection features are not available: no compliance-reviewed policy is in force.",
                 "approved": "Enabled under a compliance-reviewed policy.",
                 "demo": "DEMO ONLY — enabled for demonstration with synthetic data. Not a legal or compliance review."}[self.source]
        return {"source": self.source, "version": self.version, "label": label,
                "features": {"publicDiscovery": self.public_discovery, "matching": self.matching, "clientRequests": self.client_requests},
                "showFees": self.show_fees, "visibleProfileFields": sorted(self.visible_fields),
                "disclosures": list(self.disclosures), "disclosureHash": self.disclosure_hash}


SAFE_DEFAULT = EffectivePolicy(source="default")


def _from_row(row: ConnectionPolicy, source: Literal["approved", "demo"]) -> EffectivePolicy:
    visible = frozenset(row.visible_profile_fields or []) & PUBLIC_PROFILE_FIELDS
    if not row.show_fees:
        visible -= FEE_FIELDS
    return EffectivePolicy(source=source, policy_id=row.id, version=row.version, public_discovery=row.public_discovery_enabled,
                           matching=row.matching_enabled, client_requests=row.client_requests_enabled, show_fees=row.show_fees,
                           visible_fields=visible, disclosures=tuple(row.required_disclosures or ()),
                           professional_rules=tuple(row.professional_rules or ()), review_reference=row.review_reference)


def effective(db: Session, jurisdiction: str = JURISDICTION) -> EffectivePolicy:
    def latest(status: str) -> ConnectionPolicy | None:
        return db.scalar(select(ConnectionPolicy).where(ConnectionPolicy.jurisdiction == jurisdiction,
                                                        ConnectionPolicy.review_status == status)
                         .order_by(ConnectionPolicy.version.desc()).limit(1))

    if row := latest("APPROVED"):
        return _from_row(row, "approved")
    if get_settings().demo_mode and (row := latest("DEMO_ONLY")):
        return _from_row(row, "demo")
    return SAFE_DEFAULT


def require(db: Session, feature: Feature) -> EffectivePolicy:
    """Raise unless the current policy enables `feature`. Called on every gated request and again at approval execution."""
    p = effective(db)
    if not p.enabled(feature):
        raise Forbidden("This feature is not available until it has passed compliance review.", code="connection_feature_disabled",
                        details={"feature": feature, "policySource": p.source})
    return p


def project_lawyer(p: EffectivePolicy, out: dict) -> dict:
    """Reduce a lawyer projection to what the policy allows the public (or a client) to see."""
    return {k: v for k, v in out.items() if k in ALWAYS_SHOWN or k in p.visible_fields}


def validate_fields(fields: list[str]) -> list[str]:
    unknown = sorted(set(fields) - PUBLIC_PROFILE_FIELDS)
    if unknown:
        raise Unprocessable(f"Fields cannot be made public: {', '.join(unknown)}", code="field_not_allowed")
    return sorted(set(fields))
