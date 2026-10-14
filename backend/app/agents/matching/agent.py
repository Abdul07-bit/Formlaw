"""
Case Matching Agent — matches a client's intake with KYC-verified lawyers and explains why.

Uses only verified or platform-recorded data: admin-verified practice areas, jurisdictions, languages, availability,
and the number of FormLaw matters of the same type the lawyer has led (platform record, no case content). Self-declared
experience is labelled as such. Never uses ratings, win rates or personal characteristics; never predicts outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..base import AgentSpec

SPEC = AgentSpec(
    name="Case Matching Agent",
    purpose="Match a client's matter with verified lawyers and explain each match",
    actions=(), tools=frozenset({"search_verified_lawyers"}),
    inputs="structured intake (domain, jurisdiction, city, language, complexity, urgency)",
    outputs="ranked verified lawyers with reasons and considerations",
    failure_modes="no verified specialist → says so; never substitutes unverified profiles",
    verification="only VERIFIED, published profiles are candidates; reasons come from verified fields",
)
DISCLAIMER = ("Matches are based on verified practice areas, location and availability. FormLaw does not rate lawyers "
              "and does not predict or guarantee case outcomes.")


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    city: str
    state: str
    jurisdictions: tuple[str, ...]
    verified_areas: frozenset[str]
    languages: tuple[str, ...]
    experience_years: int
    accepting: bool
    platform_matters: int  # FormLaw matters of this type the lawyer led


@dataclass
class Match:
    lawyer_id: str
    rank: int = 0
    reasons: list[str] = field(default_factory=list)
    considerations: list[str] = field(default_factory=list)
    _score: float = 0.0


def match(domain: str, city: str, jurisdiction: str, language: str, complexity: str, candidates: list[Candidate], limit: int = 5) -> list[Match]:
    pool = [c for c in candidates if c.accepting]
    specialists = [c for c in pool if domain in c.verified_areas]
    if specialists:
        pool = specialists  # verified practice-area fit is required whenever any verified specialist exists
    out = []
    for c in pool:
        m = Match(c.id)
        if domain in c.verified_areas:
            m._score += 50
            m.reasons.append(f"Verified {domain} practice")
        place = (jurisdiction or city).lower()
        if place and (c.city.lower() == place or c.state.lower() == place or any(place in j.lower() for j in c.jurisdictions)):
            m._score += 20
            m.reasons.append(f"Practises in {jurisdiction or city}")
        elif city and c.city.lower() == city.lower():
            m._score += 15
            m.reasons.append(f"Based in {c.city}")
        if language and any(language.lower() == l.lower() for l in c.languages):
            m._score += 8
            m.reasons.append(f"Speaks {language}")
        if c.platform_matters:
            m._score += min(12, 3 * c.platform_matters)
            m.reasons.append(f"Has led {c.platform_matters} {domain} matter(s) on FormLaw")
        if complexity == "high" and c.experience_years >= 10:
            m._score += 6
            m.reasons.append(f"{c.experience_years} years of practice (self-declared) for a complex matter")
        elif c.experience_years:
            m.considerations.append(f"{c.experience_years} years of practice is self-declared")
        if domain not in c.verified_areas:
            m.considerations.append(f"No verified {domain} practice area — shown because no verified specialist is available")
        out.append(m)
    out.sort(key=lambda m: m._score, reverse=True)
    for i, m in enumerate(out[:limit], start=1):
        m.rank = i
    return out[:limit]
