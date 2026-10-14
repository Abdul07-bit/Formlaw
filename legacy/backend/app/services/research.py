"""
Legal Research Agent over the trusted corpus: constitutional Articles, statute sections, rules, regulations and
judgments — kept as distinct kinds, each with provenance. Nothing is generated: missing authorities are reported.

Sources searched:
* the ingested corpus (legal_documents/legal_chunks — e.g. Supreme Court judgments, CC-BY-4.0),
* the constitutional layer (constitution_provisions, once imported from a permitted source),
* the original project's IPC/CrPC excerpts (agents/legal/corpus.py) — labelled REVIEW_REQUIRED pending a terms review.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import legal_bridge
from ..agents.llm.provider import get_embedder
from ..models import ConstitutionProvision
from ..retrieval.hybrid import Passage, content_hash, search
from ..retrieval.legal_corpus import CorpusFilters, search_corpus


def _legacy_passages() -> list[Passage]:
    out = []
    for d in legal_bridge.trusted_corpus():
        if d["type"] == "statute":
            out.append(Passage(f"corpus:{d['doc_id']}", d["text"], d["doc_id"], d["title"], section=f"Section {d['section']}", source="statute",
                               source_url=d["source_url"], metadata={"kind": "statute_section", "reference": f"Section {d['section']}, {d['title']}",
                                                                     "jurisdiction": "India", "source_name": "India Code excerpt (original project corpus)"}))
        else:
            out.append(Passage(f"corpus:{d['doc_id']}", d.get("holding", ""), d["doc_id"], d["title"], source="judgment", source_url=d["source_url"],
                               metadata={"kind": "judgment", "reference": d.get("citation"), "court": d.get("court"),
                                         "date": f"{d.get('year')}-01-01" if d.get("year") else None, "jurisdiction": "India",
                                         "source_name": "Original project corpus (holding summary)"}))
    return out


def _constitution_passages(db: Session) -> list[Passage]:
    out = []
    for p in db.scalars(select(ConstitutionProvision).where(ConstitutionProvision.kind.in_(("article", "clause", "schedule", "amendment")))):
        if not p.text:
            continue
        label = {"article": "Article", "clause": "Article", "schedule": "Schedule", "amendment": "Amendment"}[p.kind]
        out.append(Passage(f"const:{p.id}", p.text, p.id, f"Constitution of India — {label} {p.number}" + (f": {p.title}" if p.title else ""),
                           section=f"{label} {p.number}", source="constitution", source_url=p.source_url,
                           metadata={"kind": "constitution_article", "reference": f"{label} {p.number}", "jurisdiction": "India",
                                     "date": p.as_on_date.isoformat() if p.as_on_date else None, "source_name": p.source_name}))
    return out


def research(db: Session, query: str, *, filters: CorpusFilters, limit: int) -> dict[str, Any]:
    results: list[tuple[float, dict[str, Any]]] = []

    for rank, h in enumerate(search_corpus(db, query, filters, k=limit, embedder=get_embedder())):
        e = h.evidence(f"R{rank + 1}")
        results.append((1 / (60 + rank + 1), {
            "id": f"legal:{h.chunk.id}", "kind": h.doc.kind, "title": h.doc.title,
            "reference": h.doc.neutral_citation or h.doc.citation or h.doc.case_number, "court": h.doc.court, "date": e["date"],
            "text": h.chunk.text[:1200], "source_name": h.source.name, "source_url": h.doc.source_url, "content_hash": h.chunk.content_hash,
            "score": e["score"], "citation": h.doc.citation, "neutral_citation": h.doc.neutral_citation, "case_number": h.doc.case_number,
            "page": h.chunk.page, "document_url": h.doc.document_url, "source_status": h.source.verification_status,
            "data_class": h.doc.data_class, "license": h.doc.license_ref,
        }))

    # Small in-memory layers: constitutional provisions + the original project's excerpts.
    small = _constitution_passages(db) + _legacy_passages()
    small_filters = {"kind": filters.kinds or None, "jurisdiction": filters.jurisdiction, "court": filters.court}
    if not (filters.year_from or filters.year_to or filters.case_type or filters.citation or filters.source):
        q = query + (f" article {filters.article}" if filters.article else "") + (f" {filters.statute}" if filters.statute else "")
        for rank, (p, score) in enumerate(search(small, q, k=limit, filters=small_filters)):
            legacy = p.id.startswith("corpus:")
            results.append((1 / (60 + rank + 1), {
                "id": p.id, "kind": p.metadata.get("kind", p.source), "title": p.document_name, "reference": p.metadata.get("reference"),
                "court": p.metadata.get("court"), "date": p.metadata.get("date"), "text": p.text[:1200],
                "source_name": p.metadata.get("source_name", ""), "source_url": p.source_url, "content_hash": content_hash(p.text),
                "score": score, "source_status": "REVIEW_REQUIRED" if legacy else "APPROVED", "data_class": "VERIFIED_SOURCE",
            }))

    results.sort(key=lambda x: x[0], reverse=True)
    wants_article = bool(filters.article or re.search(r"\barticles?\s+\d+|fundamental right|directive principle|constitution", query, re.I))
    note = None
    if wants_article and not any(r["kind"] == "constitution_article" for _, r in results):
        note = ("The Constitution of India has not been imported: its official source requires prior permission (see the source registry). "
                "FormLaw does not generate constitutional text.")
    elif not results:
        note = "No authority in the verified corpus matches this query. Nothing has been generated in its place."
    return {"query": query, "results": [r for _, r in results[:limit]], "note": note}
