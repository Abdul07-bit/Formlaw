"""
Client side: intake, matching, connections, lawyer↔client messages and lawyer-approved client updates.
Clients never see lawyer-internal data; these tables hold only what the client submitted or was explicitly sent.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin


class Intake(IdMixin, TimestampMixin, Base):
    __tablename__ = "intakes"
    __table_args__ = (CheckConstraint("status IN ('draft','submitted','matched','connected','closed')", name="ck_intake_status"),)

    client_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)  # client's personal org
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)  # raw, untrusted
    answers: Mapped[dict] = mapped_column(JsonType, default=dict)  # guided intake answers
    # People / organisations the CLIENT named as involved (stated by the client, not inferred). Used for conflict checks.
    declared_parties: Mapped[list] = mapped_column(JsonType, default=list)
    structured: Mapped[dict] = mapped_column(JsonType, default=dict)  # Client Intake Agent output
    matter_type: Mapped[str | None] = mapped_column(String(20))
    jurisdiction: Mapped[str] = mapped_column(String(120), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    urgency: Mapped[str] = mapped_column(String(10), default="normal")
    language: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(10), default="submitted")
    security_flags: Mapped[list] = mapped_column(JsonType, default=list)
    budget_max: Mapped[int | None] = mapped_column(Integer)  # INR the client is prepared to spend on the matter (client-stated)
    # Automated organisation of the client's own files (services/client_review.py). Not legal advice; never shared unasked.
    review: Mapped[dict | None] = mapped_column(JsonType)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntakeDocument(IdMixin, TimestampMixin, Base):
    __tablename__ = "intake_documents"

    intake_id: Mapped[str] = mapped_column(ForeignKey("intakes.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(160))
    mime_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(64))


class LawyerMatch(IdMixin, TimestampMixin, Base):
    """A recommendation and the reasons it was produced (kept for audit). No outcome predictions."""
    __tablename__ = "lawyer_matches"

    intake_id: Mapped[str] = mapped_column(ForeignKey("intakes.id", ondelete="CASCADE"), index=True)
    lawyer_id: Mapped[str] = mapped_column(ForeignKey("lawyers.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list] = mapped_column(JsonType, default=list)
    considerations: Mapped[list] = mapped_column(JsonType, default=list)  # e.g. "experience is self-declared"


class Connection(IdMixin, TimestampMixin, Base):
    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("intake_id", "lawyer_id", name="uq_connection"),
        CheckConstraint("status IN ('requested','accepted','declined','withdrawn')", name="ck_connection_status"),
    )

    intake_id: Mapped[str] = mapped_column(ForeignKey("intakes.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lawyer_id: Mapped[str] = mapped_column(ForeignKey("lawyers.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="requested")
    client_note: Mapped[str] = mapped_column(String(1000), default="")
    lawyer_note: Mapped[str] = mapped_column(String(1000), default="")
    case_id: Mapped[str | None] = mapped_column(String(36))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(IdMixin, TimestampMixin, Base):
    """Lawyer↔client messages on a case (portal channel)."""
    __tablename__ = "messages"

    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientUpdate(IdMixin, TimestampMixin, Base):
    """An update the lawyer explicitly approved for the client. Created only through an approval."""
    __tablename__ = "client_updates"

    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approval_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
