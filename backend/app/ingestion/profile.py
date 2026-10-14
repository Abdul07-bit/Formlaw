"""
Document profiling: a heuristic document type, dates found, and other documents the text refers to.
Heuristics only label; they never create facts. Referenced documents feed the Missing Information agent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DOC_TYPES: list[tuple[str, list[str]]] = [
    ("fir", [r"\bfirst information report\b", r"\bF\.?I\.?R\.?\b", r"\bfir\b"]),
    ("remand_report", [r"\bremand (report|application)\b", r"\bremand\b"]),
    ("arrest_memo", [r"\barrest memo\b", r"\bmemo of arrest\b", r"\barrest-cum-inspection memo\b"]),
    ("charge_sheet", [r"\bcharge[- ]?sheet\b", r"\bfinal report\b"]),
    ("witness_statement", [r"\bstatement of (the )?witness\b", r"\bwitness statement\b", r"\bsection 161\b", r"\bsection 180 bnss\b"]),
    ("seizure_memo", [r"\bseizure memo\b", r"\brecovery memo\b", r"\bpanchnama\b"]),
    ("medical_report", [r"\bmedical (report|examination|certificate)\b", r"\bpost[- ]mortem\b", r"\bmlc\b"]),
    ("bail_order", [r"\bbail\b.{0,40}\border\b", r"\border\b.{0,40}\bbail\b"]),
    ("judgment", [r"\bjudgment\b", r"\bhon'?ble (court|justice)\b"]),
    ("contract", [r"\bagreement\b", r"\bthis contract\b", r"\bwhereas\b", r"\bparties (hereto|agree)\b", r"\bclause \d+"]),
    ("legal_notice", [r"\blegal notice\b", r"\bnotice under section\b", r"\bunder instructions from (my|our) client\b"]),
    ("affidavit", [r"\baffidavit\b", r"\bsolemnly affirm\b", r"\bdeponent\b"]),
    ("complaint", [r"\bcomplaint\b", r"\bcomplainant\b"]),
    ("invoice", [r"\binvoice\b", r"\bgstin\b", r"\bamount due\b"]),
    ("correspondence", [r"^\s*(from|to|subject|dear)\s*[:,]", r"\bregards\b"]),
]

# Documents a matter commonly refers to. Key → (label, patterns)
REFERENCEABLE: dict[str, tuple[str, list[str]]] = {
    "arrest_memo": ("Arrest memo", [r"\barrest memo\b", r"\bmemo of arrest\b"]),
    "seizure_memo": ("Seizure / recovery memo", [r"\bseizure memo\b", r"\brecovery memo\b", r"\bpanchnama\b"]),
    "medical_report": ("Medical examination report", [r"\bmedical (report|examination)\b", r"\bmlc\b"]),
    "witness_statement": ("Witness statement(s)", [r"\bstatements? of (the )?witness(es)?\b", r"\bwitness statements?\b"]),
    "cctv_footage": ("CCTV footage", [r"\bcctv\b"]),
    "call_records": ("Call detail records", [r"\bcall detail records?\b", r"\bcdrs?\b"]),
    "charge_sheet": ("Charge sheet", [r"\bcharge[- ]?sheet\b"]),
    "remand_report": ("Remand report", [r"\bremand report\b"]),
    "fir": ("FIR", [r"\bF\.?I\.?R\.?\b"]),
    "forensic_report": ("Forensic (FSL) report", [r"\bfsl\b", r"\bforensic (science )?(report|laboratory)\b"]),
    "bail_order": ("Bail order", [r"\bbail order\b"]),
    "annexure": ("Annexure / schedule", [r"\bannexure[- ]?[A-Z0-9]+\b", r"\bschedule [A-Z0-9]+\b"]),
    "notice": ("Notice", [r"\b(termination|legal|demand) notice\b"]),
    "invoice": ("Invoice", [r"\binvoices?\b"]),
    "power_of_attorney": ("Power of attorney", [r"\bpower of attorney\b"]),
}

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
DATE_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({MONTHS})\.?,?\s+(\d{{4}})\b|\b({MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b|\b(\d{{1,2}})[./-](\d{{1,2}})[./-](\d{{4}})\b", re.I)
_MONTH_NUM = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}


@dataclass
class Profile:
    doc_type: str = "document"
    dates: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)  # REFERENCEABLE keys mentioned in the text
    template_fields: list[str] = field(default_factory=list)  # doc_type "template": the fields left unfilled


def month_num(m: str) -> int:
    m = m.lower().rstrip(".")
    for name, n in _MONTH_NUM.items():
        if name.startswith(m[:3]):
            return n
    return 0


def parse_dates(text: str) -> list[tuple[str, str | None]]:
    """[(date as written, ISO date or None)]. Numeric dates are read day-first (Indian convention)."""
    out = []
    for m in DATE_RE.finditer(text):
        raw = m.group(0)
        if m.group(1):
            d, mo, y = int(m.group(1)), month_num(m.group(2)), int(m.group(3))
        elif m.group(4):
            d, mo, y = int(m.group(5)), month_num(m.group(4)), int(m.group(6))
        else:
            d, mo, y = int(m.group(7)), int(m.group(8)), int(m.group(9))
        iso = f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 and 1900 < y < 2100 else None
        out.append((raw, iso))
    return out


# ------------------------------------------------------------------ blank forms and templates
# A bracketed placeholder: "[Full Name]", "[DD/MM/YYYY]", "[Argument 1, supporting evidence, and legal basis.]".
# Not: citations "[2019]", footnotes "[1]", editorial marks "[sic]", "[emphasis supplied]", "[REDACTED]".
_BRACKET = re.compile(r"\[([^\[\]\n]{2,90})\]")
_EDITORIAL = re.compile(r"^(sic|emphasis\b.*|supplied|added|redacted|illegible|translated|translation|page \d+|p\. ?\d+|\d+|\d{4}|\.{2,}|…"
                        r"|.*,\s*(J|JJ|CJ|CJI)\.?:?|per .*)$", re.I)  # also judges' names in judgment headers: "[DIPAK MISRA, J.]"
_BLANK = re.compile(r"\bDD\s*/\s*MM\s*/\s*YY(?:YY)?\b|_{4,}|\.{6,}", re.I)
# A form instruction in place of content: "Background: Describe the events leading to the dispute."
_INSTRUCTION = re.compile(r"(?:^|:\s*)(Describe|State|Summari[sz]e|Insert|Enter|Provide|List|Explain|Specify|Mention)\s+(the|what|any|all|each|your|key|a|an)\b"
                          r"|\breplace (all )?(the )?bracketed\b|\bthis (form|template) is\b|\bfill (in|out) (the|this)\b", re.I | re.M)
_LABEL = re.compile(r"([A-Z][A-Za-z /&'()-]{1,40}?)\s*:\s*$")
_WORD = re.compile(r"[A-Za-z]{3,}")


def placeholders(text: str) -> list[str]:
    """Unfilled template placeholders in the text (bracketed fields and DD/MM/YYYY-style blanks)."""
    out = [m.group(1).strip() for m in _BRACKET.finditer(text) if not _EDITORIAL.match(m.group(1).strip()) and re.search(r"[A-Za-z]", m.group(1))]
    return out + [m.group(0) for m in _BLANK.finditer(text) if not _BRACKET.search(text[max(0, m.start() - 1):m.end() + 1])]


def is_placeholder_only(text: str) -> bool:
    """True when a passage carries no case-specific content once placeholders, field labels and instructions are removed."""
    if not placeholders(text) and not _INSTRUCTION.search(text):
        return False
    rest = _BLANK.sub(" ", _BRACKET.sub(" ", text))
    rest = re.sub(r"[A-Z][A-Za-z /&'()-]{1,40}?:", " ", rest)                     # field labels
    rest = re.sub(r"\b\w+(?:\s*/\s*\w+){2,}\b", " ", rest)                         # option lists: High / Medium / Low
    rest = re.sub(r"(?:Describe|State|Summari[sz]e|Insert|Enter|Provide|List|Explain|Specify|Mention)\b[^.]*\.?", " ", rest)
    content = [w for w in _WORD.findall(rest) if w.lower() not in {"and", "the", "vs", "for", "with", "from"}]
    return len(content) <= 4


def _label_before(prefix: str) -> str | None:
    prefix = re.sub(r"\b\w+(?:\s*/\s*\w+){2,}\b", " ", prefix.rsplit("]", 1)[-1])  # option lists are not labels
    m = _LABEL.search(prefix)
    return m.group(1).strip() if m else None


def template_fields(text: str) -> list[str]:
    """The fields a blank form leaves unfilled, by label where there is one: "Plaintiff / Complainant", "Filing Date"."""
    fields: list[str] = []
    for line in text.splitlines():
        for m in _BRACKET.finditer(line):
            inner = m.group(1).strip()
            if _EDITORIAL.match(inner) or not re.search(r"[A-Za-z]", inner):
                continue
            lab = _label_before(line[:m.start()])
            if lab or len(inner.split()) <= 6:  # an unlabelled long bracketed note is guidance, not a field
                fields.append(lab or ("Date" if _BLANK.fullmatch(inner) else inner.rstrip(".")))
        for m in _BLANK.finditer(line):
            if lab := _label_before(line[:m.start()]):
                fields.append(lab)
        im = re.match(r"\s*([A-Z][A-Za-z /&'()-]{1,40}?)\s*:\s*(Describe|State|Summari[sz]e|Insert|Enter|Provide|List|Explain|Specify|Mention)\b", line)
        if im:
            fields.append(im.group(1).strip())
    seen: set[str] = set()
    return [f for f in fields if not (f.lower() in seen or seen.add(f.lower()))][:40]


def is_template(text: str) -> bool:
    """A blank form: placeholders or form instructions make up most of its substantive lines."""
    lines = [ln for ln in (x.strip() for x in text.splitlines()) if len(_WORD.findall(ln)) >= 1 and not ln.startswith("[[PAGE")]
    if not lines:
        return False
    marked = sum(1 for ln in lines if placeholders(ln) or _INSTRUCTION.search(ln))
    return len(placeholders(text)) >= 3 and marked / len(lines) >= 0.4


def profile(filename: str, text: str) -> Profile:
    if is_template(text):
        return Profile("template", [], [], template_fields(text))  # a blank form's mentions are not references
    name = filename.lower().replace("_", " ").replace("-", " ")
    head = text[:4000]
    best, best_score = "document", 0
    for kind, pats in DOC_TYPES:
        score = sum(3 for p in pats if re.search(p, name, re.I)) + sum(1 for p in pats if re.search(p, head, re.I | re.M))
        if score > best_score:
            best, best_score = kind, score
    refs = [k for k, (_label, pats) in REFERENCEABLE.items() if any(re.search(p, text, re.I) for p in pats)]
    return Profile(best if best_score >= 2 else "document", [d for d, _ in parse_dates(text)][:50], refs)
