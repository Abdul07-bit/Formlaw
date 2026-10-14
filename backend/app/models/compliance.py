"""
Compliance records: the connection policy that gates client↔advocate discovery, and client consents.

Indian professional rules (Bar Council of India Rules, Part VI, Chapter II, rule 36 and related rules) restrict advocate
advertising and solicitation. FormLaw therefore treats every discovery / matching / connection feature as OFF until a
human compliance reviewer approves a specific, versioned policy. Policies are append-only: a change is a new version.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin

POLICY_STATUSES = ("DRAFT", "APPROVED", "REJECTED", "SUPERSEDED", "REVOKED", "DEMO_ONLY")


class ConnectionPolicy(IdMixin, TimestampMixin, Base):
    __tablename__ = "connection_policies"
    __table_args__ = (
        UniqueConstraint("jurisdiction", "version", name="uq_connection_policy_version"),
        CheckConstraint(f"review_status IN ({','.join(repr(s) for s in POLICY_STATUSES)})", name="ck_connection_policy_status"),
    )

    jurisdiction: Mapped[str] = mapped_column(String(8), default="IN")
    version: Mapped[int] = mapped_column(Integer)
    public_discovery_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    matching_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    client_requests_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    show_fees: Mapped[bool] = mapped_column(Boolean, default=False)
    visible_profile_fields: Mapped[list] = mapped_column(JsonType, default=list)
    required_disclosures: Mapped[list] = mapped_column(JsonType, default=list)
    professional_rules: Mapped[list] = mapped_column(JsonType, default=list)  # references the reviewer relied on
    rationale: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(12), default="DRAFT")
    review_reference: Mapped[str | None] = mapped_column(String(200))  # e.g. counsel opinion reference
    review_note: Mapped[str | None] = mapped_column(String(1000))
    drafted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


CONFLICT_STATUSES = ("PENDING_REVIEW", "CLEARED", "CONFLICT")


class ConflictCheck(IdMixin, TimestampMixin, Base):
    """
    Conflict-of-interest check for one client request, run before the advocate sees the matter summary.
    Only names are disclosed for checking; automated hits reference the advocate's own firm's matters by reference
    number only. The client never learns why a request was declined.
    """
    __tablename__ = "conflict_checks"
    __table_args__ = (CheckConstraint(f"status IN ({','.join(repr(s) for s in CONFLICT_STATUSES)})", name="ck_conflict_status"),)

    connection_id: Mapped[str] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"), unique=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)  # the advocate's firm that was searched
    names_checked: Mapped[list] = mapped_column(JsonType, default=list)  # [{"name", "role": "client"|"other_party"}]
    automated_hits: Mapped[list] = mapped_column(JsonType, default=list)  # [{"caseId", "reference", "name", "field"}]
    status: Mapped[str] = mapped_column(String(16), default="PENDING_REVIEW")
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(1000), default="")  # internal to the advocate; never shown to the client


class Consent(IdMixin, TimestampMixin, Base):
    """A specific, informed permission: who agreed to share what, with whom, under which disclosures. Revocable."""
    __tablename__ = "consents"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(60))  # e.g. connection.share_intake
    subject_type: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    recipient_type: Mapped[str] = mapped_column(String(30))
    recipient_id: Mapped[str] = mapped_column(String(36))
    policy_id: Mapped[str | None] = mapped_column(ForeignKey("connection_policies.id"))
    disclosures: Mapped[list] = mapped_column(JsonType, default=list)  # exact text the user was shown
    disclosure_hash: Mapped[str] = mapped_column(String(64))
    approval_id: Mapped[str | None] = mapped_column(String(36))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="")
