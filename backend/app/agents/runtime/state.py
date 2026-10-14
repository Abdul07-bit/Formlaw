"""
Run state: the plan and the blackboard. The blackboard is the only channel between agents, and every item on it
carries citations (chunk id + verbatim quote) so it can be verified and traced back to a page of a document.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Literal

from ...domain.enums import ClaimStatus
from ...ingestion.profile import is_placeholder_only
from ...retrieval.case_index import EvidenceHit

StepState = Literal["pending", "running", "done", "failed", "skipped"]


@dataclass
class PlanStep:
    id: str
    agent: str
    action: str
    label: str
    params: dict[str, Any] = field(default_factory=dict)
    status: StepState = "pending"
    attempts: int = 0
    origin: Literal["plan", "adapt", "replan", "gate"] = "plan"
    reason: str = ""
    summary: str = ""

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "agent": self.agent, "action": self.action, "label": self.label, "status": self.status,
                "origin": self.origin, "reason": self.reason, "summary": self.summary}


@dataclass(frozen=True)
class Cite:
    chunk_id: str
    quote: str


@dataclass
class ClaimItem:
    id: str
    text: str
    kind: str                      # fact | allegation | admission | disputed | procedural | issue | answer | contract_* | summary
    agent: str
    citations: list[Cite] = field(default_factory=list)
    authority_ids: list[str] = field(default_factory=list)
    status: str = ClaimStatus.UNVERIFIED
    confidence: str = "low"
    reason: str = "Not yet verified"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status in (ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED)


@dataclass
class TimelineItem:
    id: str
    date_text: str
    date_iso: str | None
    description: str
    event_type: str
    cite: Cite
    status: str = "consistent"


@dataclass
class Side:
    cite: Cite
    value: str
    statement: str


@dataclass
class ContradictionItem:
    id: str
    topic: str
    nature: str
    a: Side
    b: Side
    explanation: str
    confidence: str = "medium"
    event_type: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False  # provenance step ran (it never "picks a winner")


@dataclass
class MissingItem:
    id: str
    title: str
    why: str
    basis: str                 # referenced_in_documents | checklist | conflict_resolution
    importance: str = "medium"
    cite: Cite | None = None
    key: str = ""


@dataclass
class AuthorityItem:
    id: str
    legal_document_id: str
    legal_chunk_id: str
    authority_type: str
    title: str
    citation: str | None
    court: str | None
    decision_date: str | None
    page: int | None
    quote: str
    source_name: str
    source_url: str | None
    license: str | None
    content_hash: str
    issue: str
    status: str = ClaimStatus.UNVERIFIED


@dataclass
class SecurityItem:
    kind: str
    source: str
    snippet: str
    chunk_id: str | None = None
    action: str = "excluded_from_ai_context"


@dataclass
class Answer:
    summary: str
    claim_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    strict: bool = False
    assessment: str | None = None  # forces the overall assessment (e.g. not_assessed for template-only material)


@dataclass
class DraftDoc:
    kind: str
    title: str
    facts: list[dict[str, Any]]
    authorities: list[dict[str, Any]]
    inferences: list[dict[str, Any]]
    recommendations: list[str]
    body: str


@dataclass
class Blackboard:
    evidence: dict[str, EvidenceHit] = field(default_factory=dict)
    # Passages from blank forms / unfilled placeholders. Kept apart so no agent ever treats them as case facts;
    # the composer uses them only to report that the analysis is incomplete and which fields are missing.
    templates: dict[str, EvidenceHit] = field(default_factory=dict)
    claims: list[ClaimItem] = field(default_factory=list)
    parties: list[dict[str, Any]] = field(default_factory=list)
    case_details: list[dict[str, Any]] = field(default_factory=list)  # {field, value, chunkId, quote}
    timeline: list[TimelineItem] = field(default_factory=list)
    contradictions: list[ContradictionItem] = field(default_factory=list)
    missing: list[MissingItem] = field(default_factory=list)
    authorities: list[AuthorityItem] = field(default_factory=list)
    contract_missing: list[dict[str, str]] = field(default_factory=list)
    security: list[SecurityItem] = field(default_factory=list)
    draft: DraftDoc | None = None
    answer: Answer | None = None
    queries: list[str] = field(default_factory=list)
    focus: list[str] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)
    _seq: Any = field(default_factory=lambda: itertools.count(1))

    def next_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._seq)}"

    def add_evidence(self, hits: list[EvidenceHit]) -> int:
        new = 0
        for h in hits:
            if not h.flagged and (h.doc_type == "template" or is_placeholder_only(h.text)):
                self.templates.setdefault(h.chunk_id, h)
                continue
            if h.chunk_id not in self.evidence:
                self.evidence[h.chunk_id] = h
                new += 1
            elif h.score > self.evidence[h.chunk_id].score:
                self.evidence[h.chunk_id].score = h.score
        return new

    def ranked_evidence(self, *, include_flagged: bool = False, limit: int = 40) -> list[EvidenceHit]:
        items = [e for e in self.evidence.values() if include_flagged or not e.flagged]
        return sorted(items, key=lambda e: e.score, reverse=True)[:limit]

    def claim(self, claim_id: str) -> ClaimItem | None:
        return next((c for c in self.claims if c.id == claim_id), None)

    def add_claim(self, c: ClaimItem) -> ClaimItem:
        norm = " ".join(c.text.lower().split())
        for existing in self.claims:
            if " ".join(existing.text.lower().split()) == norm and existing.kind == c.kind:
                return existing
        self.claims.append(c)
        return c
