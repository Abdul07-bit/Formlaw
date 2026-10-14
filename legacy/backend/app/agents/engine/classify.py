"""Orchestrator step 1: classify the matter into a practice area from document text."""
from __future__ import annotations

from dataclasses import dataclass

AREA_TERMS: dict[str, list[str]] = {
    "Criminal": ["fir", "arrest", "bail", "accused", "police", "remand", "bns", "bnss", "ipc", "crpc", "theft", "custody", "chargesheet", "witness", "offence", "magistrate"],
    "Family": ["divorce", "maintenance", "custody of child", "marriage", "husband", "wife", "dowry", "domestic violence", "alimony", "guardian"],
    "Property": ["property", "land", "partition", "title", "sale deed", "tenant", "landlord", "mutation", "possession", "encroachment", "rent"],
    "Corporate": ["contract", "agreement", "invoice", "liability", "indemnity", "arbitration", "shareholder", "company", "breach", "vendor"],
    "Consumer": ["refund", "defective", "warranty", "consumer", "product", "service deficiency", "e-commerce", "seller"],
    "Cyber": ["upi", "otp", "phishing", "hacked", "cyber", "online fraud", "social media", "it act", "identity theft"],
    "Labour": ["salary", "termination", "employer", "wages", "gratuity", " pf ", "retrenchment", "posh", "notice period"],
    "Constitutional": ["article 21", "article 14", "writ", "fundamental right", "habeas corpus", "article 226", "article 32"],
}


@dataclass(frozen=True)
class Classification:
    area: str
    confidence: float
    scores: dict[str, int]


def classify(text: str) -> Classification:
    lower = text.lower()
    scores = {a: sum(lower.count(t) for t in terms) for a, terms in AREA_TERMS.items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(scores.values())
    if not total:
        return Classification("Criminal", 0.2, scores)
    return Classification(ranked[0][0], min(0.97, ranked[0][1] / total + 0.15), scores)
