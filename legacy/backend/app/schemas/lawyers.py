from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import ApiModel, OutModel, PracticeArea

Outcome = Literal["Allowed", "Dismissed", "Settled", "Acquitted", "Convicted", "Bail granted", "Decree passed"]


class KycSubmissionOut(OutModel):
    degree_certificate: str | None
    id_card: str | None
    id_type: str | None
    face_match_score: float | None
    liveness_passed: bool | None
    provider: str
    checks: list[dict]
    submitted_at: str
    reviewed_at: str | None = None
    review_note: str | None = None


class LawyerOut(OutModel):
    id: str
    name: str
    title: str
    role: Literal["lawyer", "judge"]
    photo_hue: int
    initials: str
    city: str
    state: str
    courts: list[str]
    bar_council: str
    enrolment_no: str
    experience_years: int
    practice_areas: list[str]
    languages: list[str]
    consultation_fee: int
    hearing_fee: int
    rating: float
    reviews: int
    cases_handled: int
    response_hours: int
    bio: str
    kyc: Literal["not_started", "pending", "verified", "rejected"]
    profile_status: str
    is_demo: bool
    kyc_submission: KycSubmissionOut | None = None  # only for the lawyer themself and admins


class LawyerProfileIn(ApiModel):
    """Fields a lawyer may edit. Verification status, ratings and profile status are NOT here (server-controlled)."""
    name: str | None = Field(default=None, min_length=2, max_length=120)
    title: Literal["Advocate", "Senior Advocate", "Retd. Judge"] | None = None
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    courts: list[str] | None = Field(default=None, max_length=10)
    bar_council: str | None = Field(default=None, max_length=120)
    enrolment_no: str | None = Field(default=None, max_length=60)
    experience_years: int | None = Field(default=None, ge=0, le=70)
    practice_areas: list[PracticeArea] | None = Field(default=None, max_length=8)
    languages: list[str] | None = Field(default=None, max_length=12)
    consultation_fee: int | None = Field(default=None, ge=0, le=10_000_000)
    hearing_fee: int | None = Field(default=None, ge=0, le=10_000_000)
    response_hours: int | None = Field(default=None, ge=1, le=240)
    bio: str | None = Field(default=None, max_length=2000)


class LawyerCaseIn(ApiModel):
    title: str = Field(min_length=3, max_length=200)
    area: PracticeArea
    court: str = Field(min_length=2, max_length=160)
    year: int = Field(ge=1950, le=2100)
    outcome: Outcome
    sections: list[str] = Field(default_factory=list, max_length=20)
    summary: str = Field(min_length=10, max_length=3000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    duration_months: int = Field(default=0, ge=0, le=600)


class LawyerCaseOut(OutModel):
    id: str
    lawyer_id: str
    title: str
    area: str
    court: str
    year: int
    outcome: str
    sections: list[str]
    summary: str
    keywords: list[str]
    duration_months: int
    verified: bool
    verification_status: str
    is_demo: bool


class KycDecisionIn(ApiModel):
    approve: bool
    note: str = Field(default="", max_length=500)


class VerifyCaseIn(ApiModel):
    approve: bool
