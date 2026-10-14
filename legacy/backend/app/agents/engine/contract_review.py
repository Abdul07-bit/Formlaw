"""
Contract Review Agent: clauses, obligations, risks, unusual provisions and missing standard clauses.
Every finding quotes the clause text it came from; absent clauses are reported as gaps, not guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .chunking import Chunk

STANDARD_CLAUSES: dict[str, re.Pattern[str]] = {
    "Termination": re.compile(r"\bterminat", re.I),
    "Governing law": re.compile(r"governing law|governed by the laws", re.I),
    "Dispute resolution / arbitration": re.compile(r"arbitrat|dispute resolution|jurisdiction of the courts", re.I),
    "Confidentiality": re.compile(r"confidential", re.I),
    "Limitation of liability": re.compile(r"limitation of liability|liability shall not exceed|aggregate liability", re.I),
    "Indemnity": re.compile(r"indemnif", re.I),
    "Force majeure": re.compile(r"force majeure", re.I),
    "Payment terms": re.compile(r"\bpayment\b|\binvoice\b|\bfees?\b", re.I),
    "Notice": re.compile(r"\bnotices?\b.{0,40}(in writing|address)", re.I),
}

RISK_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("Unlimited liability", re.compile(r"unlimited liability|without (any )?limit", re.I), "high"),
    ("One-sided termination", re.compile(r"(may|can) terminate .{0,60}(at any time|without (cause|notice|reason))", re.I), "high"),
    ("Automatic renewal", re.compile(r"automatically renew|auto-?renew", re.I), "medium"),
    ("Non-compete", re.compile(r"non-?compete|shall not .{0,40}compet", re.I), "medium"),
    ("Penalty / liquidated damages", re.compile(r"liquidated damages|penalty of", re.I), "medium"),
    ("Unilateral amendment", re.compile(r"(may|reserves the right to) (amend|modify|change) .{0,40}(at any time|without notice)", re.I), "high"),
    ("Waiver of rights", re.compile(r"waives? (all|any) (rights?|claims?)", re.I), "high"),
]
OBLIGATION = re.compile(r"\b(shall|must|agrees to|is required to|undertakes to)\b", re.I)


@dataclass
class ContractFinding:
    kind: str  # obligation | risk | unusual
    title: str
    text: str
    doc_name: str
    page: int
    severity: str = "low"


@dataclass
class ContractReview:
    clauses_found: list[str] = field(default_factory=list)
    missing_clauses: list[str] = field(default_factory=list)
    findings: list[ContractFinding] = field(default_factory=list)


def looks_like_contract(chunks: list[Chunk]) -> bool:
    text = " ".join(c.sentence for c in chunks[:200]).lower()
    return sum(w in text for w in ("agreement", "party", "parties", "hereinafter", "clause", "whereas", "term")) >= 3


def review_contract(chunks: list[Chunk]) -> ContractReview:
    out = ContractReview()
    full = "\n".join(c.sentence for c in chunks)
    for name, rx in STANDARD_CLAUSES.items():
        (out.clauses_found if rx.search(full) else out.missing_clauses).append(name)
    for c in chunks:
        for title, rx, sev in RISK_PATTERNS:
            if rx.search(c.sentence):
                out.findings.append(ContractFinding("risk", title, c.sentence, c.doc_name, c.page, sev))
        if OBLIGATION.search(c.sentence) and len([f for f in out.findings if f.kind == "obligation"]) < 25:
            out.findings.append(ContractFinding("obligation", "Obligation", c.sentence, c.doc_name, c.page))
    return out
