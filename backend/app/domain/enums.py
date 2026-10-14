"""Shared vocabulary. Values are stored in the database and sent on the wire, so they never change meaning."""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Account type. Judicial status is a verification result, never an account type."""
    LAWYER = "lawyer"
    CLIENT = "client"
    ADMIN = "admin"
    COMPLIANCE = "compliance"  # reviews connection policies; no case content, no platform administration


class OrgType(StrEnum):
    INDIVIDUAL = "individual"
    LAW_FIRM = "law_firm"
    LEGAL_DEPARTMENT = "legal_department"
    PLATFORM = "platform"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class CaseRole(StrEnum):
    LEAD = "lead"
    MEMBER = "member"
    VIEWER = "viewer"
    CLIENT = "client"  # client portal access only (client-safe projections)


class CaseStatus(StrEnum):
    INTAKE = "intake"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MatterType(StrEnum):
    CRIMINAL = "criminal"
    CIVIL = "civil"
    CONTRACT = "contract"
    PROPERTY = "property"
    FAMILY = "family"
    EMPLOYMENT = "employment"
    CORPORATE = "corporate"
    CONSUMER = "consumer"
    CYBER = "cyber"
    CONSTITUTIONAL = "constitutional"
    OTHER = "other"


class DocumentStatus(StrEnum):
    RECEIVED = "received"
    INDEXED = "indexed"
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"


class ClaimStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(StrEnum):
    """The lawyer's decision on an AI-produced item."""
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class LawyerVerification(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"


class Intent(StrEnum):
    CASE_REVIEW = "CASE_REVIEW"
    EVIDENCE_QA = "EVIDENCE_QA"
    CONTRADICTIONS = "CONTRADICTIONS"
    TIMELINE = "TIMELINE"
    MISSING_INFO = "MISSING_INFO"
    CONTRACT_REVIEW = "CONTRACT_REVIEW"
    LEGAL_RESEARCH = "LEGAL_RESEARCH"
    DRAFT = "DRAFT"
    COMPARE_DOCUMENTS = "COMPARE_DOCUMENTS"
    SUMMARY = "SUMMARY"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"      # stopped by a budget or failure with verified partial results
    REFUSED = "refused"      # request blocked by security policy
    FAILED = "failed"


class Risk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MemoryScope(StrEnum):
    CASE = "case"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    SECURITY = "security"


def values(e: type[StrEnum]) -> tuple[str, ...]:
    return tuple(m.value for m in e)


def check_in(column: str, e: type[StrEnum]) -> str:
    """SQL CHECK expression restricting a column to an enum's values."""
    return f"{column} IN ({','.join(repr(v) for v in values(e))})"
