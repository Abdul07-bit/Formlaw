"""Precedent Agent: related outcomes from lawyers' verified, anonymised case history (not judicial precedent)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseMeta:
    id: str
    lawyer_id: str
    area: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class Related:
    case_id: str
    lawyer_id: str
    similarity: float
    shared_terms: tuple[str, ...]


def find_related(area: str, text: str, cases: list[CaseMeta], limit: int = 4) -> list[Related]:
    lower = text.lower()
    out = []
    for c in cases:
        if not c.keywords:
            continue
        shared = tuple(k for k in c.keywords if k.lower() in lower)
        sim = len(shared) / len(c.keywords) * 0.75 + (0.25 if c.area == area else 0)
        sim = round(min(sim, 0.97), 2)
        if sim >= 0.3:
            out.append(Related(c.id, c.lawyer_id, sim, shared[:5]))
    return sorted(out, key=lambda r: r.similarity, reverse=True)[:limit]
