from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Role = Literal["client", "lawyer", "admin", "compliance"]
Matter = Literal["criminal", "civil", "contract", "property", "family", "employment", "corporate", "consumer", "cyber", "constitutional", "other"]


class ApiModel(BaseModel):
    """camelCase on the wire (matches src/types), snake_case in Python. Unknown input fields are rejected (no mass assignment)."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class OutModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Ok(OutModel):
    ok: bool = True
