"""
Lawyer Matching Agent.

Ranks only KYC-verified, published profiles using trusted fields: verified practice-area expertise,
jurisdiction/city, related verified case metadata, availability and the client's budget preference.
It never uses ratings, self-reported win rates or personal characteristics, never predicts outcomes,
and records the reasons for every recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TYPICAL_HEARINGS: dict[str, tuple[int, int]] = {
    "Criminal": (2, 6), "Family": (4, 10), "Property": (6, 14), "Corporate": (3, 8),
    "Consumer": (2, 5), "Cyber": (2, 5), "Labour": (3, 8), "Constitutional": (2, 5),
}
DISCLAIMER = "Indicative fee range only. FormLaw does not predict or guarantee case outcomes."


@dataclass(frozen=True)
class Candidate:
    id: str
    city: str
    state: str
    verified_areas: frozenset[str]
    consultation_fee: int
    hearing_fee: int
    response_hours: int
    experience_years: int


@dataclass
class Match:
    lawyer_id: str
    score: int
    reasons: list[str] = field(default_factory=list)
    estimate: tuple[int, int] = (0, 0)


def match_lawyers(area: str, city: str, budget: int, candidates: list[Candidate], related_authors: set[str], limit: int = 4) -> list[Match]:
    out: list[Match] = []
    lo, hi = TYPICAL_HEARINGS.get(area, (2, 6))
    for c in candidates:
        reasons: list[str] = []
        score = 20.0
        if area in c.verified_areas:
            score += 40
            reasons.append(f"Verified {area} practice")
        if city and c.city.lower() == city.lower():
            score += 15
            reasons.append(f"Based in {c.city}")
        if c.id in related_authors:
            score += 12
            reasons.append("Handled a closely related, verified case")
        if c.experience_years >= 10:
            score += 5
            reasons.append(f"{c.experience_years} years of practice")
        estimate = (c.consultation_fee + c.hearing_fee * lo, c.consultation_fee + c.hearing_fee * hi)
        if budget and estimate[0] <= budget:
            score += 8
            reasons.append("Indicative fee fits your budget")
        elif budget and estimate[0] > budget * 1.5:
            score -= 10
        if c.response_hours <= 6:
            score += 3
            reasons.append(f"Usually replies within {c.response_hours}h")
        out.append(Match(c.id, max(5, min(97, round(score))), reasons, estimate))
    # Area fit is a hard requirement when any verified specialist exists.
    if any(area in c.verified_areas for c in candidates):
        ids = {c.id for c in candidates if area in c.verified_areas}
        out = [m for m in out if m.lawyer_id in ids]
    return sorted(out, key=lambda m: m.score, reverse=True)[:limit]
