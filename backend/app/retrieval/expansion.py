"""Legal query expansion: curated synonyms only (no model). Used when retrieval is weak or the query is short."""
from __future__ import annotations

import re

SYNONYMS: dict[str, list[str]] = {
    "arrest": ["arrested", "apprehended", "detained", "custody", "taken into custody", "arrest memo"],
    "arrested": ["arrest", "apprehended", "detained", "custody"],
    "fir": ["first information report", "complaint registered", "case registered"],
    "remand": ["judicial custody", "police custody", "produced before magistrate"],
    "seizure": ["seized", "recovered", "recovery", "panchnama"],
    "witness": ["statement", "eyewitness", "deposed"],
    "bail": ["released", "surety", "bond"],
    "date": ["on", "dated"],
    "terminate": ["termination", "terminated", "rescind", "cancel"],
    "termination": ["terminate", "terminated", "notice period", "rescission"],
    "payment": ["pay", "paid", "consideration", "fee", "invoice", "amount"],
    "penalty": ["liquidated damages", "penalty", "fine", "late fee"],
    "liability": ["liable", "indemnify", "indemnity", "damages"],
    "confidential": ["confidentiality", "non-disclosure", "nda"],
    "dispute": ["arbitration", "jurisdiction", "governing law", "courts"],
    "deadline": ["within", "days", "due date", "no later than"],
    "injury": ["injuries", "hurt", "wound", "medical"],
    "weapon": ["knife", "firearm", "rod", "weapon"],
    "theft": ["stolen", "stole", "robbery", "snatched"],
    "contradiction": ["inconsistent", "different", "conflict"],
    "evidence": ["exhibit", "document", "record", "statement"],
    "accused": ["defendant", "respondent"],
    "defendant": ["accused"],
}
# Make expansion symmetric: a word that appears as a synonym also expands back to its head term.
for _head, _syns in list(SYNONYMS.items()):
    for _s in _syns:
        if " " not in _s:
            SYNONYMS.setdefault(_s, [])
            if _head not in SYNONYMS[_s]:
                SYNONYMS[_s].append(_head)
_W = re.compile(r"[a-z0-9]+")


def expand(query: str, *, aggressive: bool = False) -> str:
    words = _W.findall(query.lower())
    extra: list[str] = []
    for w in words:
        for s in SYNONYMS.get(w, []) + (SYNONYMS.get(w.rstrip("s"), []) if aggressive else []):
            if s not in extra and s not in query.lower():
                extra.append(s)
    return query if not extra else f"{query} {' '.join(extra[: 12 if aggressive else 6])}"
