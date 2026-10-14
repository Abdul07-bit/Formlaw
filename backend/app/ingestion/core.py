"""
Shared ingestion stages. Every adapter yields IngestItems; process() runs each one through:

    FILE VALIDATION → HASH → DEDUPLICATION → TEXT EXTRACTION → NORMALIZATION → INJECTION SCAN
    → METADATA QC → CHUNKING → STORE (searchable only if every check passes, otherwise quarantined)

(LICENSE / TERMS CHECK happens before an adapter runs; EMBEDDING + INDEXING run in `app.ingestion.index`.)
External legal documents are untrusted content: nothing in them can change system behaviour.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LegalChunk, LegalDocument, LegalSource
from ..security.injection import kinds_in
from .extract import extract
from .normalize import chunk_pages, clean_meta, normalize

log = logging.getLogger("formlaw.ingestion")

MAX_FILE = 40 * 1024 * 1024
MIN_TEXT = 500
# Active PDF content. (/OpenAction and /AA alone are common view settings; scripts and launches are not.)
PDF_DANGEROUS = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia|XFA)\b")
REQUIRED = {"judgment": ("title", "court", "decision_date"), "statute_section": ("title", "act"), "constitution_article": ("title",)}


@dataclass
class IngestItem:
    external_id: str
    kind: str  # judgment | statute_section | rule | regulation | constitution_article
    file_kind: str  # pdf | docx | text
    data: bytes
    document_url: str
    meta: dict[str, Any] = field(default_factory=dict)
    expected_year: int | None = None


@dataclass
class Stats:
    seen: int = 0
    inserted: int = 0
    quarantined: int = 0
    duplicates: int = 0
    conflicts: int = 0
    out_of_window: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {**{k: v for k, v in vars(self).items() if k != "errors"}, "errors": self.errors[:50]}


def _validate_file(item: IngestItem) -> str | None:
    if not item.data:
        return "empty file"
    if len(item.data) > MAX_FILE:
        return "file exceeds size cap"
    if item.file_kind == "pdf":
        if not item.data[:1024].lstrip().startswith(b"%PDF-"):
            return "content is not a PDF"
        if PDF_DANGEROUS.search(item.data):
            return "PDF contains active content (scripts/launch/embedded files)"
    return None


def _parse_date(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    if not v:
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def process(db: Session, source: LegalSource, item: IngestItem, stats: Stats, *, license_ref: str,
            window_start: date | None = None) -> LegalDocument | None:
    stats.seen += 1
    reasons: list[str] = []

    if (bad := _validate_file(item)):  # FILE VALIDATION
        reasons.append(bad)
    digest = hashlib.sha256(item.data).hexdigest()  # HASH (of the original bytes)

    # DEDUPLICATION + duplicate-poisoning defence: never overwrite an existing record silently.
    if db.scalar(select(LegalDocument.id).where(LegalDocument.content_hash == digest)):
        stats.duplicates += 1
        return None
    existing = db.scalar(select(LegalDocument).where(LegalDocument.source_id == source.id, LegalDocument.external_id == item.external_id))
    if existing:
        stats.conflicts += 1
        log.warning("ingest conflict source=%s id=%s: different content for an existing record (kept original)", source.key, item.external_id)
        return None

    meta = {k: (clean_meta(v, 600) if isinstance(v, str) else v) for k, v in item.meta.items()}
    decided = _parse_date(meta.get("decision_date"))
    if item.kind == "judgment" and window_start and decided and decided < window_start:
        stats.out_of_window += 1
        return None

    text, pages = "", None
    if not reasons:
        ex = extract(item.file_kind, item.data)  # TEXT EXTRACTION
        if ex.status != "extracted":
            reasons.append(ex.note or "no extractable text")
        text, pages = ex.text, ex.pages
    clean = normalize(re.sub(r"\[\[PAGE \d+\]\]", "\n", text))  # NORMALIZATION

    # QUALITY CHECK
    if text and len(clean) < MIN_TEXT:
        reasons.append("too little text")
    if clean and sum(c.isalpha() for c in clean) / max(len(clean), 1) < 0.5:
        reasons.append("text looks corrupted (low letter ratio)")
    if clean and kinds_in(clean[:200_000]):
        reasons.append("instruction-like text found; held for human review")
    missing = [f for f in REQUIRED.get(item.kind, ("title",)) if not (decided if f == "decision_date" else meta.get(f))]
    if missing:
        reasons.append("missing metadata: " + ", ".join(missing))
    if item.kind == "judgment" and not (meta.get("neutral_citation") or meta.get("case_number") or meta.get("citation")):
        reasons.append("missing metadata: citation or case number")
    if decided and (decided.year < 1950 or decided > date.today()):
        reasons.append("implausible decision date")
    if decided and item.expected_year and decided.year != item.expected_year:
        reasons.append(f"decision date {decided} does not match dataset partition {item.expected_year}")

    doc = LegalDocument(
        source_id=source.id, kind=item.kind, title=(meta.get("title") or item.external_id)[:400], court=meta.get("court"),
        case_number=meta.get("case_number"), decision_date=decided, parties=meta.get("parties"), subject=(meta.get("subject") or None) and meta["subject"][:200],
        jurisdiction=meta.get("jurisdiction") or source.jurisdiction, citation=meta.get("citation"), act=meta.get("act"),
        section_or_article=meta.get("section_or_article"), source_url=meta.get("source_url") or source.terms_url,
        language=meta.get("language") or "en", content_hash=digest, text=clean, external_id=item.external_id,
        document_url=item.document_url, retrieved_at=datetime.now(timezone.utc),
        license_ref=str(meta.get("license") or license_ref)[:200],  # per-document licence (manual import) wins
        neutral_citation=meta.get("neutral_citation"), cnr=meta.get("cnr"), judges=meta.get("judges"), disposal=meta.get("disposal"),
        case_type=meta.get("case_type"), page_count=pages, data_class="VERIFIED_SOURCE",
        quality_status="quarantined" if reasons else "passed", quarantine_reason="; ".join(reasons)[:300] or None,
    )
    db.add(doc)
    db.flush()
    if reasons:
        stats.quarantined += 1
        return doc
    for i, (page, heading, chunk) in enumerate(chunk_pages(text)):  # CHUNKING (page-aware)
        db.add(LegalChunk(legal_document_id=doc.id, ordinal=i, heading=heading, page=page, text=chunk,
                          content_hash=hashlib.sha256(chunk.encode()).hexdigest()))
    stats.inserted += 1
    return doc
