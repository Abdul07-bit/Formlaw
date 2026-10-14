"""
Hybrid retrieval over one case's documents.

    query → expansion (curated legal synonyms) → BM25 (light stemming) ∥ cosine over chunk embeddings (if any)
          → metadata filters (documents, doc types, pages) → reciprocal-rank fusion → rerank → evidence items

Isolation: chunks are loaded with BOTH organization_id and case_id. A caller cannot widen the scope.
The per-case index is held in-process (keyed by the case's chunk set) — appropriate for case-sized corpora; the
legal corpus, which is large, uses FTS5 / tsvector + pgvector (retrieval/legal_corpus.py).
"""
from __future__ import annotations

import math
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..llm.providers import LLMError, LLMOutputError, get_embedder
from ..models import ChunkEmbedding, Document, DocumentChunk
from .expansion import expand

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("the and was for that with this from his her are not has have been after about which what when were who whom into "
            "of to in on a an is it by as at be or does did do any all case document documents find show me please".split())
_KEYTERM = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+[a-z]+\s+\d{4}\b|\b(?:section|clause|article)\s+\d+[a-z]?\b|\b\d[\d,.]{2,}\b", re.I)


def stem(t: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "edly", "ed", "es", "s"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def tokens(text: str) -> list[str]:
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class EvidenceHit:
    chunk_id: str
    document_id: str
    document_name: str
    doc_type: str
    page: int
    paragraph: int
    section: str | None
    text: str
    content_hash: str
    score: float
    security_flags: list[str] = field(default_factory=list)
    source_type: str = "case_document"

    @property
    def flagged(self) -> bool:
        return bool(self.security_flags)

    @property
    def label(self) -> str:
        return f"{self.document_name} · p.{self.page} ¶{self.paragraph}"

    def as_dict(self) -> dict[str, Any]:
        return {"chunkId": self.chunk_id, "documentId": self.document_id, "documentName": self.document_name, "docType": self.doc_type,
                "page": self.page, "paragraph": self.paragraph, "section": self.section, "text": self.text,
                "contentHash": self.content_hash, "relevance": round(self.score, 4), "sourceType": self.source_type,
                "securityFlags": self.security_flags}


@dataclass
class _Index:
    key: tuple
    rows: list[tuple[DocumentChunk, Document]]
    tf: list[Counter]
    lengths: list[int]
    idf: dict[str, float]
    avgdl: float


_cache: dict[str, _Index] = {}
_lock = threading.Lock()


def _load(db: Session, organization_id: str, case_id: str) -> _Index:
    sig = db.execute(select(func.count(DocumentChunk.id), func.max(DocumentChunk.id)).where(
        DocumentChunk.organization_id == organization_id, DocumentChunk.case_id == case_id)).one()
    key = (organization_id, case_id, sig[0], sig[1])
    with _lock:
        idx = _cache.get(case_id)
        if idx and idx.key == key:
            return idx
    rows = db.execute(select(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id).where(
        DocumentChunk.organization_id == organization_id, DocumentChunk.case_id == case_id,
        Document.organization_id == organization_id, Document.case_id == case_id).order_by(Document.created_at, DocumentChunk.ordinal)).all()
    docs_tokens = [tokens(f"{c.section or ''} {c.text}") for c, _ in rows]
    df: Counter[str] = Counter()
    for t in docs_tokens:
        df.update(set(t))
    n = max(len(rows), 1)
    idx = _Index(key, [(c, d) for c, d in rows], [Counter(t) for t in docs_tokens], [len(t) for t in docs_tokens],
                 {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()},
                 sum(len(t) for t in docs_tokens) / n)
    with _lock:
        _cache[case_id] = idx
    return idx


def invalidate(case_id: str) -> None:
    with _lock:
        _cache.pop(case_id, None)


def _bm25(idx: _Index, query: str, k1: float = 1.4, b: float = 0.75) -> list[float]:
    q = set(tokens(query))
    out = []
    for tf, dl in zip(idx.tf, idx.lengths):
        s = 0.0
        for t in q:
            f = tf.get(t)
            if f:
                s += idx.idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / max(idx.avgdl, 1)))
        out.append(s)
    return out


def _semantic(db: Session, idx: _Index, case_id: str, query: str) -> dict[str, float]:
    embedder = get_embedder()
    if not embedder:
        return {}
    rows = db.execute(select(ChunkEmbedding.chunk_id, ChunkEmbedding.vector).where(
        ChunkEmbedding.case_id == case_id, ChunkEmbedding.model == embedder.model)).all()
    if not rows:
        return {}
    try:
        qv = np.asarray(embedder.embed([query], task="query")[0], dtype=np.float32)
    except (LLMError, LLMOutputError):
        return {}  # embeddings are an enhancement; keyword results still stand
    allowed = {c.id for c, _ in idx.rows}
    ids = [r[0] for r in rows if r[0] in allowed]
    mat = np.asarray([r[1] for r in rows if r[0] in allowed], dtype=np.float32)
    if not len(mat):
        return {}
    sims = (mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)) @ (qv / (np.linalg.norm(qv) + 1e-9))
    return {cid: float(s) for cid, s in zip(ids, sims) if s > 0.3}


@dataclass
class SearchResult:
    hits: list[EvidenceHit]
    query_used: str
    semantic: bool
    total_chunks: int

    @property
    def strength(self) -> float:
        return self.hits[0].score if self.hits else 0.0


def search(db: Session, *, organization_id: str, case_id: str, query: str, k: int = 8, document_ids: list[str] | None = None,
           doc_types: list[str] | None = None, exclude_chunk_ids: set[str] | None = None, broaden: bool = False,
           max_per_document: int = 4) -> SearchResult:
    idx = _load(db, organization_id, case_id)
    q = expand(query, aggressive=broaden)
    if not idx.rows or not q.strip():
        return SearchResult([], q, False, len(idx.rows))
    kw = _bm25(idx, q)
    sem = _semantic(db, idx, case_id, query)

    def allowed(i: int) -> bool:
        c, d = idx.rows[i]
        return ((not document_ids or d.id in document_ids) and (not doc_types or d.doc_type in doc_types)
                and (not exclude_chunk_ids or c.id not in exclude_chunk_ids))

    pool = [i for i in range(len(idx.rows)) if allowed(i)]
    fused: dict[int, float] = {}
    for r, i in enumerate(sorted((i for i in pool if kw[i] > 0), key=lambda i: kw[i], reverse=True)):
        fused[i] = 1 / (60 + r + 1)
    if sem:
        by_id = {idx.rows[i][0].id: i for i in pool}
        for r, (cid, _s) in enumerate(sorted(sem.items(), key=lambda kv: kv[1], reverse=True)):
            if cid in by_id:
                fused[by_id[cid]] = fused.get(by_id[cid], 0) + 1 / (60 + r + 1)

    ql = query.lower()
    keyterms = [t.lower() for t in _KEYTERM.findall(query)]
    qtok = set(tokens(query))

    def rerank(i: int) -> float:
        c, d = idx.rows[i]
        text = c.text.lower()
        s = fused[i]
        s += 0.004 * len(qtok & set(idx.tf[i]))                       # coverage of the original (unexpanded) terms
        s += 0.01 * sum(kt in text for kt in keyterms)                # dates / sections / amounts in the query
        s += 0.006 if len(ql) > 12 and ql in text else 0              # exact phrase
        s += 0.004 if d.doc_type.replace("_", " ") in ql else 0       # "the remand report says…"
        return s

    hits: list[EvidenceHit] = []
    per_doc: Counter[str] = Counter()
    for i in sorted(fused, key=rerank, reverse=True):
        c, d = idx.rows[i]
        if per_doc[d.id] >= max_per_document:
            continue
        per_doc[d.id] += 1
        hits.append(EvidenceHit(c.id, d.id, d.filename, d.doc_type, c.page, c.paragraph, c.section, c.text, c.content_hash,
                                rerank(i), list(c.security_flags or [])))
        if len(hits) >= k:
            break
    return SearchResult(hits, q, bool(sem), len(idx.rows))


def get_chunks(db: Session, *, organization_id: str, case_id: str, chunk_ids: list[str]) -> list[EvidenceHit]:
    rows = db.execute(select(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id).where(
        DocumentChunk.id.in_(chunk_ids), DocumentChunk.organization_id == organization_id, DocumentChunk.case_id == case_id)).all()
    return [EvidenceHit(c.id, d.id, d.filename, d.doc_type, c.page, c.paragraph, c.section, c.text, c.content_hash, 0.0,
                        list(c.security_flags or [])) for c, d in rows]


def all_chunks(db: Session, *, organization_id: str, case_id: str, limit: int = 400) -> list[EvidenceHit]:
    idx = _load(db, organization_id, case_id)
    return [EvidenceHit(c.id, d.id, d.filename, d.doc_type, c.page, c.paragraph, c.section, c.text, c.content_hash, 0.0,
                        list(c.security_flags or [])) for c, d in idx.rows[:limit]]
