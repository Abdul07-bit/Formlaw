"""Strongly typed contracts for the Review Agent.

`ReviewAnalysis` is what the LLM is asked to produce. `ReviewResult` is what the
system returns: the analysis plus fields only deterministic code may set
(review_id, status, warnings, security_flags).
"""

from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.base import WorkflowType

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveInt = Annotated[int, Field(ge=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReviewStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvidenceReference(StrictModel):
    evidence_id: str = Field(min_length=1, max_length=32)
    document_name: str | None
    page: PositiveInt | None
    section: str | None
    paragraph: str | None
    text: str = Field(min_length=1, max_length=2000)
    source_type: str = Field(min_length=1, max_length=64)


class Party(StrictModel):
    id: str
    name: str = Field(min_length=1)
    role: str
    evidence_ids: list[str]


class Fact(StrictModel):
    id: str
    statement: str = Field(min_length=1)
    category: str | None
    evidence_ids: list[str]
    confidence: Confidence
    status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]


class TimelineEvent(StrictModel):
    id: str
    date: str | None
    description: str = Field(min_length=1)
    evidence_ids: list[str]
    confidence: Confidence
    status: Literal["SUPPORTED", "CONFLICTED", "UNKNOWN"]


class Issue(StrictModel):
    id: str
    title: str = Field(min_length=1)
    description: str
    type: Literal["FACTUAL", "PROCEDURAL", "CONTRACTUAL", "LEGAL", "EVIDENTIARY"]
    evidence_ids: list[str]
    confidence: Confidence


class Risk(StrictModel):
    id: str
    title: str = Field(min_length=1)
    description: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    evidence_ids: list[str]
    is_inference: bool
    recommended_action: str | None
    confidence: Confidence


class Contradiction(StrictModel):
    id: str
    description: str = Field(min_length=1)
    conflicting_evidence_ids: list[str] = Field(min_length=2)
    affected_ids: list[str]
    confidence: Confidence
    resolution_status: Literal["UNRESOLVED"] = "UNRESOLVED"


class MissingInformation(StrictModel):
    id: str
    description: str = Field(min_length=1)
    why_it_matters: str
    confidence: Confidence


class Claim(StrictModel):
    id: str
    text: str = Field(min_length=1)
    claim_type: Literal["FACT", "LEGAL_RULE", "INFERENCE", "RECOMMENDATION"]
    evidence_ids: list[str]
    confidence: Confidence
    verification_status: Literal[
        "PENDING",
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
        "CONTRADICTED",
        "UNVERIFIED",
    ]


class SecurityFlag(StrictModel):
    type: Literal["PROMPT_INJECTION", "DELIMITER_SPOOFING"]
    severity: Literal["MEDIUM", "HIGH"]
    source: Literal["document"] = "document"
    description: str


class ReviewAnalysis(StrictModel):
    """LLM-facing output schema. Every field is required: omission is a validation error."""

    summary: str = Field(min_length=1)
    summary_evidence_ids: list[str]
    parties: list[Party]
    facts: list[Fact]
    timeline: list[TimelineEvent]
    issues: list[Issue]
    risks: list[Risk]
    contradictions: list[Contradiction]
    missing_information: list[MissingInformation]
    claims: list[Claim]
    evidence: list[EvidenceReference]
    confidence: Confidence


class ReviewResult(ReviewAnalysis):
    review_id: UUID
    workflow_type: WorkflowType
    status: ReviewStatus
    warnings: list[str]
    security_flags: list[SecurityFlag]


class ReviewRequest(BaseModel):
    """API/service input. Document size is checked against configured limits by the agent."""

    model_config = ConfigDict(extra="forbid")

    request: str = Field(min_length=1, max_length=4000)
    workflow_type: WorkflowType
    document_text: str = Field(min_length=1)
    document_name: str | None = Field(default=None, max_length=255)

    @field_validator("request", "document_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ReviewResponse(BaseModel):
    review_id: UUID
    workflow_type: WorkflowType
    status: ReviewStatus
    result: ReviewResult
