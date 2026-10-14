"""Case/Contract Review Agent.

Flow: validate input -> select versioned prompt -> call LLMProvider for structured output
-> schema re-validation -> deterministic grounding checks -> ReviewResult.
Invalid or ungrounded output is retried with validation feedback (bounded by
settings.max_retries) and otherwise returned as a structured failure, never as a result.

The agent has no tools and no access to credentials, files, network or databases; the only
side effect it can cause is a call to the injected LLMProvider.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.agents.base import AgentContext, AgentError, AgentResult, AgentStatus, WorkflowType
from app.agents.review.prompts import PromptBundle, PromptLibrary, build_user_prompt
from app.agents.review.schemas import ReviewAnalysis, ReviewResult, ReviewStatus
from app.agents.review.security import scan_document
from app.agents.review.validators import GroundingOutcome, ground_analysis
from app.config import Settings
from app.errors import (
    DocumentTooLargeError,
    EmptyDocumentError,
    FormLawError,
    InvalidInputError,
    InvalidWorkflowError,
    LLMFailureError,
    RetryExhaustedError,
    StructuredOutputError,
    summarize_validation_error,
)
from app.logging import log_event
from app.services.llm.base import LLMProvider

logger = logging.getLogger("formlaw.review_agent")


@dataclass
class _RunTrace:
    attempts: int = 0
    prompt_version: str | None = None


class ReviewAgent:
    name = "review_agent"
    version = "0.1.0"

    def __init__(
        self,
        *,
        provider: LLMProvider,
        settings: Settings,
        prompts: PromptLibrary | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._prompts = prompts or PromptLibrary(settings.prompts_dir)

    async def run(self, context: AgentContext) -> AgentResult[ReviewResult]:
        started = time.perf_counter()
        trace = _RunTrace()
        try:
            result = await self._execute(context, trace)
        except FormLawError as exc:
            return self._finish(context, trace, started, error=exc)
        return self._finish(context, trace, started, output=result)

    # ----------------------------------------------------------------- steps

    async def _execute(self, context: AgentContext, trace: _RunTrace) -> ReviewResult:
        workflow = self._validate_context(context)
        prompt = self._prompts.get(workflow)
        trace.prompt_version = prompt.version

        flags = scan_document(context.document_text)
        if flags:
            log_event(
                logger,
                "security_event",
                level=logging.WARNING,
                task_id=str(context.task_id),
                event_type=",".join(f.type for f in flags),
                source="document",
                action="flagged_and_treated_as_data",
            )

        outcome = await self._generate_grounded(context, prompt, trace)
        return ReviewResult(
            **outcome.analysis.model_dump(),
            review_id=uuid4(),
            workflow_type=workflow,
            status=ReviewStatus.COMPLETED,
            warnings=outcome.warnings,
            security_flags=flags,
        )

    def _validate_context(self, context: AgentContext) -> WorkflowType:
        try:
            workflow = WorkflowType(context.workflow_type)
        except ValueError as exc:
            raise InvalidWorkflowError("Unsupported workflow type.") from exc
        if not context.request.strip():
            raise InvalidInputError("Request must not be empty.")
        if not context.document_text.strip():
            raise EmptyDocumentError("Document text must not be empty.")
        limit = self._settings.max_document_chars
        if len(context.document_text) > limit:
            # Never silently truncate a legal document.
            raise DocumentTooLargeError(f"Document exceeds the maximum of {limit} characters.")
        return workflow

    async def _generate_grounded(
        self, context: AgentContext, prompt: PromptBundle, trace: _RunTrace
    ) -> GroundingOutcome:
        max_attempts = self._settings.max_retries + 1
        feedback: list[str] = []
        last_error: FormLawError | None = None

        for attempt in range(1, max_attempts + 1):
            trace.attempts = attempt
            try:
                raw = await self._call_provider(context, prompt, feedback)
                analysis = self._coerce(raw)
                return ground_analysis(
                    analysis,
                    document_text=context.document_text,
                    document_name=context.document_name,
                )
            except LLMFailureError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
            except StructuredOutputError as exc:
                last_error, feedback = exc, exc.details or [exc.message]
            except ValidationError as exc:
                feedback = summarize_validation_error(exc)
                last_error = StructuredOutputError("Model output failed schema validation.")
            except FormLawError as exc:  # GroundingViolationError and other retryable content errors
                if not exc.retryable:
                    raise
                last_error = exc
                feedback = list(getattr(exc, "violations", [exc.message]))

            log_event(
                logger,
                "review_attempt_failed",
                level=logging.WARNING,
                task_id=str(context.task_id),
                attempt=attempt,
                error_code=last_error.code,
            )
            if attempt < max_attempts and self._settings.retry_backoff_seconds > 0:
                await asyncio.sleep(self._settings.retry_backoff_seconds * attempt)

        assert last_error is not None  # loop ran at least once
        raise RetryExhaustedError(last_error_code=last_error.code, attempts=max_attempts)

    async def _call_provider(
        self, context: AgentContext, prompt: PromptBundle, feedback: list[str]
    ) -> BaseModel:
        user_prompt = build_user_prompt(
            request=context.request,
            document_text=context.document_text,
            document_name=context.document_name,
            feedback=feedback,
        )
        try:
            return await asyncio.wait_for(
                self._provider.generate_structured(
                    system_prompt=prompt.system_prompt,
                    user_prompt=user_prompt,
                    schema=ReviewAnalysis,
                    model=self._settings.llm_model,
                ),
                timeout=self._settings.llm_timeout_seconds,
            )
        except TimeoutError as exc:
            raise LLMFailureError("LLM call timed out.", retryable=True) from exc

    @staticmethod
    def _coerce(raw: BaseModel) -> ReviewAnalysis:
        """Re-validate whatever the provider returned; never trust an unchecked instance."""
        if not isinstance(raw, ReviewAnalysis):
            raise StructuredOutputError("Provider returned an unexpected output type.")
        return ReviewAnalysis.model_validate(raw.model_dump())

    # ------------------------------------------------------------- reporting

    def _finish(
        self,
        context: AgentContext,
        trace: _RunTrace,
        started: float,
        *,
        output: ReviewResult | None = None,
        error: FormLawError | None = None,
    ) -> AgentResult[ReviewResult]:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        status = AgentStatus.FAILED if error else AgentStatus.COMPLETED
        log_event(
            logger,
            "agent_run_failed" if error else "agent_run_completed",
            level=logging.ERROR if error else logging.INFO,
            task_id=str(context.task_id),
            agent_name=self.name,
            agent_version=self.version,
            workflow_type=str(getattr(context.workflow_type, "value", context.workflow_type)),
            duration_ms=duration_ms,
            status=status.value,
            error_code=error.code if error else None,
            attempts=trace.attempts,
            prompt_version=trace.prompt_version,
            model=self._settings.llm_model,
            document_chars=len(context.document_text),
            document_sha256=hashlib.sha256(context.document_text.encode()).hexdigest()[:12],
        )
        return AgentResult[ReviewResult](
            agent_name=self.name,
            agent_version=self.version,
            task_id=context.task_id,
            status=status,
            output=output,
            error=(
                AgentError(code=error.code, message=error.message, retryable=error.retryable)
                if error
                else None
            ),
            duration_ms=duration_ms,
            attempts=trace.attempts,
            prompt_version=trace.prompt_version,
            model=self._settings.llm_model or None,
        )
