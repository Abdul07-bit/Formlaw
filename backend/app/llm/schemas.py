"""
Output contracts for every model call. Models fill these; code then validates grounding (quotes, ids, values).
Bounded lengths keep a misbehaving model from flooding the run.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentName = Literal["CASE_REVIEW", "EVIDENCE_QA", "CONTRADICTIONS", "TIMELINE", "MISSING_INFO", "CONTRACT_REVIEW",
                     "LEGAL_RESEARCH", "DRAFT", "COMPARE_DOCUMENTS", "SUMMARY", "OUT_OF_SCOPE"]


class IntentOut(BaseModel):
    intent: IntentName
    secondary: list[IntentName] = Field(default_factory=list, max_length=3)
    topic: str = Field(default="", max_length=120)
    draft_kind: str = Field(default="", max_length=40)
    wants_research: bool = False


class PlanOut(BaseModel):
    queries: list[str] = Field(default_factory=list, max_length=5)
    focus_topics: list[str] = Field(default_factory=list, max_length=3)
    rationale: str = Field(default="", max_length=300)


class Quoted(BaseModel):
    passage_id: str = Field(max_length=20)
    quote: str = Field(max_length=800)


class PartyOut(Quoted):
    name: str = Field(max_length=120)
    role: str = Field(max_length=60)


class FactOut(Quoted):
    text: str = Field(max_length=500)
    kind: Literal["fact", "allegation", "admission", "disputed", "procedural"] = "fact"


class EventOut(Quoted):
    date_text: str = Field(max_length=60)
    date_iso: str = Field(default="", max_length=10)
    description: str = Field(max_length=300)
    event_type: str = Field(default="event", max_length=40)


class IssueOut(Quoted):
    text: str = Field(max_length=400)


class CaseDetailOut(Quoted):
    field: Literal["case_number", "court", "jurisdiction", "case_type", "police_station", "procedural_status", "provision"]
    value: str = Field(max_length=160)


class ExtractOut(BaseModel):
    case_details: list[CaseDetailOut] = Field(default_factory=list, max_length=20)
    parties: list[PartyOut] = Field(default_factory=list, max_length=30)
    facts: list[FactOut] = Field(default_factory=list, max_length=40)
    events: list[EventOut] = Field(default_factory=list, max_length=40)
    issues: list[IssueOut] = Field(default_factory=list, max_length=15)
    uncertainties: list[str] = Field(default_factory=list, max_length=10)


class ComposeSentence(BaseModel):
    text: str = Field(max_length=600)
    passage_ids: list[str] = Field(default_factory=list, max_length=6)
    quote: str = Field(default="", max_length=800)


class ComposeOut(BaseModel):
    summary: str = Field(max_length=800)
    sentences: list[ComposeSentence] = Field(default_factory=list, max_length=12)
    limitations: list[str] = Field(default_factory=list, max_length=6)


class Side(Quoted):
    value: str = Field(max_length=120)


class ContradictionOut(BaseModel):
    topic: str = Field(max_length=120)
    nature: Literal["date", "amount", "statement", "clause", "identity", "place", "time"]
    a: Side
    b: Side
    explanation: str = Field(default="", max_length=400)


class ContradictionsOut(BaseModel):
    contradictions: list[ContradictionOut] = Field(default_factory=list, max_length=12)


class ContractFindingOut(Quoted):
    category: str = Field(max_length=30)
    title: str = Field(max_length=120)
    text: str = Field(max_length=500)
    risk_level: Literal["low", "medium", "high"] = "low"
    party: str = Field(default="", max_length=120)


class MissingProvisionOut(BaseModel):
    title: str = Field(max_length=120)
    why: str = Field(max_length=300)


class ContractOut(BaseModel):
    findings: list[ContractFindingOut] = Field(default_factory=list, max_length=40)
    missing_provisions: list[MissingProvisionOut] = Field(default_factory=list, max_length=15)


class DraftItem(BaseModel):
    text: str = Field(max_length=800)
    fact_ids: list[str] = Field(default_factory=list, max_length=10)
    authority_ids: list[str] = Field(default_factory=list, max_length=10)


class DraftOut(BaseModel):
    title: str = Field(max_length=200)
    facts: list[DraftItem] = Field(default_factory=list, max_length=30)
    authorities: list[DraftItem] = Field(default_factory=list, max_length=15)
    inferences: list[DraftItem] = Field(default_factory=list, max_length=15)
    recommendations: list[str] = Field(default_factory=list, max_length=12)
    body: str = Field(default="", max_length=12000)


class JudgeVerdict(BaseModel):
    claim_id: str = Field(max_length=20)
    verdict: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]
    reason: str = Field(default="", max_length=300)


class JudgeOut(BaseModel):
    verdicts: list[JudgeVerdict] = Field(default_factory=list, max_length=60)


class IntakeParty(BaseModel):
    name: str = Field(max_length=120)
    role: str = Field(max_length=60)


class IntakeEvent(BaseModel):
    date_text: str = Field(max_length=60)
    event: str = Field(max_length=300)


class IntakeOut(BaseModel):
    problem: str = Field(max_length=800)
    legal_domain: Literal["criminal", "civil", "contract", "property", "family", "employment", "corporate", "consumer",
                          "cyber", "constitutional", "other"] = "other"
    parties: list[IntakeParty] = Field(default_factory=list, max_length=12)
    timeline: list[IntakeEvent] = Field(default_factory=list, max_length=20)
    documents_mentioned: list[str] = Field(default_factory=list, max_length=20)
    jurisdiction: str = Field(default="", max_length=120)
    urgency: Literal["urgent", "soon", "normal"] = "normal"
    complexity: Literal["low", "medium", "high"] = "medium"
    known_evidence: list[str] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=15)
    questions_for_client: list[str] = Field(default_factory=list, max_length=10)


class AnswerSentence(BaseModel):
    text: str = Field(max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)


class GroundedAnswer(BaseModel):
    sentences: list[AnswerSentence] = Field(default_factory=list, max_length=12)
