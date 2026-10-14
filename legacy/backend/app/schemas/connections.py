from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import ApiModel, OutModel


class MessageOut(OutModel):
    id: str
    from_: Literal["client", "lawyer", "system"] = Field(alias="from")
    text: str
    at: str


class ConversationOut(OutModel):
    id: str
    case_id: str
    case_title: str
    client_id: str
    client_name: str
    lawyer_id: str
    status: Literal["requested", "accepted", "declined", "closed"]
    quote: int | None = None
    messages: list[MessageOut]
    updated_at: str


class RespondIn(ApiModel):
    accept: bool
    quote: int | None = Field(default=None, ge=0, le=100_000_000)


class MessageIn(ApiModel):
    text: str = Field(min_length=1, max_length=4000)


class ApprovalCreateIn(ApiModel):
    action: Literal["connection.request", "draft.share", "case.delete", "document.delete"]
    resource_id: str = Field(min_length=1, max_length=36)
    params: dict[str, str] = Field(default_factory=dict)


class ApprovalOut(OutModel):
    id: str
    action: str
    risk_level: str
    resource_type: str
    resource_id: str
    summary: str
    status: str
    created_at: str
    decided_at: str | None = None
    result: dict | None = None


class ApprovalDecisionIn(ApiModel):
    approve: bool
