"""
Client Intake Agent — turns a client's own description into a structured, lawyer-readable intake.
It uses only what the client wrote; unknown fields stay empty. It never assesses merits or predicts outcomes.
"""
from __future__ import annotations

import re
from typing import Any

from ...ingestion.profile import REFERENCEABLE, parse_dates
from ...llm import prompts
from ...llm.providers import LLMError, LLMOutputError, get_router
from ...llm.schemas import IntakeOut
from ...security.injection import scan
from ..base import AgentSpec

SPEC = AgentSpec(
    name="Client Intake Agent",
    purpose="Convert a client's description into a structured intake summary for a lawyer",
    actions=(), tools=frozenset({"llm_structured"}),
    inputs="client description + guided answers (untrusted)",
    outputs="problem, domain, parties, timeline, documents, jurisdiction, urgency, complexity, missing information, questions",
    failure_modes="model unavailable → rule-based structuring with explicit empty fields",
    verification="timeline dates must appear in the client's text; instruction-like text is flagged, not followed",
)
DOMAIN_TERMS = {
    "criminal": ["fir", "arrest", "bail", "police", "accused", "theft", "assault", "custody", "cheating", "chargesheet"],
    "family": ["divorce", "maintenance", "custody of", "marriage", "husband", "wife", "dowry", "domestic violence", "alimony"],
    "property": ["property", "land", "tenant", "landlord", "rent", "possession", "sale deed", "encroach", "flat", "builder"],
    "contract": ["contract", "agreement", "breach", "vendor", "supplier", "invoice", "payment not", "deliver"],
    "employment": ["salary", "terminated", "employer", "fired", "wages", "gratuity", "notice period", "resign", "posh"],
    "consumer": ["refund", "defective", "warranty", "consumer", "product", "seller", "service centre"],
    "cyber": ["upi", "otp", "phishing", "hacked", "online fraud", "social media", "scam"],
    "corporate": ["shareholder", "company", "director", "startup", "investor"],
    "constitutional": ["fundamental right", "writ", "article 21", "article 14"],
}
URGENT = re.compile(r"\b(arrest(ed)?|in custody|detained|bail|hearing (is )?(tomorrow|today|on monday)|eviction|threat|violence|deadline (is )?(tomorrow|today))\b", re.I)
QUESTIONS = {
    "criminal": ["Has an FIR been registered? Do you have a copy?", "Has anyone been arrested? On what date?", "Is there a court date scheduled?"],
    "property": ["Which documents show ownership or tenancy?", "Is any case already pending about this property?"],
    "contract": ["Do you have the signed agreement and all annexures?", "What notices or emails have been exchanged?"],
    "employment": ["Do you have your appointment letter and termination letter?", "What dues are unpaid, and since when?"],
    "family": ["When and where was the marriage registered?", "Are there children, and with whom do they live?"],
}


def _domain(text: str) -> str:
    low = text.lower()
    scores = {d: sum(low.count(t) for t in terms) for d, terms in DOMAIN_TERMS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "other"


def structure(description: str, answers: dict[str, str]) -> tuple[dict[str, Any], str, list[str]]:
    """Returns (structured intake, engine, security flags)."""
    text = (description + "\n" + "\n".join(f"{k}: {v}" for k, v in answers.items())).strip()
    flags = sorted(scan(text).kinds)
    router = get_router()
    if router is not None:
        try:
            system, _ = prompts.system_prompt("intake")
            obj, _tokens, model = router.generate("intake", system_prompt=system, schema=IntakeOut,
                                                  user_prompt=prompts.user_message(request="Structure this client intake.",
                                                                                   passages=[prompts.PromptPassage("P1", "client description", text)]))
            data = obj.model_dump()
            data["timeline"] = [e for e in data["timeline"] if e["date_text"].lower() in text.lower()]  # no invented dates
            return data, model, flags
        except (LLMError, LLMOutputError):
            pass
    domain = _domain(text)
    timeline = []
    for raw, _iso in parse_dates(text)[:12]:
        sent = next((s for s in re.split(r"(?<=[.!?\n])\s+", text) if raw in s), raw)
        timeline.append({"date_text": raw, "event": sent.strip()[:300]})
    docs = [label for _k, (label, pats) in REFERENCEABLE.items() if any(re.search(p, text, re.I) for p in pats)]
    docs += [w for w in ("agreement", "receipt", "notice", "email", "letter", "photos", "bank statement") if w in text.lower() and w not in docs]
    jur = next((m.group(1) for m in re.finditer(r"\b(?:in|at)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b", description)), "")
    return {
        "problem": " ".join(re.split(r"(?<=[.!?])\s+", description.strip())[:3])[:800],
        "legal_domain": domain, "parties": [], "timeline": timeline, "documents_mentioned": docs[:20], "jurisdiction": jur,
        "urgency": "urgent" if URGENT.search(text) else "normal",
        "complexity": "high" if len(text) > 2500 or len(timeline) > 8 else "medium" if len(text) > 600 else "low",
        "known_evidence": docs[:10], "missing_information": [] if docs else ["Copies of any documents related to the matter"],
        "questions_for_client": QUESTIONS.get(domain, ["Which documents do you have about this matter?", "What outcome are you seeking?"]),
    }, "deterministic", flags
