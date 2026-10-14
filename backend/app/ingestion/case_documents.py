"""
Case document ingestion:

  VALIDATE → HASH (per-case dedupe) → ENCRYPT + STORE → EXTRACT → NORMALIZE → PROFILE (type, dates, references)
  → SECURITY SCAN (per chunk) → CHUNK (page / paragraph / section / offsets) → EMBED (if configured) → INDEX

A document that contains instructions is NOT rejected: it is legal evidence (a forged affidavit can matter). Its
flagged chunks are marked so they never enter a model prompt; a security event and an audit record are written.
"""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import Conflict, Unprocessable
from ..domain.enums import DocumentStatus
from ..llm.providers import LLMError, LLMOutputError, get_embedder
from ..models import ChunkEmbedding, Document, DocumentChunk
from ..security.files import validate_upload
from ..security.injection import scan
from ..services import audit
from ..services.storage import storage
from .chunker import chunk_text
from .extract import extract
from .profile import profile
from .text import normalize, split_pages, with_page_markers

log = logging.getLogger("formlaw.ingestion.case")
SECURITY_ACTIONS = ["Instruction text treated as evidence only", "Flagged passages excluded from AI prompts",
                    "Security event logged", "Document kept available as evidence"]


MALICIOUS_CODES = {"active_content", "archive_bomb", "content_mismatch", "macro_content"}


def _record_malicious(organization_id: str, case_id: str, actor_id: str, filename: str, e: Unprocessable) -> None:
    """The request transaction rolls back on rejection, so the security event is written in its own session."""
    from ..db.session import session_factory
    with session_factory()() as s2:
        audit.security_event(s2, kind="malicious_file", source=filename[:200], snippet=e.message,
                             actions=["Upload refused", "File not stored", "Security event logged"], organization_id=organization_id,
                             case_id=case_id, actor_id=actor_id)
        audit.record(s2, action="document.upload", result="blocked", resource_type="case", resource_id=case_id, risk="HIGH",
                     organization_id=organization_id, case_id=case_id, detail=f"{e.code}: {filename[:80]}")
        s2.commit()


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def ingest(db: Session, *, organization_id: str, case_id: str, uploaded_by: str, filename: str, declared_type: str | None,
           data: bytes, source: str = "lawyer_upload", is_demo: bool = False) -> Document:
    s = get_settings()
    try:
        v = validate_upload(filename, declared_type, data, s.max_upload_bytes)
    except Unprocessable as e:
        if e.code in MALICIOUS_CODES:
            _record_malicious(organization_id, case_id, uploaded_by, filename, e)
        raise
    digest = sha256(data)
    if db.scalar(select(Document.id).where(Document.case_id == case_id, Document.content_hash == digest)):
        raise Conflict(f"“{v.display_name}” is already in this case", code="duplicate_document")

    doc = Document(case_id=case_id, organization_id=organization_id, uploaded_by=uploaded_by, filename=v.display_name,
                   mime_type=v.content_type, size=len(data), content_hash=digest, storage_key=storage().put(data),
                   source=source, is_demo=is_demo)
    db.add(doc)
    db.flush()

    ex = extract(v.kind, data)
    if ex.status != "extracted":
        doc.status = DocumentStatus.NEEDS_OCR if ex.status == "needs_ocr" else DocumentStatus.FAILED
        doc.status_note, doc.pages = ex.note, ex.pages
        audit.record(db, action="document.ingest", result="error" if ex.status == "failed" else "success", actor=None,
                     resource_type="document", resource_id=doc.id, risk="MEDIUM", organization_id=organization_id,
                     case_id=case_id, detail=ex.note)
        return doc

    text = with_page_markers([normalize(t) for _, t in split_pages(ex.text)]) if "[[PAGE" in ex.text else normalize(ex.text)
    prof = profile(v.display_name, text)
    doc.doc_type, doc.pages = prof.doc_type, ex.pages
    doc.meta = {"dates": prof.dates[:30], "references": prof.references,
                **({"templateFields": prof.template_fields} if prof.doc_type == "template" else {})}

    raw = chunk_text(text)
    flags_found: set[str] = set()
    spans: list[str] = []
    rows: list[DocumentChunk] = []
    for c in raw:
        finding = scan(c.text)
        if finding.flagged:
            flags_found |= finding.kinds
            spans += finding.spans
        rows.append(DocumentChunk(document_id=doc.id, case_id=case_id, organization_id=organization_id, ordinal=c.ordinal,
                                  page=c.page, paragraph=c.paragraph, section=c.section, text=c.text, char_start=c.char_start,
                                  char_end=c.char_end, content_hash=sha256(c.text), security_flags=sorted(finding.kinds)))
    db.add_all(rows)
    db.flush()
    doc.status = DocumentStatus.INDEXED if rows else DocumentStatus.FAILED
    doc.status_note = None if rows else "No readable text"

    if flags_found:
        doc.security_flags = sorted(flags_found)
        ev = audit.security_event(db, kind=sorted(flags_found, key=lambda k: k != "exfiltration")[0], source=v.display_name,
                                  snippet=" … ".join(spans), actions=SECURITY_ACTIONS, organization_id=organization_id,
                                  case_id=case_id, document_id=doc.id, actor_id=uploaded_by)
        audit.record(db, action="document.injection_detected", result="blocked", resource_type="document", resource_id=doc.id,
                     risk="HIGH", organization_id=organization_id, case_id=case_id, security_event_id=ev.id,
                     detail=f"{len(spans)} instruction-like passage(s) flagged")

    _embed(db, case_id, rows)
    audit.record(db, action="document.ingest", result="success", resource_type="document", resource_id=doc.id, risk="MEDIUM",
                 organization_id=organization_id, case_id=case_id, detail=f"{len(rows)} chunks, type={doc.doc_type}")
    return doc


def _embed(db: Session, case_id: str, rows: list[DocumentChunk]) -> None:
    embedder = get_embedder()
    if not embedder or not rows:
        return
    try:
        vecs = embedder.embed([r.text for r in rows], task="document")
    except (LLMError, LLMOutputError) as e:
        log.warning("case chunk embedding skipped (%s); keyword retrieval still available", type(e).__name__)
        return
    for r, v in zip(rows, vecs):
        db.add(ChunkEmbedding(chunk_id=r.id, model=embedder.model, case_id=case_id, dim=len(v), vector=v))
