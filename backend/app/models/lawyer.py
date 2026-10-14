"""
Lawyer profiles and verification. Verification records are separate from the profile, and only server-side
workflows (KYC provider + admin decision) write `verification_status`. There are no ratings, reviews, win rates
or other performance figures: FormLaw cannot verify them, so it does not store them.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin, utcnow
from ..domain.enums import LawyerVerification, MatterType, check_in

# No biometric (face-match) check: collecting biometrics needs a lawful basis and specialist legal review first.
VERIFICATION_TYPES = ("government_id", "bar_registration", "qualification", "judicial_status")


class Lawyer(IdMixin, TimestampMixin, Base):
    __tablename__ = "lawyers"
    __table_args__ = (
        CheckConstraint(check_in("verification_status", LawyerVerification), name="ck_lawyer_verification"),
        CheckConstraint("profile_status IN ('draft','published','suspended')", name="ck_lawyer_profile"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    headline: Mapped[str] = mapped_column(String(160), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    jurisdictions: Mapped[list] = mapped_column(JsonType, default=list)  # courts / states of practice
    bar_council: Mapped[str] = mapped_column(String(120), default="")
    enrolment_number: Mapped[str] = mapped_column(String(60), default="")
    experience_years: Mapped[int] = mapped_column(Integer, default=0)  # self-declared; labelled as such
    languages: Mapped[list] = mapped_column(JsonType, default=list)
    education: Mapped[list] = mapped_column(JsonType, default=list)
    qualifications: Mapped[list] = mapped_column(JsonType, default=list)
    bio: Mapped[str] = mapped_column(Text, default="")
    accepting_clients: Mapped[bool] = mapped_column(Boolean, default=True)
    consultation_fee: Mapped[int | None] = mapped_column(Integer)  # INR, self-declared
    # Typical professional fee for a matter, INR, self-declared by the advocate. Shown only if the ConnectionPolicy allows fees.
    fee_range_min: Mapped[int | None] = mapped_column(Integer)
    fee_range_max: Mapped[int | None] = mapped_column(Integer)
    # Written only by server workflows.
    verification_status: Mapped[str] = mapped_column(String(14), default=LawyerVerification.NOT_STARTED)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    judicial_status_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    profile_status: Mapped[str] = mapped_column(String(10), default="draft")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LawyerPracticeArea(Base):
    __tablename__ = "lawyer_practice_areas"
    __table_args__ = (CheckConstraint(check_in("area", MatterType), name="ck_practice_area"),)

    lawyer_id: Mapped[str] = mapped_column(ForeignKey("lawyers.id", ondelete="CASCADE"), primary_key=True)
    area: Mapped[str] = mapped_column(String(20), primary_key=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # true only after an admin verification decision


class VerificationEvent(IdMixin, TimestampMixin, Base):
    """Append-only history of every verification status change: who (or which system rule) changed it, and why."""
    __tablename__ = "verification_events"

    lawyer_id: Mapped[str] = mapped_column(ForeignKey("lawyers.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str] = mapped_column(String(14))
    to_status: Mapped[str] = mapped_column(String(14))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(10))  # lawyer | admin | system
    reason: Mapped[str] = mapped_column(String(500), default="")
    submission_id: Mapped[str | None] = mapped_column(String(36))


class LawyerVerificationCheck(IdMixin, TimestampMixin, Base):
    """One verification check (document, registration or judicial status). No biometric checks are run or stored."""
    __tablename__ = "lawyer_verifications"
    __table_args__ = (
        CheckConstraint(f"verification_type IN ({','.join(repr(t) for t in VERIFICATION_TYPES)})", name="ck_lv_type"),
        CheckConstraint("status IN ('pending','passed','failed','manual_review')", name="ck_lv_status"),
    )

    lawyer_id: Mapped[str] = mapped_column(ForeignKey("lawyers.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[str] = mapped_column(String(36), index=True)
    verification_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(14), default="pending")
    provider: Mapped[str] = mapped_column(String(60))
    provider_reference: Mapped[str | None] = mapped_column(String(120))
    result: Mapped[dict] = mapped_column(JsonType, default=dict)
    document_key: Mapped[str | None] = mapped_column(String(64))  # encrypted object key
    document_name: Mapped[str | None] = mapped_column(String(160))
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))
