"""
Legal knowledge base: provenance-tracked public legal documents (judgments, statutes, rules,
regulations) and a separate constitutional layer. Unknown metadata stays NULL — never guessed.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin, utcnow

AUTHORITY_KINDS = ("constitution_article", "statute_section", "rule", "regulation", "judgment")


class LegalSource(IdMixin, TimestampMixin, Base):
    __tablename__ = "legal_sources"

    key: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(300))
    license: Mapped[str] = mapped_column(String(300))  # terms under which the data may be used
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # true only when verification_status == APPROVED
    # Terms audit (single source of truth: legal-data/source-config/sources.json, synced by discover_sources)
    source_type: Mapped[str | None] = mapped_column(String(40))
    jurisdiction: Mapped[str | None] = mapped_column(String(60))
    terms_url: Mapped[str | None] = mapped_column(String(500))
    coverage_start: Mapped[int | None] = mapped_column(Integer)  # year
    coverage_end: Mapped[int | None] = mapped_column(Integer)
    access_method: Mapped[str | None] = mapped_column(String(200))
    allowed_usage: Mapped[str | None] = mapped_column(Text)
    restrictions: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    commercial_use_allowed: Mapped[bool | None] = mapped_column(Boolean)
    redistribution_allowed: Mapped[bool | None] = mapped_column(Boolean)
    api_available: Mapped[bool | None] = mapped_column(Boolean)
    verification_status: Mapped[str] = mapped_column(String(16), default="REVIEW_REQUIRED")  # APPROVED | REVIEW_REQUIRED | REJECTED
    decision_reason: Mapped[str | None] = mapped_column(Text)
    last_checked: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LegalDocument(IdMixin, Base):
    __tablename__ = "legal_documents"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('constitution_article','statute_section','rule','regulation','judgment')", name="ck_legal_doc_kind"
        ),
        CheckConstraint("data_class IN ('VERIFIED_SOURCE','SYNTHETIC')", name="ck_legal_doc_data_class"),
        CheckConstraint("quality_status IN ('pending','passed','quarantined')", name="ck_legal_doc_quality"),
        UniqueConstraint("source_id", "external_id", name="uq_legal_doc_source_external"),
    )

    source_id: Mapped[str] = mapped_column(ForeignKey("legal_sources.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(400))
    court: Mapped[str | None] = mapped_column(String(200), index=True)
    case_number: Mapped[str | None] = mapped_column(String(120))
    decision_date: Mapped[date | None] = mapped_column(Date, index=True)
    parties: Mapped[list | None] = mapped_column(JsonType)
    subject: Mapped[str | None] = mapped_column(String(200))
    jurisdiction: Mapped[str | None] = mapped_column(String(120), index=True)
    citation: Mapped[str | None] = mapped_column(String(200), index=True)
    act: Mapped[str | None] = mapped_column(String(200))  # for statute sections / rules
    section_or_article: Mapped[str | None] = mapped_column(String(40), index=True)
    source_url: Mapped[str | None] = mapped_column(String(500))
    language: Mapped[str | None] = mapped_column(String(20))
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    text: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    quality_status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | passed | quarantined
    quarantine_reason: Mapped[str | None] = mapped_column(String(300))
    # Provenance: the original source is never lost (Answer → Claim → Evidence → Document → Original Source)
    external_id: Mapped[str | None] = mapped_column(String(120), index=True)  # id within the source dataset
    document_url: Mapped[str | None] = mapped_column(String(500))  # the exact file retrieved
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    license_ref: Mapped[str | None] = mapped_column(String(200))
    neutral_citation: Mapped[str | None] = mapped_column(String(60), index=True)
    cnr: Mapped[str | None] = mapped_column(String(40))
    judges: Mapped[list | None] = mapped_column(JsonType)
    disposal: Mapped[str | None] = mapped_column(String(120))
    case_type: Mapped[str | None] = mapped_column(String(80))
    page_count: Mapped[int | None] = mapped_column(Integer)
    # VERIFIED_SOURCE (real, provenance-tracked) vs SYNTHETIC (demo only) — never mixed in retrieval
    data_class: Mapped[str] = mapped_column(String(16), default="VERIFIED_SOURCE", index=True)


class LegalChunk(IdMixin, Base):
    __tablename__ = "legal_chunks"
    __table_args__ = (UniqueConstraint("legal_document_id", "ordinal", name="uq_legal_chunk_ordinal"),)

    legal_document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(200))
    page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding_id: Mapped[str | None] = mapped_column(String(36))


class ConstitutionProvision(IdMixin, Base):
    """
    Constitution of India: Preamble, Part > Chapter > Article > Clause, plus Schedules and
    Amendments. Articles are never called "sections".
    """
    __tablename__ = "constitution_provisions"
    __table_args__ = (
        CheckConstraint("kind IN ('preamble','part','chapter','article','clause','schedule','amendment')", name="ck_constitution_kind"),
        UniqueConstraint("kind", "number", "parent_id", name="uq_constitution_node"),
    )

    kind: Mapped[str] = mapped_column(String(10), index=True)
    number: Mapped[str] = mapped_column(String(20), index=True)  # "21", "21A", "III", "Seventh", "42nd"
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("constitution_provisions.id"))
    part: Mapped[str | None] = mapped_column(String(10))
    title: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JsonType, default=list)  # e.g. "Fundamental Rights"
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(500))
    as_on_date: Mapped[date | None] = mapped_column(Date)  # date of the authoritative text version
    amendment_ref: Mapped[str | None] = mapped_column(String(120))
    content_hash: Mapped[str | None] = mapped_column(String(64))


class Embedding(IdMixin, TimestampMixin, Base):
    """
    Embedding metadata + vector. On PostgreSQL the `vector_pg` column (pgvector) is added by migration 0002
    and used for ANN search; `vector` (JSON) keeps development/test databases portable.
    """
    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("owner_type", "owner_id", "model", name="uq_embedding_owner_model"),)

    owner_type: Mapped[str] = mapped_column(String(20))  # legal_chunk | evidence
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    model: Mapped[str] = mapped_column(String(80))
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list] = mapped_column(JsonType)


class IngestionRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_runs"

    source_key: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(12), default="running")
    stats: Mapped[dict] = mapped_column(JsonType, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
