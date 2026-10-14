"""
Hybrid retrieval:  keyword (BM25)  +  semantic (embeddings, when a provider is configured)
                   +  metadata filters  →  reciprocal-rank fusion  →  evidence set.

Every hit is returned with its provenance (document, page, section, source, content hash) so callers
can cite it. Semantic search is optional: without an embedding provider, retrieval is keyword-only.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("the and was for that with this from his her are not has have been after about which what when were who into of to in on a an is it by as at be or".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True)
class Passage:
    id: str
    text: str
    document_id: str
    document_name: str
    page: int | None = None
    section: str | None = None
    source: str = "case_document"  # case_document | statute | judgment | constitution
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)  # jurisdiction, court, date, domain, article, citation ...

    def as_evidence(self) -> dict[str, Any]:
        return {
            "evidence_id": self.id, "document_id": self.document_id, "document_name": self.document_name,
            "page": self.page, "section": self.section, "text": self.text, "source": self.source,
            "source_url": self.source_url, "content_hash": content_hash(self.text),
        }


class BM25:
    def __init__(self, passages: Sequence[Passage], k1: float = 1.4, b: float = 0.75):
        self.passages = list(passages)
        self.docs = [tokenize(p.text) for p in self.passages]
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / max(self.avgdl, 1)))
            out.append(s)
        return out


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def matches_filters(p: Passage, filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, want in filters.items():
        if want in (None, "", []):
            continue
        have = p.metadata.get(key, getattr(p, key, None))
        if key == "date_from":
            if not p.metadata.get("date") or str(p.metadata["date"]) < str(want):
                return False
        elif key == "date_to":
            if not p.metadata.get("date") or str(p.metadata["date"]) > str(want):
                return False
        elif isinstance(want, (list, tuple, set)):
            if have not in want:
                return False
        elif have is None or str(have).lower() != str(want).lower():
            return False
    return True


def search(passages: Sequence[Passage], query: str, *, k: int = 5, filters: dict[str, Any] | None = None,
           embed: Callable[[list[str]], list[list[float]]] | None = None,
           passage_vectors: dict[str, list[float]] | None = None, rrf_k: int = 60) -> list[tuple[Passage, float]]:
    pool = [p for p in passages if matches_filters(p, filters)]
    if not pool or not query.strip():
        return []
    kw = BM25(pool).scores(query)
    ranked_kw = [i for i in sorted(range(len(pool)), key=lambda i: kw[i], reverse=True) if kw[i] > 0]
    fused: dict[int, float] = {i: 1 / (rrf_k + r + 1) for r, i in enumerate(ranked_kw)}

    if embed and passage_vectors:
        qv = embed([query])[0]
        sem = [(i, _cosine(qv, passage_vectors[p.id])) for i, p in enumerate(pool) if p.id in passage_vectors]
        for r, (i, s) in enumerate(sorted(sem, key=lambda x: x[1], reverse=True)):
            if s > 0.2:
                fused[i] = fused.get(i, 0) + 1 / (rrf_k + r + 1)

    # Rerank: fused score with a small boost for exact phrase / key-term (section, article) matches.
    q_lower = query.lower()
    keyterms = re.findall(r"(?:section|article)\s+\d+[a-z]?", q_lower)
    def rerank(i: int) -> float:
        text = pool[i].text.lower()
        return fused[i] + 0.01 * sum(kt in text for kt in keyterms) + (0.005 if q_lower in text else 0)

    order = sorted(fused, key=rerank, reverse=True)[:k]
    return [(pool[i], round(rerank(i), 5)) for i in order]
