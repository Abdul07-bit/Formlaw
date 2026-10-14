"""Cases, team access, documents and the per-case chunk index."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base, IdMixin, JsonType, TimestampMixin, utcnow
from ..domain.enums import CaseRole, CaseStatus, DocumentStatus, MatterType, check_in


class Case(IdMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(check_in("status", CaseStatus), name="ck_case_status"),
        CheckConstraint(check_in("matter_type", MatterType), name="ck_case_matter_type"),
    )

    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reference: Mapped[str] = mapped_column(String(40), index=True)  # human case id, e.g. FL-2026-0001
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    matter_type: Mapped[str] = mapped_column(String(20), default=MatterType.OTHER)
    status: Mapped[str] = mapped_column(String(10), default=CaseStatus.ACTIVE)
    jurisdiction: Mapped[str] = mapped_column(String(120), default="")
    court: Mapped[str] = mapped_column(String(160), default="")
    client_name: Mapped[str] = mapped_column(String(120), default="")  # display only; portal access is via case_members
    intake_id: Mapped[str | None] = mapped_column(String(36))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    documents = relationship("Document", back_populates="case", order_by="Document.created_at", cascade="all, delete-orphan", passive_deletes=True)


class CaseMember(IdMixin, TimestampMixin, Base):
    __tablename__ = "case_members"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_member"),
        CheckConstraint(check_in("role", CaseRole), name="ck_case_member_role"),
    )

    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    added_by: Mapped[str | None] = mapped_column(String(36))


class Document(IdMixin, TimestampMixin, Base):
    """A first-class, untrusted input. The original file is encrypted at rest; text lives in document_chunks."""
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(check_in("status", DocumentStatus), name="ck_doc_status"),
        UniqueConstraint("case_id", "content_hash", name="uq_doc_case_hash"),
    )

    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(160))  # sanitised display name; never used as a path
    mime_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(64))  # random object key
    source: Mapped[str] = mapped_column(String(20), default="lawyer_upload")  # lawyer_upload | client_upload | intake
    status: Mapped[str] = mapped_column(String(12), default=DocumentStatus.RECEIVED)
    status_note: Mapped[str | None] = mapped_column(String(300))
    doc_type: Mapped[str] = mapped_column(String(40), default="document")  # fir, remand_report, contract, ... (heuristic)
    pages: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict] = mapped_column("metadata", JsonType, default=dict)  # dates, parties, referenced documents
    security_flags: Mapped[list] = mapped_column(JsonType, default=list)  # e.g. ["prompt_injection"]
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    case = relationship("Case", back_populates="documents")


class DocumentChunk(IdMixin, Base):
    """
    Retrieval unit with exact provenance. `security_flags` marks spans that tried to instruct the system:
    such chunks remain evidence but are never placed in a model prompt.
    """
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunk_ordinal"),
        Index("ix_chunks_org_case", "organization_id", "case_id"),
    )

    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer, default=1)
    paragraph: Mapped[int] = mapped_column(Integer, default=1)  # paragraph number within the page
    section: Mapped[str | None] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer, default=0)  # offsets within the page text
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64))
    security_flags: Mapped[list] = mapped_column(JsonType, default=list)


class ChunkEmbedding(Base):
    """Vector for a case chunk. JSON here; PostgreSQL adds a pgvector column + HNSW index in migration 0005."""
    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), primary_key=True)
    model: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list] = mapped_column(JsonType)
