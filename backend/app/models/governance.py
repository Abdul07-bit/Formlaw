"""Approvals, audit, security events, memory and notifications."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin
from ..domain.enums import MemoryScope, Risk, check_in


class AuditLog(IdMixin, TimestampMixin, Base):
    """Who did what to which resource, with what risk and result. Never holds document content."""
    __tablename__ = "audit_logs"
    __table_args__ = (CheckConstraint(check_in("risk_level", Risk), name="ck_audit_risk"),)

    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    task_id: Mapped[str | None] = mapped_column(String(24), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor_role: Mapped[str | None] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(60), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(30))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    risk_level: Mapped[str] = mapped_column(String(6), default=Risk.LOW)
    result: Mapped[str] = mapped_column(String(12))  # success | denied | error | blocked | pending
    agent: Mapped[str | None] = mapped_column(String(40))
    tool: Mapped[str | None] = mapped_column(String(40))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    verification_status: Mapped[str | None] = mapped_column(String(40))
    security_event_id: Mapped[str | None] = mapped_column(String(36))
    ip_hash: Mapped[str | None] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(String(300))  # redacted, short


class SecurityEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "security_events"
    __table_args__ = (CheckConstraint(check_in("risk", Risk), name="ck_security_risk"),)

    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    run_id: Mapped[str | None] = mapped_column(String(36))
    actor_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(200))  # document name, "chat request", "login", ...
    kind: Mapped[str] = mapped_column(String(30))  # prompt_injection | tool_request | exfiltration | malicious_file | auth_abuse | output_violation
    risk: Mapped[str] = mapped_column(String(6))
    snippet: Mapped[str] = mapped_column(String(240))
    actions: Mapped[list] = mapped_column(JsonType, default=list)


class Approval(IdMixin, TimestampMixin, Base):
    """HIGH-risk actions wait here until the responsible human approves or rejects them."""
    __tablename__ = "approvals"
    __table_args__ = (CheckConstraint("status IN ('pending','approved','rejected','executed','expired','failed')", name="ck_approval_status"),)

    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    risk_level: Mapped[str] = mapped_column(String(6))
    resource_type: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    summary: Mapped[str] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(36))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JsonType)


class MemoryItem(IdMixin, TimestampMixin, Base):
    """
    Long-lived agent memory. Written only by the system from verified outcomes, always with provenance,
    scoped to an organization (and case where relevant), and expiring. Memory points at evidence; it is
    never itself treated as evidence.
    """
    __tablename__ = "memory_items"
    __table_args__ = (CheckConstraint(check_in("scope", MemoryScope), name="ck_memory_scope"),)

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(40))  # run_outcome | verified_fact | open_contradiction | flagged_chunk | authority_link
    key: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[dict] = mapped_column(JsonType, default=dict)
    provenance: Mapped[dict] = mapped_column(JsonType, default=dict)  # run_id, claim ids, evidence ids
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(IdMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
