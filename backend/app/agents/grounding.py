"""
Grounding helpers shared by agents. The central rule: a quote is accepted only if it appears verbatim (after
whitespace/case/quote normalisation) in the chunk it cites. Everything else is discarded or marked unsupported.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..ingestion.profile import DATE_RE, parse_dates
from ..ingestion.text import norm_for_match
from ..retrieval.case_index import EvidenceHit, tokens

DOC_LABEL = {
    "fir": "the FIR", "remand_report": "the remand report", "arrest_memo": "the arrest memo", "charge_sheet": "the charge sheet",
    "witness_statement": "the witness statement", "seizure_memo": "the seizure memo", "medical_report": "the medical report",
    "bail_order": "the bail order", "judgment": "the judgment", "contract": "the contract", "legal_notice": "the legal notice",
    "affidavit": "the affidavit", "complaint": "the complaint", "invoice": "the invoice", "correspondence": "the correspondence",
}
# Event vocabulary → event type. Ordered: more specific first.
EVENT_TERMS: list[tuple[str, str]] = [
    (r"\b(arrest(?:ed)?|apprehended|taken into custody|detained)\b", "arrest"),
    (r"\b(fir|first information report)\b.{0,30}\b(registered|lodged|recorded|filed)\b|\b(registered|lodged)\b.{0,20}\b(fir|case)\b", "fir_registered"),
    (r"\b(remand(?:ed)?|produced before)\b", "remand"),
    (r"\b(seized|seizure|recovered|recovery)\b", "seizure"),
    (r"\b(medical(?:ly)? examin\w*|mlc)\b", "medical_examination"),
    (r"\b(bail|released)\b", "bail"),
    (r"\b(charge[- ]?sheet)\b", "charge_sheet"),
    (r"\b(incident|occurred|took place|robbed|stolen|assaulted|attacked)\b", "incident"),
    (r"\b(hearing|listed|adjourned)\b", "hearing"),
    (r"\b(terminat\w+)\b", "termination"),
    (r"\b(signed|executed|entered into)\b", "signing"),
    (r"\b(paid|payment|remitted|transferred)\b", "payment"),
    (r"\b(deliver\w*|dispatched|shipped)\b", "delivery"),
    (r"\b(notice)\b", "notice"),
    (r"\b(statement recorded|recorded the statement|deposed)\b", "statement"),
]
# Events that happen once; different dates for them across documents are a conflict.
SINGLE_OCCURRENCE = {"arrest", "fir_registered", "incident", "seizure", "signing", "termination", "medical_examination", "charge_sheet"}
EVENT_LABEL = {"arrest": "Date of arrest", "fir_registered": "Date of FIR registration", "incident": "Date of incident",
               "seizure": "Date of seizure", "signing": "Date of signing", "termination": "Date of termination",
               "medical_examination": "Date of medical examination", "charge_sheet": "Date of charge sheet"}
_SENT = re.compile(r"(?<=[.!?])\s+(?=[\"'(]?[A-Z0-9])")


def doc_label(hit: EvidenceHit) -> str:
    return DOC_LABEL.get(hit.doc_type, f"“{hit.document_name}”")


def verbatim(quote: str, text: str) -> bool:
    q = norm_for_match(quote).strip(" .\"'")
    return len(q) >= 8 and q in norm_for_match(text)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if len(s.strip()) > 3]


def best_sentence(text: str, query: str) -> str:
    q = set(tokens(query))
    sents = sentences(text) or [text]
    return max(sents, key=lambda s: (len(q & set(tokens(s))), -abs(len(s) - 160)))


@dataclass(frozen=True)
class DatedEvent:
    date_text: str
    date_iso: str | None
    event_type: str
    sentence: str


def events_in(text: str) -> list[DatedEvent]:
    """Dated events: each date is attributed to the nearest event term before it (or right after it) in its sentence."""
    out: list[DatedEvent] = []
    for sent in sentences(text):
        dates = list(DATE_RE.finditer(sent))
        if not dates:
            continue
        parsed = parse_dates(sent)
        prev_end = 0
        for i, m in enumerate(dates):
            window = sent[prev_end:m.start()].lower()
            after = sent[m.end():m.end() + 40].lower()
            best: tuple[int, str] | None = None
            for pat, kind in EVENT_TERMS:
                for em in re.finditer(pat, window, re.I):
                    dist = len(window) - em.end()
                    if best is None or dist < best[0]:
                        best = (dist, kind)
            if best is None:
                for pat, kind in EVENT_TERMS:
                    if re.search(pat, after, re.I):
                        best = (0, kind)
                        break
            if best is not None:
                out.append(DatedEvent(parsed[i][0], parsed[i][1], best[1], sent))
            prev_end = m.end()
    return out
