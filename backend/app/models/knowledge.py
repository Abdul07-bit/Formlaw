"""
Case knowledge produced by agents and reviewed by the lawyer. Every row records the run that produced it
(provenance) and carries organization_id + case_id for isolation. `key` de-duplicates the same finding across runs.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin
from ..domain.enums import ClaimStatus, Confidence, ReviewStatus, check_in


class _CaseScoped:
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Evidence(IdMixin, TimestampMixin, _CaseScoped, Base):
    """A quoted span of a case document. Claims cite evidence; evidence points at the exact chunk."""
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("case_id", "key", name="uq_evidence_key"),)

    key: Mapped[str] = mapped_column(String(64))  # sha256(chunk_id + quote)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column()
    paragraph: Mapped[int] = mapped_column()
    section: Mapped[str | None] = mapped_column(String(160))
    quote: Mapped[str] = mapped_column(Text)  # verbatim text from the chunk
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 of the chunk text at citation time
    source_type: Mapped[str] = mapped_column(String(20), default="case_document")
    first_run_id: Mapped[str | None] = mapped_column(String(36))


class Claim(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(check_in("status", ClaimStatus), name="ck_claim_status"),
        CheckConstraint(check_in("confidence", Confidence), name="ck_claim_confidence"),
        CheckConstraint(check_in("review_status", ReviewStatus), name="ck_claim_review"),
        UniqueConstraint("case_id", "key", name="uq_claim_key"),
    )

    key: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    agent: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(30), default="fact")  # fact | allegation | admission | issue | finding | contract_* | answer
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[str] = mapped_column(String(6), default=Confidence.MEDIUM)
    reason: Mapped[str] = mapped_column(String(400), default="")
    review_status: Mapped[str] = mapped_column(String(10), default=ReviewStatus.UNREVIEWED)
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(500))


class Citation(IdMixin, Base):
    __tablename__ = "citations"
    __table_args__ = (CheckConstraint("(evidence_id IS NOT NULL) OR (authority_id IS NOT NULL)", name="ck_citation_target"),)

    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    authority_id: Mapped[str | None] = mapped_column(ForeignKey("legal_authorities.id", ondelete="CASCADE"))


class Contradiction(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "contradictions"
    __table_args__ = (
        UniqueConstraint("case_id", "key", name="uq_contradiction_key"),
        CheckConstraint("status IN ('open','resolved','dismissed')", name="ck_contradiction_status"),
    )

    key: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(36))
    topic: Mapped[str] = mapped_column(String(160))
    statement_a: Mapped[str] = mapped_column(Text)
    statement_b: Mapped[str] = mapped_column(Text)
    evidence_a_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    evidence_b_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    nature: Mapped[str] = mapped_column(String(30))  # date | amount | statement | clause | identity
    confidence: Mapped[str] = mapped_column(String(6), default=Confidence.MEDIUM)
    provenance: Mapped[dict] = mapped_column(JsonType, default=dict)  # source assessment + corroboration found
    status: Mapped[str] = mapped_column(String(10), default="open")
    resolution_note: Mapped[str | None] = mapped_column(String(500))


MISSING_BASES = ("referenced_in_documents", "checklist", "conflict_resolution", "template_field", "timeline_gap")


class MissingInformation(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "missing_information"
    __table_args__ = (
        UniqueConstraint("case_id", "key", name="uq_missing_key"),
        CheckConstraint("status IN ('open','requested','resolved','dismissed')", name="ck_missing_status"),
        CheckConstraint(f"basis IN ({','.join(repr(b) for b in MISSING_BASES)})", name="ck_missing_basis"),
    )

    key: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200))
    why_needed: Mapped[str] = mapped_column(Text, default="")
    basis: Mapped[str] = mapped_column(String(30), default="checklist")
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id", ondelete="SET NULL"))
    importance: Mapped[str] = mapped_column(String(6), default="medium")
    status: Mapped[str] = mapped_column(String(10), default="open")


class TimelineEvent(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "timeline_events"
    __table_args__ = (
        UniqueConstraint("case_id", "key", name="uq_timeline_key"),
        Index("ix_timeline_case_date", "case_id", "event_date"),
    )

    key: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(36))
    event_date: Mapped[date | None] = mapped_column(Date)
    date_text: Mapped[str] = mapped_column(String(60))  # as written in the document
    description: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(40), default="event")
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12), default="consistent")  # consistent | conflicted


class LegalAuthority(IdMixin, TimestampMixin, _CaseScoped, Base):
    """Snapshot of a verified-corpus passage used in this case. Never generated: always points to a corpus row."""
    __tablename__ = "legal_authorities"
    __table_args__ = (UniqueConstraint("case_id", "key", name="uq_authority_key"),)

    key: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str | None] = mapped_column(String(36))
    legal_document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id"))
    legal_chunk_id: Mapped[str] = mapped_column(ForeignKey("legal_chunks.id"))
    authority_type: Mapped[str] = mapped_column(String(24))  # judgment | statute_section | constitution_article | regulation | rule
    title: Mapped[str] = mapped_column(String(400))
    citation: Mapped[str | None] = mapped_column(String(200))
    court: Mapped[str | None] = mapped_column(String(200))
    decision_date: Mapped[date | None] = mapped_column(Date)
    page: Mapped[int | None] = mapped_column()
    quote: Mapped[str] = mapped_column(Text)
    issue: Mapped[str] = mapped_column(String(300), default="")
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str | None] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(10), default=ReviewStatus.UNREVIEWED)


class Draft(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "drafts"
    __table_args__ = (CheckConstraint("status IN ('draft','approved','shared')", name="ck_draft_status"),)

    run_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(30))  # legal_notice | case_summary | research_memo | chronology | client_update | ...
    title: Mapped[str] = mapped_column(String(200))
    sections: Mapped[dict] = mapped_column(JsonType, default=dict)  # facts / authorities / inferences / recommendations / body
    body: Mapped[str] = mapped_column(Text, default="")  # lawyer-editable text
    status: Mapped[str] = mapped_column(String(10), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(String(36))
    approved_by: Mapped[str | None] = mapped_column(String(36))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Task(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("status IN ('open','done')", name="ck_task_status"),)

    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(6), default="open")
    due_date: Mapped[date | None] = mapped_column(Date)
    assignee_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(10), default="lawyer")  # lawyer | agent (suggested; lawyer created it)
    created_by: Mapped[str] = mapped_column(String(36))


class SavedFinding(IdMixin, TimestampMixin, _CaseScoped, Base):
    __tablename__ = "saved_findings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[dict] = mapped_column(JsonType, default=dict)  # snapshot of the answer / claim and its citations
    message_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str] = mapped_column(Text, default="")
