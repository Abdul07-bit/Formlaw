"""Thin application-service layer: API/Orchestrator-facing entry point to the Review Agent.

This is where authentication/authorization (user -> organization -> case -> document) and
document retrieval will be added later; the agent itself stays unaware of them.
"""

from uuid import UUID, uuid4

from app.agents.base import AgentContext, AgentResult
from app.agents.review.agent import ReviewAgent
from app.agents.review.schemas import ReviewRequest, ReviewResult


class ReviewService:
    def __init__(self, agent: ReviewAgent) -> None:
        self._agent = agent

    async def review(
        self,
        request: ReviewRequest,
        *,
        task_id: UUID | None = None,
        case_id: UUID | None = None,
    ) -> AgentResult[ReviewResult]:
        context = AgentContext(
            task_id=task_id or uuid4(),
            case_id=case_id,
            request=request.request,
            workflow_type=request.workflow_type,
            document_text=request.document_text,
            document_name=request.document_name,
        )
        return await self._agent.run(context)
