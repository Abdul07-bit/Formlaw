import pytest

from app.agents.base import AgentContext, WorkflowType
from app.config import Settings
from tests.fixtures import ARJUN_DOC


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_model="test-model",
        max_document_chars=5000,
        max_retries=2,
        retry_backoff_seconds=0,
        llm_timeout_seconds=1.0,
    )


def make_context(
    *,
    request: str = "When was Arjun Kumar arrested?",
    document_text: str = ARJUN_DOC,
    workflow: WorkflowType = WorkflowType.CASE_REVIEW,
    document_name: str | None = "case_001.pdf",
) -> AgentContext:
    return AgentContext(
        request=request, workflow_type=workflow,
        document_text=document_text, document_name=document_name,
    )  # fmt: skip
