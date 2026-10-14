"""Common agent contract. The future Orchestrator depends only on this module."""

from enum import Enum
from typing import Any, Generic, Protocol, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

OutputT = TypeVar("OutputT", bound=BaseModel)


class WorkflowType(str, Enum):
    CASE_REVIEW = "case_review"
    CONTRACT_REVIEW = "contract_review"


class AgentStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentContext(BaseModel):
    """Everything an agent receives. No credentials, no handles to infrastructure."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID = Field(default_factory=uuid4)
    case_id: UUID | None = None
    request: str
    workflow_type: WorkflowType
    document_text: str
    document_name: str | None = None


class AgentError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class AgentResult(BaseModel, Generic[OutputT]):
    """Typed envelope returned by every agent; failures are data, not exceptions."""

    agent_name: str
    agent_version: str
    task_id: UUID
    status: AgentStatus
    output: OutputT | None = None
    error: AgentError | None = None
    duration_ms: float
    attempts: int
    prompt_version: str | None = None
    model: str | None = None


class Agent(Protocol):
    name: str
    version: str

    async def run(self, context: AgentContext) -> AgentResult[Any]: ...
