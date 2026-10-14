"""
Retrieval over the ingested legal corpus:

    keyword (SQLite FTS5 / PostgreSQL tsvector)  +  vector (numpy / pgvector)  +  metadata filters
    →  reciprocal-rank fusion  →  rerank  →  evidence with full provenance

Only `passed`, VERIFIED_SOURCE documents are searchable by default; SYNTHETIC data must be requested explicitly
and is always labelled.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from ..db.session import engine
from ..models import Embedding, LegalChunk, LegalDocument, LegalSource

_WORD = re.compile(r"[A-Za-z0-9]{2,}")
_STOP = set("the and was for that with this from his her are not has have been after about which what when were who into of to in on a an is it by as at be or what does how".split())


@dataclass
class CorpusFilters:
    court: str | None = None
    jurisdiction: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    case_type: str | None = None
    topic: str | None = None
    citation: str | None = None
    article: str | None = None
    statute: str | None = None
    source: str | None = None
    kinds: list[str] = field(default_factory=list)
    include_synthetic: bool = False


@dataclass
class Hit:
    chunk: LegalChunk
    doc: LegalDocument
    source: LegalSource
    score: float

    def evidence(self, label: str) -> dict[str, Any]:
        d, s, c = self.doc, self.source, self.chunk
        return {
            "evidence_id": label, "document_id": d.id, "document_name": d.title, "kind": d.kind, "court": d.court,
            "date": d.decision_date.isoformat() if d.decision_date else None, "citation": d.citation,
            "neutral_citation": d.neutral_citation, "case_number": d.case_number, "page": c.page, "text": c.text,
            "source": s.name, "source_key": s.key, "source_status": s.verification_status, "source_url": d.source_url,
            "document_url": d.document_url, "license": d.license_ref, "attribution": s.attribution,
            "content_hash": c.content_hash, "document_hash": d.content_hash, "data_class": d.data_class, "score": round(self.score, 5),
        }


_fts_lock = threading.Lock()
_fts_ready = False


def ensure_keyword_index() -> None:
    """SQLite: create the FTS5 index + triggers if missing (migrations do this; tests use create_all)."""
    global _fts_ready
    eng = engine()
    if eng.dialect.name != "sqlite" or _fts_ready:
        return
    with _fts_lock, eng.begin() as conn:
        have = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE name IN "
                                                 "('legal_chunks_fts','legal_chunks_ai','legal_chunks_ad')"))}
        if not have >= {"legal_chunks_fts", "legal_chunks_ai", "legal_chunks_ad"}:
            # Missing table or triggers (e.g. legal_chunks was recreated): rebuild from the content table.
            conn.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS legal_chunks_fts USING fts5(text, content='legal_chunks', content_rowid='rowid')"))
            conn.execute(text("CREATE TRIGGER IF NOT EXISTS legal_chunks_ai AFTER INSERT ON legal_chunks BEGIN "
                              "INSERT INTO legal_chunks_fts(rowid, text) VALUES (new.rowid, new.text); END"))
            conn.execute(text("CREATE TRIGGER IF NOT EXISTS legal_chunks_ad AFTER DELETE ON legal_chunks BEGIN "
                              "INSERT INTO legal_chunks_fts(legal_chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text); END"))
            conn.execute(text("INSERT INTO legal_chunks_fts(legal_chunks_fts) VALUES ('rebuild')"))
        _fts_ready = True


def reset_index_cache() -> None:
    global _fts_ready, _vec_cache
    _fts_ready = False
    _vec_cache = None


def _terms(q: str) -> list[str]:
    return [t for t in _WORD.findall(q.lower()) if t not in _STOP][:24]


def _doc_conditions(f: CorpusFilters) -> list[Any]:
    conds: list[Any] = [LegalDocument.quality_status == "passed"]
    if not f.include_synthetic:
        conds.append(LegalDocument.data_class == "VERIFIED_SOURCE")
    if f.kinds:
        conds.append(LegalDocument.kind.in_(f.kinds))
    if f.court:
        conds.append(LegalDocument.court.ilike(f"%{f.court}%"))
    if f.jurisdiction:
        conds.append(LegalDocument.jurisdiction.ilike(f"%{f.jurisdiction}%"))
    if f.year_from:
        conds.append(LegalDocument.decision_date >= date(f.year_from, 1, 1))
    if f.year_to:
        conds.append(LegalDocument.decision_date <= date(f.year_to, 12, 31))
    if f.case_type:
        conds.append(LegalDocument.case_type.ilike(f"%{f.case_type}%"))
    if f.topic:
        conds.append(LegalDocument.subject.ilike(f"%{f.topic}%") | LegalDocument.title.ilike(f"%{f.topic}%"))
    if f.citation:
        c = re.sub(r"\s+", "", f.citation)
        conds.append(text("(replace(coalesce(legal_documents.citation,''),' ','') LIKE :cit OR "
                          "replace(coalesce(legal_documents.neutral_citation,''),' ','') LIKE :cit)").bindparams(cit=f"%{c}%"))
    if f.source:
        conds.append(LegalSource.key == f.source)
    return conds


def _keyword(db: Session, query: str, f: CorpusFilters, limit: int) -> list[tuple[str, float]]:
    terms = _terms(query)
    phrases = []
    if f.article:
        phrases.append(f'"article {re.sub(r"[^0-9A-Za-z]", "", f.article)}"')
    if f.statute:
        phrases.append('"' + " ".join(_terms(f.statute)) + '"')
    if not terms and not phrases:
        return []
    base = (select(LegalChunk.id).join(LegalDocument, LegalChunk.legal_document_id == LegalDocument.id)
            .join(LegalSource, LegalDocument.source_id == LegalSource.id).where(and_(*_doc_conditions(f))))
    if engine().dialect.name == "postgresql":
        tsq = " | ".join(terms) if terms else ""
        req = " & ".join(p.strip('"').replace(" ", " <-> ") for p in phrases)
        expr = f"({tsq}) & {req}" if tsq and req else (tsq or req)
        # Same expression as the GIN index (migration 0002) so the index is used. Terms are [a-z0-9] tokens only.
        vec, query_ = func.to_tsvector("english", LegalChunk.text), func.to_tsquery("english", expr)
        rank = func.ts_rank(vec, query_).label("rank")
        rows = db.execute(base.add_columns(rank).where(vec.op("@@")(query_)).order_by(rank.desc()).limit(limit)).all()
        return [(r[0], float(r[1])) for r in rows]
    ensure_keyword_index()
    # Terms are quoted, so user input can never inject FTS5 query syntax.
    match = " OR ".join(f'"{t}"' for t in terms)
    if phrases:
        match = f"({match}) AND {' AND '.join(phrases)}" if match else " AND ".join(phrases)
    ranked = db.execute(text(
        "SELECT legal_chunks.id, -bm25(legal_chunks_fts) FROM legal_chunks_fts "
        "JOIN legal_chunks ON legal_chunks.rowid = legal_chunks_fts.rowid "
        "WHERE legal_chunks_fts MATCH :m ORDER BY bm25(legal_chunks_fts) LIMIT 3000"), {"m": match}).all()
    if not ranked:
        return []
    allowed = set(db.scalars(base.where(LegalChunk.id.in_([r[0] for r in ranked]))))
    return [(cid, float(s)) for cid, s in ranked if cid in allowed][:limit]


_vec_cache: tuple[int, list[str], np.ndarray] | None = None
_vec_lock = threading.Lock()


def _vectors(db: Session, model: str) -> tuple[list[str], np.ndarray]:
    """In-process vector matrix (SQLite). Rebuilt when the embedding count changes."""
    global _vec_cache
    from sqlalchemy import func

    n = db.scalar(select(func.count()).select_from(Embedding).where(Embedding.owner_type == "legal_chunk", Embedding.model == model)) or 0
    with _vec_lock:
        if _vec_cache and _vec_cache[0] == n:
            return _vec_cache[1], _vec_cache[2]
        rows = db.execute(select(Embedding.owner_id, Embedding.vector).where(Embedding.owner_type == "legal_chunk", Embedding.model == model)).all()
        ids = [r[0] for r in rows]
        mat = np.asarray([r[1] for r in rows], dtype=np.float32) if rows else np.zeros((0, 1), dtype=np.float32)
        if len(mat):
            mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
        _vec_cache = (n, ids, mat)
        return ids, mat


def pg_vector_dim(db: Session, table: str) -> int | None:
    """Declared dimension of `<table>.vector_pg` (pgvector stores it in atttypmod); None if the column is absent."""
    v = db.scalar(text("SELECT atttypmod FROM pg_attribute WHERE attrelid = CAST(:t AS regclass) AND attname = 'vector_pg' "
                       "AND NOT attisdropped"), {"t": table})
    return int(v) if v and v > 0 else None


def _semantic(db: Session, qvec: list[float], model: str, allowed: set[str] | None, limit: int) -> list[tuple[str, float]]:
    if engine().dialect.name == "postgresql" and len(qvec) == pg_vector_dim(db, "embeddings") and db.scalar(
            select(Embedding.id).where(Embedding.owner_type == "legal_chunk", Embedding.model == model,
                                       text("embeddings.vector_pg IS NOT NULL")).limit(1)):
        import json
        rows = db.execute(text("SELECT owner_id, 1 - (vector_pg <=> CAST(:q AS vector)) AS s FROM embeddings "
                               "WHERE owner_type='legal_chunk' AND model=:m AND vector_pg IS NOT NULL ORDER BY vector_pg <=> CAST(:q AS vector) LIMIT :k"),
                          {"q": json.dumps(qvec), "m": model, "k": limit * 4}).all()
        return [(r[0], float(r[1])) for r in rows if allowed is None or r[0] in allowed][:limit]
    ids, mat = _vectors(db, model)
    if not ids:
        return []
    q = np.asarray(qvec, dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-9
    sims = mat @ q
    order = np.argsort(-sims)
    out = []
    for i in order:
        if sims[i] < 0.35:
            break
        if allowed is None or ids[i] in allowed:
            out.append((ids[i], float(sims[i])))
            if len(out) >= limit:
                break
    return out


def search_corpus(db: Session, query: str, f: CorpusFilters | None = None, *, k: int = 8, embedder=None,
                  max_per_doc: int = 2) -> list[Hit]:
    f = f or CorpusFilters()
    kw = _keyword(db, query, f, 150)
    sem: list[tuple[str, float]] = []
    if embedder is not None and query.strip():
        allowed = None
        if any(v for k_, v in vars(f).items() if k_ not in ("include_synthetic",)):
            allowed = set(db.scalars(select(LegalChunk.id).join(LegalDocument).join(LegalSource).where(and_(*_doc_conditions(f)))))
        try:
            sem = _semantic(db, embedder.embed([query], task="query")[0], embedder.model, allowed, 150)
        except Exception:  # noqa: BLE001 — embeddings are an enhancement; keyword results still stand
            sem = []
    fused: dict[str, float] = {}
    for ranked in (kw, sem):
        for r, (cid, _) in enumerate(ranked):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (60 + r + 1)
    if not fused:
        return []
    rows = db.execute(select(LegalChunk, LegalDocument, LegalSource).join(LegalDocument, LegalChunk.legal_document_id == LegalDocument.id)
                      .join(LegalSource, LegalDocument.source_id == LegalSource.id).where(LegalChunk.id.in_(list(fused)))).all()
    ql = query.lower()
    cites = [re.sub(r"\s+", "", c) for c in re.findall(r"\d{4}\s*INSC\s*\d+|\[\d{4}\]\s*\d+\s*S\.C\.R\.\s*\d+", query, re.I)]

    def rerank(ch: LegalChunk, doc: LegalDocument) -> float:
        s = fused[ch.id]
        hay = re.sub(r"\s+", "", f"{doc.citation} {doc.neutral_citation}").lower()
        s += 0.02 * sum(c.lower() in hay for c in cites)
        s += 0.004 * sum(t in (doc.title or "").lower() for t in _terms(query))
        if f.article and f"article {f.article}".lower() in ch.text.lower():
            s += 0.01
        if ql and ql in ch.text.lower():
            s += 0.005
        return s

    hits = sorted((Hit(ch, doc, src, rerank(ch, doc)) for ch, doc, src in rows), key=lambda h: h.score, reverse=True)
    per_doc: dict[str, int] = {}
    out = []
    for h in hits:
        if per_doc.get(h.doc.id, 0) >= max_per_doc:
            continue
        per_doc[h.doc.id] = per_doc.get(h.doc.id, 0) + 1
        out.append(h)
        if len(out) >= k:
            break
    return out


def find_by_citation(db: Session, citation: str) -> list[LegalDocument]:
    c = re.sub(r"\s+", "", citation).lower()
    return list(db.scalars(select(LegalDocument).where(
        LegalDocument.quality_status == "passed", LegalDocument.data_class == "VERIFIED_SOURCE",
        text("(lower(replace(coalesce(legal_documents.citation,''),' ','')) = :c OR "
             "lower(replace(coalesce(legal_documents.neutral_citation,''),' ','')) = :c)").bindparams(c=c))))


def find_by_parties(db: Session, a: str, b: str) -> list[LegalDocument]:
    def toks(s: str) -> list[str]:
        return [t for t in _terms(s) if t not in {"state", "union", "india", "others", "anr", "ors"}][:3] or _terms(s)[:2]
    q = select(LegalDocument).where(LegalDocument.quality_status == "passed", LegalDocument.data_class == "VERIFIED_SOURCE",
                                    LegalDocument.kind == "judgment")
    for t in toks(a) + toks(b):
        q = q.where(LegalDocument.title.ilike(f"%{t}%"))
    return list(db.scalars(q.limit(5)))
