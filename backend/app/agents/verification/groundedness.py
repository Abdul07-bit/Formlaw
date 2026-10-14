"""
Verification Agent core: decides whether a claim is backed by the evidence it cites.

    SUPPORTED            every key fact (dates, numbers, sections) and most content words appear in the evidence
    PARTIALLY_SUPPORTED  the evidence covers part of the claim
    CONTRADICTED         the evidence discusses the same thing but states a different date/number/section
    UNSUPPORTED          evidence was supplied but does not back the claim
    UNVERIFIED           nothing to check against, or a cited authority is not in the trusted corpus

Deterministic on purpose: the model that wrote a claim never grades its own claim.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_DATE = re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}\b|\b\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}\b", re.I)
_SECTION = re.compile(r"\b(?:section|s\.|article|art\.)\s*\d+[a-z]?(?:\(\d+\))?", re.I)
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
_STOP = set("the and was for that with this from his her are not has have been after about which what when were who into than then also their there they them its any all can may shall will would could should under upon such other".split())

STATUSES = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNVERIFIED")


@dataclass(frozen=True)
class Verdict:
    status: str
    confidence: float
    reason: str
    best_evidence: int | None = None  # index into the evidence list


def _norm_date(s: str) -> str:
    return re.sub(r"(st|nd|rd|th)\b", "", s.lower()).replace("  ", " ").strip()


def _keys(text: str) -> tuple[set[str], set[str], set[str]]:
    dates = {_norm_date(d) for d in _DATE.findall(text)}
    sections = {re.sub(r"\s+", "", s.lower()).replace("s.", "section").replace("art.", "article") for s in _SECTION.findall(text)}
    no_dates = _DATE.sub(" ", _SECTION.sub(" ", text))
    numbers = {n.replace(",", "") for n in _NUMBER.findall(no_dates)}
    return dates, sections, numbers


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def verify_claim(claim: str, evidence: list[str], *, citations: Iterable[str] = (),
                 citation_exists: Callable[[str], bool] | None = None) -> Verdict:
    # Cited authorities must exist in the trusted corpus — fabricated or wrong citations fail here.
    for cite in citations:
        if citation_exists is None or not citation_exists(cite):
            return Verdict("UNVERIFIED", 0.0, f"Citation not found in the trusted corpus: {cite}")
    if not evidence:
        return Verdict("UNVERIFIED", 0.0, "No evidence supplied for this claim")

    c_dates, c_secs, c_nums = _keys(claim)
    c_words = _words(claim)
    best: tuple[float, int, bool] | None = None
    for i, ev in enumerate(evidence):
        e_dates, e_secs, e_nums = _keys(ev)
        e_words = _words(ev)
        overlap = len(c_words & e_words) / max(len(c_words), 1)
        # Same topic, different key value → contradiction.
        if overlap >= 0.35 and (
            (c_dates and e_dates and not (c_dates & e_dates))
            or (c_secs and e_secs and not (c_secs & e_secs))
        ):
            return Verdict("CONTRADICTED", 0.9, "Evidence on the same point states a different date or provision", i)
        keys_ok = c_dates <= e_dates and c_secs <= e_secs and c_nums <= (e_nums | {d for d in c_nums if len(d) <= 1})
        if best is None or (keys_ok, overlap) > (best[2], best[0]):
            best = (overlap, i, keys_ok)

    assert best is not None
    overlap, idx, keys_ok = best
    if keys_ok and overlap >= 0.6:
        return Verdict("SUPPORTED", round(min(1.0, 0.5 + overlap / 2), 2), "Key facts and wording found in evidence", idx)
    if not keys_ok:
        # A date, amount, section or other figure in the claim appears in no cited passage: never partially true.
        return Verdict("UNSUPPORTED", round(overlap, 2), "A key fact (date, number or provision) is not in the evidence", idx)
    if overlap >= 0.3 or (c_dates or c_secs):
        return Verdict("PARTIALLY_SUPPORTED", round(0.3 + overlap / 2, 2), "Evidence covers only part of the claim", idx)
    return Verdict("UNSUPPORTED", round(overlap, 2), "Evidence does not back this claim", idx)
