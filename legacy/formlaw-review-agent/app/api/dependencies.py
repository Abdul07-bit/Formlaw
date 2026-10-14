"""FastAPI dependencies. Authentication/authorization will be added here as extra
dependencies (e.g. `Depends(get_principal)`) without touching the agent."""

from fastapi import Request

from app.agents.review.agent import ReviewAgent
from app.agents.review.prompts import PromptLibrary
from app.agents.review.service import ReviewService
from app.config import Settings
from app.errors import LLMNotConfiguredError
from app.services.llm.base import LLMProvider


def get_review_service(request: Request) -> ReviewService:
    state = request.app.state
    provider: LLMProvider | None = state.llm_provider
    if provider is None:
        raise LLMNotConfiguredError("LLM_API_KEY and LLM_MODEL must be configured.")
    settings: Settings = state.settings
    prompts: PromptLibrary = state.prompts
    return ReviewService(ReviewAgent(provider=provider, settings=settings, prompts=prompts))
