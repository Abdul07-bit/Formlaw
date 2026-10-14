"""Identity and tenancy: organizations, users, memberships, refresh tokens."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base, IdMixin, TimestampMixin
from ..domain.enums import MembershipRole, OrgType, Role, check_in


class Organization(IdMixin, TimestampMixin, Base):
    """Tenant boundary. A solo lawyer gets a personal practice; firms share one; each client gets a personal one."""
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint(check_in("type", OrgType), name="ck_org_type"),)

    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default=OrgType.INDIVIDUAL)
    plan: Mapped[str] = mapped_column(String(20), default="free")  # billing tier placeholder; no billing in the MVP


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(check_in("role", Role), name="ck_user_role"),
        CheckConstraint("status IN ('active','locked','disabled')", name="ck_user_status"),
    )

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)  # home organization
    role: Mapped[str] = mapped_column(String(10))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # stored lower-cased
    phone: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(80))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(10), default="active")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship("Organization")


class Membership(IdMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership"),
        CheckConstraint(check_in("role", MembershipRole), name="ck_membership_role"),
    )

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10), default=MembershipRole.MEMBER)


class RefreshToken(IdMixin, TimestampMixin, Base):
    """Rotating refresh tokens. Only a hash is stored. Re-use of a rotated token revokes the whole family."""
    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[str | None] = mapped_column(String(36))
