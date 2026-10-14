from __future__ import annotations

from typing import Literal

from pydantic import EmailStr, Field, field_validator

from .common import ApiModel, OutModel, Role


class RegisterIn(ApiModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Literal["client", "lawyer"]  # admins are never self-registered
    firm_name: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, pattern=r"^\+?\d{10,15}$")

    @field_validator("name", "city")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v


class LoginIn(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class DemoLoginIn(ApiModel):
    persona: Literal["client", "lawyer", "admin", "compliance"]


class UserOut(OutModel):
    id: str
    name: str
    email: str
    role: Role
    city: str | None = None
    lawyer_id: str | None = None
    organization_id: str
    organization_name: str = ""
    verification_status: str | None = None
    is_demo: bool = False


class SessionOut(OutModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
