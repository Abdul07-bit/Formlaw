from fastapi import APIRouter, Depends, Request

from app.agents.base import AgentStatus
from app.agents.review.schemas import ReviewRequest, ReviewResponse
from app.agents.review.service import ReviewService
from app.api.dependencies import get_review_service
from app.errors import AgentExecutionError

router = APIRouter(prefix="/reviews", tags=["reviews"])

_ERROR_RESPONSES = {
    413: {"description": "Document exceeds MAX_DOCUMENT_CHARS"},
    422: {"description": "Invalid input"},
    502: {"description": "Model/validation failure after retries"},
    503: {"description": "LLM provider not configured"},
}


@router.post("", response_model=ReviewResponse, responses=_ERROR_RESPONSES)
async def create_review(
    payload: ReviewRequest,
    request: Request,  # noqa: ARG001 - kept for request-scoped auth hooks
    service: ReviewService = Depends(get_review_service),  # noqa: B008
) -> ReviewResponse:
    outcome = await service.review(payload)
    if outcome.status is AgentStatus.COMPLETED and outcome.output is not None:
        result = outcome.output
        return ReviewResponse(
            review_id=result.review_id,
            workflow_type=result.workflow_type,
            status=result.status,
            result=result,
        )
    error = outcome.error
    raise AgentExecutionError(
        code=error.code if error else "INTERNAL_ERROR",
        message=error.message if error else "Review failed.",
        retryable=error.retryable if error else False,
    )
