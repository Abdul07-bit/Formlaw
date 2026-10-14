"""
Corpus status per source.

    python -m app.ingestion.status
"""
from __future__ import annotations

from typing import Any

import app  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.session import session_factory
from ..models import ConstitutionProvision, Embedding, IngestionRun, LegalChunk, LegalDocument, LegalSource


def corpus_status(db: Session) -> dict[str, Any]:
    rows = []
    for s in db.scalars(select(LegalSource).order_by(LegalSource.key)):
        base = select(func.count()).select_from(LegalDocument).where(LegalDocument.source_id == s.id)
        passed = db.scalar(base.where(LegalDocument.quality_status == "passed")) or 0
        quarantined = db.scalar(base.where(LegalDocument.quality_status == "quarantined")) or 0
        lo, hi = db.execute(select(func.min(LegalDocument.decision_date), func.max(LegalDocument.decision_date))
                            .where(LegalDocument.source_id == s.id, LegalDocument.quality_status == "passed")).one()
        indexed = db.scalar(select(func.count(func.distinct(LegalChunk.legal_document_id))).select_from(LegalChunk)
                            .join(LegalDocument).join(Embedding, (Embedding.owner_type == "legal_chunk") & (Embedding.owner_id == LegalChunk.id))
                            .where(LegalDocument.source_id == s.id)) or 0
        last = db.scalar(select(IngestionRun).where(IngestionRun.source_key == s.key).order_by(IngestionRun.created_at.desc()).limit(1))
        stats = (last.stats or {}) if last else {}
        rows.append({
            "source": s.key, "name": s.name, "status": s.verification_status, "documents": passed, "quarantined": quarantined,
            "coverage": f"{lo.year}-{hi.year}" if lo and hi else "-", "failed": len(stats.get("errors", [])),
            "duplicates": stats.get("duplicates", 0), "indexed": indexed, "last_run": last.created_at.isoformat(timespec="minutes") if last else "-",
        })
    docs = select(LegalDocument).where(LegalDocument.quality_status == "passed", LegalDocument.data_class == "VERIFIED_SOURCE")
    lo, hi = db.execute(select(func.min(LegalDocument.decision_date), func.max(LegalDocument.decision_date))
                        .where(LegalDocument.quality_status == "passed", LegalDocument.kind == "judgment")).one()
    return {
        "sources": rows,
        "totals": {
            "documents": db.scalar(select(func.count()).select_from(docs.subquery())) or 0,
            "judgments": db.scalar(select(func.count()).select_from(docs.where(LegalDocument.kind == "judgment").subquery())) or 0,
            "statutes": db.scalar(select(func.count()).select_from(docs.where(LegalDocument.kind.in_(("statute_section", "rule", "regulation"))).subquery())) or 0,
            "constitution_provisions": db.scalar(select(func.count()).select_from(ConstitutionProvision).where(ConstitutionProvision.text.is_not(None))) or 0,
            "courts": db.scalar(select(func.count(func.distinct(LegalDocument.court))).where(LegalDocument.quality_status == "passed")) or 0,
            "sources_with_data": sum(1 for r in rows if r["documents"]),
            "coverage": f"{lo.year}-{hi.year}" if lo and hi else None,
            "chunks": db.scalar(select(func.count()).select_from(LegalChunk)) or 0,
            "embedded_chunks": db.scalar(select(func.count()).select_from(Embedding).where(Embedding.owner_type == "legal_chunk")) or 0,
            "quarantined": db.scalar(select(func.count()).select_from(LegalDocument).where(LegalDocument.quality_status == "quarantined")) or 0,
        },
    }


def main() -> None:
    with session_factory()() as db:
        st = corpus_status(db)
    cols = ["source", "status", "documents", "coverage", "quarantined", "failed", "duplicates", "indexed", "last_run"]
    print("  ".join(f"{c:<22}" if c == "source" else f"{c:<16}" for c in cols))
    for r in st["sources"]:
        print("  ".join(f"{str(r[c]):<22}" if c == "source" else f"{str(r[c]):<16}" for c in cols))
    print("\nTotals:", st["totals"])


if __name__ == "__main__":
    main()
