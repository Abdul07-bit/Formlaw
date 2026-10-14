"""
Re-run quality control over the corpus.

    python -m app.ingestion.validate              report problems
    python -m app.ingestion.validate --fix        quarantine documents that now fail (never auto-promotes)

Checks every searchable document still has: an APPROVED source, provenance (source/document URL, retrieval
time, licence ref), a content hash, readable text with chunks, required metadata, and no instruction-like text.
Quarantined documents are only released by a human (`--release <id>` after review).
"""
from __future__ import annotations

import argparse

import app  # noqa: F401
from sqlalchemy import func, select

from ..db.session import session_factory
from ..models import LegalChunk, LegalDocument, LegalSource
from ..security.injection import kinds_in


def problems(doc: LegalDocument, source: LegalSource, chunks: int) -> list[str]:
    out = []
    if source.verification_status != "APPROVED" and doc.data_class == "VERIFIED_SOURCE":
        out.append(f"source {source.key} is {source.verification_status}")
    if not (doc.document_url and doc.retrieved_at and doc.license_ref):
        out.append("incomplete provenance")
    if not doc.content_hash or len(doc.content_hash) != 64:
        out.append("missing hash")
    if not chunks:
        out.append("no chunks")
    if doc.kind == "judgment" and not (doc.court and doc.decision_date and (doc.neutral_citation or doc.case_number or doc.citation)):
        out.append("incomplete judgment metadata")
    if kinds_in(doc.text[:200_000]):
        out.append("instruction-like text")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate the legal corpus")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--release", help="Document id to release from quarantine after human review")
    a = ap.parse_args()
    with session_factory()() as db:
        if a.release:
            doc = db.get(LegalDocument, a.release)
            if not doc:
                raise SystemExit("not found")
            source = db.get(LegalSource, doc.source_id)
            reasons = problems(doc, source, 1)
            if any(r.startswith("source") or r == "incomplete provenance" for r in reasons):
                raise SystemExit(f"cannot release: {reasons}")
            doc.quality_status, doc.quarantine_reason = "pending", f"released by reviewer (was: {doc.quarantine_reason})"[:300]
            db.commit()
            print("released to pending; re-ingest or re-chunk before indexing")
            return
        counts = dict(db.execute(select(LegalChunk.legal_document_id, func.count()).group_by(LegalChunk.legal_document_id)).all())
        bad = 0
        for doc, source in db.execute(select(LegalDocument, LegalSource).join(LegalSource).where(LegalDocument.quality_status == "passed")):
            reasons = problems(doc, source, counts.get(doc.id, 0))
            if reasons:
                bad += 1
                print(f"FAIL {doc.id} {doc.title[:60]!r}: {'; '.join(reasons)}")
                if a.fix:
                    doc.quality_status, doc.quarantine_reason = "quarantined", "; ".join(reasons)[:300]
        q = db.scalar(select(func.count()).select_from(LegalDocument).where(LegalDocument.quality_status == "quarantined"))
        if a.fix:
            db.commit()
        print(f"checked passed documents: {bad} problem(s); quarantined total: {q}")


if __name__ == "__main__":
    main()
