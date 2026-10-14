from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import ApiModel, OutModel, PracticeArea

ClaimStatus = Literal["supported", "partial", "conflicted", "unsupported"]


class CaseCreateIn(ApiModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    city: str = Field(default="", max_length=80)
    budget: int = Field(default=0, ge=0, le=100_000_000)


class DocumentOut(OutModel):
    id: str
    name: str
    type: str
    size: int
    extraction: Literal["live", "backend"]
    processing_status: str
    pages: int | None = None
    content_hash: str
    text: str = ""  # only present for the case owner


class EvidenceOut(OutModel):
    id: str
    doc_id: str
    doc_name: str
    page: int
    excerpt: str
    highlight: str
    content_hash: str


class FactOut(OutModel):
    id: str
    label: str
    statement: str
    status: ClaimStatus
    verification_status: str
    evidence_ids: list[str]


class ContradictionSide(OutModel):
    value: str
    evidence_id: str


class ContradictionOut(OutModel):
    id: str
    topic: str
    a: ContradictionSide
    b: ContradictionSide
    confidence: float


class MissingOut(OutModel):
    id: str
    title: str
    why: str
    action: str


class SecurityEventOut(OutModel):
    id: str
    doc_name: str
    kind: str
    snippet: str
    risk: str
    actions: list[str]
    at: str
    case_id: str | None = None


class TraceStepOut(OutModel):
    t: float
    agent: str
    message: str
    kind: str


class MatchOut(OutModel):
    lawyer_id: str
    score: int
    reasons: list[str]
    estimate: tuple[int, int]


class RelatedOut(OutModel):
    case_id: str
    similarity: float
    shared_terms: list[str]


class VerificationOut(OutModel):
    analysed: int
    supported: int
    partial: int
    conflicted: int
    unsupported: int
    coverage: int


class DraftOut(OutModel):
    title: str
    body: str


class AnalysisOut(OutModel):
    task_id: str
    area: PracticeArea
    area_confidence: float
    summary: str
    facts: list[FactOut]
    evidence: list[EvidenceOut]
    contradictions: list[ContradictionOut]
    missing: list[MissingOut]
    security: list[SecurityEventOut]
    related: list[RelatedOut]
    matches: list[MatchOut]
    draft: DraftOut
    verification: VerificationOut
    trace: list[TraceStepOut]
    completed_at: str
    legal_pipeline: dict | None = None
    fee_disclaimer: str


class CaseOut(OutModel):
    id: str
    owner_id: str
    title: str
    description: str
    city: str
    budget: int
    status: str
    documents: list[DocumentOut]
    analysis: AnalysisOut | None = None
    connected_lawyer_ids: list[str]
    created_at: str
    is_demo: bool
    access: Literal["owner", "counsel"]


class CaseSummaryOut(OutModel):
    id: str
    title: str
    city: str
    status: str
    area: str | None
    documents: int
    created_at: str
    is_demo: bool


class ChatIn(ApiModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[str] = Field(default_factory=list, max_length=6)


class ChatOut(OutModel):
    status: Literal["supported", "conflicted", "insufficient"]
    text: str
    evidence_ids: list[str]
    evidence: list[EvidenceOut]
    sources: list[str]
    note: str | None = None
    steps: list[str]
    engine: Literal["extractive", "llm"]
    verification: list[dict]


class DraftIn(ApiModel):
    doc_type: str = Field(min_length=2, max_length=40)


class CorpusFilterIn(ApiModel):
    kinds: list[Literal["constitution_article", "statute_section", "rule", "regulation", "judgment"]] = Field(default_factory=list)
    jurisdiction: str | None = Field(default=None, max_length=120)
    court: str | None = Field(default=None, max_length=200)
    year_from: int | None = Field(default=None, ge=1950, le=2100)
    year_to: int | None = Field(default=None, ge=1950, le=2100)
    case_type: str | None = Field(default=None, max_length=80)
    topic: str | None = Field(default=None, max_length=120)
    citation: str | None = Field(default=None, max_length=60)
    article: str | None = Field(default=None, pattern=r"^\d{1,3}[A-Za-z]{0,2}$")
    statute: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=60)


class ResearchIn(CorpusFilterIn):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=8, ge=1, le=25)


class LegalQuestionIn(CorpusFilterIn):
    question: str = Field(min_length=3, max_length=500)


class LegalEvidenceOut(OutModel):
    evidence_id: str
    document_id: str
    document_name: str
    kind: str | None = None
    court: str | None = None
    date: str | None = None
    citation: str | None = None
    neutral_citation: str | None = None
    case_number: str | None = None
    page: int | None = None
    text: str
    source: str | None = None
    source_key: str | None = None
    source_status: str | None = None
    source_url: str | None = None
    document_url: str | None = None
    license: str | None = None
    attribution: str | None = None
    content_hash: str | None = None
    document_hash: str | None = None
    data_class: str = "VERIFIED_SOURCE"


class LegalClaimOut(OutModel):
    text: str
    evidence_ids: list[str]
    status: str


class LegalAnswerOut(OutModel):
    status: Literal["SUPPORTED", "NOT_FOUND", "INSUFFICIENT_EVIDENCE"]
    answer: str
    claims: list[LegalClaimOut]
    evidence: list[LegalEvidenceOut]
    note: str | None = None
    engine: Literal["extractive", "llm"]


class AuthorityOut(OutModel):
    id: str
    kind: str
    title: str
    reference: str | None
    court: str | None = None
    date: str | None = None
    text: str
    source_name: str
    source_url: str | None
    content_hash: str
    score: float
    citation: str | None = None
    neutral_citation: str | None = None
    case_number: str | None = None
    page: int | None = None
    document_url: str | None = None
    source_status: str | None = None
    data_class: str = "VERIFIED_SOURCE"
    license: str | None = None


class ResearchOut(OutModel):
    query: str
    results: list[AuthorityOut]
    note: str | None = None
