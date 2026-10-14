"""Request bodies for the workbench, portal, lawyer and admin APIs. Unknown fields are rejected (no mass assignment)."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import ApiModel, Matter


class CaseIn(ApiModel):
    title: str = Field(min_length=2, max_length=200)
    reference: str | None = Field(default=None, max_length=40)
    description: str = Field(default="", max_length=5000)
    matter_type: Matter = "other"
    jurisdiction: str = Field(default="", max_length=120)
    court: str = Field(default="", max_length=160)
    client_name: str = Field(default="", max_length=120)


class CasePatch(ApiModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    matter_type: Matter | None = None
    status: Literal["active", "on_hold", "closed", "archived"] | None = None
    jurisdiction: str | None = Field(default=None, max_length=120)
    court: str | None = Field(default=None, max_length=160)
    client_name: str | None = Field(default=None, max_length=120)


class MemberIn(ApiModel):
    email: str = Field(max_length=254)
    role: Literal["member", "viewer"] = "member"


class ChatIn(ApiModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, max_length=36)


class WorkflowIn(ApiModel):
    instructions: str = Field(default="", max_length=2000)
    thread_id: str | None = Field(default=None, max_length=36)
    draft_kind: Literal["legal_notice", "case_summary", "research_memo", "argument_outline", "client_update", "chronology",
                        "response_draft", "contract_clause", "briefing_note", "cross_examination_questions"] | None = None


class ReviewIn(ApiModel):
    decision: Literal["accepted", "rejected", "unreviewed"]
    note: str = Field(default="", max_length=500)


class StatusIn(ApiModel):
    status: Literal["open", "requested", "resolved", "dismissed"]
    note: str = Field(default="", max_length=500)


class FindingIn(ApiModel):
    title: str = Field(min_length=1, max_length=240)
    content: dict = Field(default_factory=dict)
    message_id: str | None = Field(default=None, max_length=36)
    note: str = Field(default="", max_length=4000)


class TaskIn(ApiModel):
    title: str = Field(min_length=1, max_length=240)
    due_date: date | None = None
    source: Literal["lawyer", "agent"] = "lawyer"


class TaskPatch(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: Literal["open", "done"] | None = None
    due_date: date | None = None


class DraftPatch(ApiModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=60000)


class ResearchIn(ApiModel):
    query: str = Field(min_length=3, max_length=1000)
    year_from: int | None = Field(default=None, ge=1950, le=2100)
    year_to: int | None = Field(default=None, ge=1950, le=2100)


class ApprovalIn(ApiModel):
    action: Literal["client_update.send", "draft.share", "case.delete", "document.delete", "connection.request"]
    resource_id: str = Field(max_length=36)
    params: dict[str, str] = Field(default_factory=dict)


class DecisionIn(ApiModel):
    approve: bool


class LawyerProfileIn(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    jurisdictions: list[str] | None = Field(default=None, max_length=10)
    bar_council: str | None = Field(default=None, max_length=120)
    enrolment_number: str | None = Field(default=None, max_length=60)
    experience_years: int | None = Field(default=None, ge=0, le=70)
    languages: list[str] | None = Field(default=None, max_length=12)
    education: list[str] | None = Field(default=None, max_length=10)
    qualifications: list[str] | None = Field(default=None, max_length=10)
    bio: str | None = Field(default=None, max_length=2000)
    practice_areas: list[Matter] | None = Field(default=None, max_length=8)
    accepting_clients: bool | None = None
    consultation_fee: int | None = Field(default=None, ge=0, le=10_000_000)
    fee_range_min: int | None = Field(default=None, ge=0, le=1_000_000_000)
    fee_range_max: int | None = Field(default=None, ge=0, le=1_000_000_000)
    publish: bool | None = None

    @model_validator(mode="after")
    def _fee_order(self):
        if self.fee_range_min is not None and self.fee_range_max is not None and self.fee_range_min > self.fee_range_max:
            raise ValueError("feeRangeMin cannot exceed feeRangeMax")
        return self


class IntakeIn(ApiModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=8000)
    answers: dict[str, str] = Field(default_factory=dict)
    city: str = Field(default="", max_length=80)
    language: str = Field(default="", max_length=40)
    # Other people or organisations involved (e.g. the employer, the other spouse). Used only for conflict checks.
    other_parties: list[Annotated[str, Field(min_length=2, max_length=120)]] = Field(default_factory=list, max_length=10)
    budget_max: int | None = Field(default=None, ge=0, le=1_000_000_000)  # INR the client is prepared to spend


class IntakePatch(ApiModel):
    budget_max: int | None = Field(default=None, ge=0, le=1_000_000_000)
    other_parties: list[Annotated[str, Field(min_length=2, max_length=120)]] | None = Field(default=None, max_length=10)


class ConflictDecisionIn(ApiModel):
    clear: bool  # true: no conflict found; false: conflict → the request is declined without stating a reason
    note: str = Field(default="", max_length=1000)


class ConnectIn(ApiModel):
    lawyer_id: str = Field(max_length=36)
    note: str = Field(default="", max_length=1000)
    # The client must echo the policy version and disclosure hash they were shown (GET /connection-policy); if the policy
    # changed since, the request is refused so consent is never recorded against text the client did not see.
    policy_version: int = Field(ge=1)
    disclosure_hash: str = Field(min_length=64, max_length=64)


class ConnectionPolicyIn(ApiModel):
    public_discovery_enabled: bool = False
    matching_enabled: bool = False
    client_requests_enabled: bool = False
    show_fees: bool = False
    visible_profile_fields: list[str] = Field(default_factory=list, max_length=20)
    required_disclosures: list[str] = Field(default_factory=list, max_length=12)
    professional_rules: list[str] = Field(default_factory=list, max_length=20)
    rationale: str = Field(min_length=10, max_length=8000)


class PolicyReviewIn(ApiModel):
    approve: bool
    review_reference: str = Field(min_length=3, max_length=200)  # e.g. the counsel opinion this decision relies on
    note: str = Field(min_length=3, max_length=1000)
    # The reviewer attests that qualified regulatory counsel reviewed this exact policy version.
    counsel_reviewed: bool = False


class AdminNoteIn(ApiModel):
    note: str = Field(min_length=3, max_length=500)


class RespondIn(ApiModel):
    accept: bool
    note: str = Field(default="", max_length=1000)


class MessageIn(ApiModel):
    body: str = Field(min_length=1, max_length=4000)


class ClientUpdateIn(ApiModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=8000)


class BarRollCheckIn(ApiModel):
    """What the reviewer actually checked against an official State Bar Council roll (required to approve)."""
    source: str = Field(min_length=5, max_length=200)          # e.g. "Bar Council of Delhi — roll of advocates"
    reference: str = Field(min_length=3, max_length=500)       # URL, register volume/page, or letter reference
    checked_on: date
    enrolment_number_matches: bool
    name_matches: bool


class VerificationDecisionIn(ApiModel):
    approve: bool
    note: str = Field(min_length=3, max_length=500)
    bar_roll_check: BarRollCheckIn | None = None
    verified_areas: list[Matter] = Field(default_factory=list, max_length=8)
    judicial_status: bool = False
