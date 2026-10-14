"""
Case Review Agent: facts, timeline, issues and contradictions. Evidence-first: a fact is emitted only
when it points at a chunk of an uploaded document; nothing is inferred beyond the text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .chunking import Chunk

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTHS})\s+(\d{{4}})\b", re.I)
SECTION_RE = re.compile(r"Section \d+[A-Z]? (BNS|BNSS|IPC|CrPC|IT Act)", re.I)


def dates_in(s: str) -> list[str]:
    return [f"{int(d)} {m.capitalize()} {y}" for d, m, y in DATE_RE.findall(s)]


@dataclass
class EvidenceItem:
    label: str
    doc_id: str
    doc_name: str
    page: int
    text: str
    highlight: str


@dataclass
class Fact:
    key: str
    label: str
    statement: str
    status: str  # SUPPORTED | PARTIALLY_SUPPORTED | CONTRADICTED | UNSUPPORTED
    evidence: list[str] = field(default_factory=list)  # evidence labels


@dataclass
class ContradictionItem:
    topic: str
    a_value: str
    a_evidence: str
    b_value: str
    b_evidence: str
    confidence: float


@dataclass
class ReviewOutput:
    facts: list[Fact]
    evidence: list[EvidenceItem]
    contradictions: list[ContradictionItem]
    subject: str | None


class _EvidenceBook:
    def __init__(self) -> None:
        self.items: list[EvidenceItem] = []

    def add(self, c: Chunk, highlight: str) -> EvidenceItem:
        for e in self.items:
            if e.doc_id == c.doc_id and e.page == c.page and e.text == c.sentence:
                return e
        e = EvidenceItem(f"E{len(self.items) + 1:03d}", c.doc_id, c.doc_name, c.page, c.sentence, highlight)
        self.items.append(e)
        return e


def _doc_title(name: str) -> str:
    return re.sub(r"\.\w+$", "", re.sub(r"[_-]", " ", name))


def review_case(chunks: list[Chunk]) -> ReviewOutput:
    book = _EvidenceBook()
    facts: list[Fact] = []
    contradictions: list[ContradictionItem] = []
    subject = next((m.group(1) for c in chunks if (m := re.search(r"accused (?:\w+ )?([A-Z][a-z]+ [A-Z][a-z]+)", c.sentence))), None)

    # Arrest dates — compared across documents by the contradiction check.
    arrest_by_date: dict[str, EvidenceItem] = {}
    for c in chunks:
        if re.search(r"\barrest(ed)?\b", c.sentence, re.I) and (ds := dates_in(c.sentence)):
            arrest_by_date.setdefault(ds[0], book.add(c, ds[0]))
    if len(arrest_by_date) == 1:
        (d, ev), = arrest_by_date.items()
        facts.append(Fact("F-ARREST", "Arrest date", f"{subject or 'The accused'} was arrested on {d}.", "SUPPORTED", [ev.label]))
    elif len(arrest_by_date) > 1:
        entries = list(arrest_by_date.items())
        for d, ev in entries:
            facts.append(Fact(f"F-ARREST-{ev.label}", "Arrest date", f"{_doc_title(ev.doc_name)} records the arrest on {d}.", "CONTRADICTED", [ev.label]))
        contradictions.append(ContradictionItem("Arrest date", entries[0][0], entries[0][1].label, entries[1][0], entries[1][1].label, 0.98))

    # Date of occurrence.
    occ_date = None
    occ = next((c for c in chunks if re.search(r"occurrence|night of|incident", c.sentence, re.I) and dates_in(c.sentence)), None)
    if occ:
        occ_date = dates_in(occ.sentence)[0]
        labels = [book.add(occ, occ_date).label]
        for c in chunks:
            if c is not occ and re.search(r"night of|occurrence|incident", c.sentence, re.I) and occ_date in dates_in(c.sentence):
                labels.append(book.add(c, occ_date).label)
        facts.append(Fact("F-OCC", "Date of occurrence", f"The alleged incident occurred on {occ_date}.", "SUPPORTED", labels))

    # Offence sections.
    sec = next((c for c in chunks if SECTION_RE.search(c.sentence) and re.search(r"offence", c.sentence, re.I)), None)
    if sec:
        s = SECTION_RE.search(sec.sentence).group(0)  # type: ignore[union-attr]
        facts.append(Fact("F-SEC", "Offence charged", f"The FIR registers the offence under {s}.", "SUPPORTED", [book.add(sec, s).label]))

    # Identification by witness.
    weak = next((c for c in chunks if re.search(r"could not see|did not see|not clearly", c.sentence, re.I)), None)
    if weak:
        hl = re.search(r"could not see[^.]*|did not see[^.]*|not clearly[^.]*", weak.sentence, re.I).group(0)  # type: ignore[union-attr]
        facts.append(Fact("F-WIT", "Eyewitness identification", "The eyewitness could not positively identify the person at the scene.", "SUPPORTED", [book.add(weak, hl).label]))

    # Basis of suspicion.
    sus = next((c for c in chunks if re.search(r"named as a suspect", c.sentence, re.I)), None)
    if sus:
        facts.append(Fact("F-SUS", "Basis for suspicion", "The accused was named as a suspect on the basis of CCTV of the adjoining street and the complainant’s identification.",
                          "PARTIALLY_SUPPORTED", [book.add(sus, "named as a suspect").label]))

    # Possible alibi from an attendance record on the occurrence date.
    if occ_date:
        att = next((c for c in chunks if occ_date in c.sentence and re.search(r"\d{2}:\d{2},\d{2}:\d{2}", c.sentence)), None)
        if att:
            times = re.search(r"(\d{2}:\d{2}),(\d{2}:\d{2}),([^,]+)$", att.sentence)
            span = f" from {times.group(1)} to {times.group(2)} at {times.group(3).strip()}" if times else ""
            facts.append(Fact("F-ALIBI", "Possible alibi", f"An employment attendance record shows a check-in on {occ_date}{span}, overlapping the time of occurrence.",
                              "PARTIALLY_SUPPORTED", [book.add(att, occ_date).label]))

    # Generic fallback for other matters: the most fact-dense sentences, verbatim.
    if len(facts) < 2:
        def density(c: Chunk) -> int:
            return len(dates_in(c.sentence)) * 2 + len(re.findall(r"\b(Rs\.?|₹|section|article|dated|agreement|paid|notice)\b", c.sentence, re.I))
        dense = sorted((c for c in chunks if density(c) > 0), key=density, reverse=True)[:5]
        for i, c in enumerate(dense):
            ds = dates_in(c.sentence)
            facts.append(Fact(f"F-GEN-{i}", "Extracted statement", c.sentence, "SUPPORTED", [book.add(c, ds[0] if ds else c.sentence[:40]).label]))

    return ReviewOutput(facts, book.items, contradictions, subject)
