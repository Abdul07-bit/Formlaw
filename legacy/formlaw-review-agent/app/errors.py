"""Explicit, observable error types. Messages are safe to show to API clients:
they never contain document text, prompts, or model output."""

from pydantic import ValidationError


class FormLawError(Exception):
    """Base class for all expected, domain-level failures."""

    code: str = "INTERNAL_ERROR"
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidInputError(FormLawError):
    code = "INVALID_INPUT"


class EmptyDocumentError(InvalidInputError):
    code = "EMPTY_DOCUMENT"


class DocumentTooLargeError(InvalidInputError):
    code = "DOCUMENT_TOO_LARGE"


class InvalidWorkflowError(InvalidInputError):
    code = "INVALID_WORKFLOW"


class LLMNotConfiguredError(FormLawError):
    code = "LLM_NOT_CONFIGURED"


class PromptNotFoundError(FormLawError):
    code = "PROMPT_NOT_FOUND"


class LLMFailureError(FormLawError):
    """Provider call failed (network, timeout, 429/5xx, or rejected request)."""

    code = "LLM_FAILURE"

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class StructuredOutputError(FormLawError):
    """Model output could not be parsed/validated against the requested schema."""

    code = "STRUCTURED_OUTPUT_INVALID"
    retryable = True

    def __init__(self, message: str, *, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class GroundingViolationError(FormLawError):
    """Output parsed fine but violates evidence-grounding rules (e.g. fabricated evidence)."""

    code = "GROUNDING_VIOLATION"
    retryable = True

    def __init__(self, violations: list[str]) -> None:
        super().__init__("Model output violated evidence-grounding rules.")
        self.violations = violations


class RetryExhaustedError(FormLawError):
    code = "RETRY_EXHAUSTED"

    def __init__(self, *, last_error_code: str, attempts: int) -> None:
        super().__init__(
            f"Review failed after {attempts} attempt(s); last error: {last_error_code}."
        )
        self.last_error_code = last_error_code
        self.attempts = attempts


class AgentExecutionError(FormLawError):
    """Wraps a failed AgentResult so the API layer can render it uniformly."""

    def __init__(self, *, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


HTTP_STATUS_BY_CODE: dict[str, int] = {
    "INVALID_INPUT": 422,
    "EMPTY_DOCUMENT": 422,
    "INVALID_WORKFLOW": 422,
    "DOCUMENT_TOO_LARGE": 413,
    "LLM_NOT_CONFIGURED": 503,
    "PROMPT_NOT_FOUND": 500,
    "LLM_FAILURE": 502,
    "STRUCTURED_OUTPUT_INVALID": 502,
    "GROUNDING_VIOLATION": 502,
    "RETRY_EXHAUSTED": 502,
}


def http_status_for(code: str) -> int:
    return HTTP_STATUS_BY_CODE.get(code, 500)


def summarize_validation_error(exc: ValidationError, limit: int = 10) -> list[str]:
    """Return 'location: message' lines only - never the offending input values."""
    lines = []
    for err in exc.errors()[:limit]:
        loc = ".".join(str(part) for part in err.get("loc", ()))
        lines.append(f"{loc}: {err.get('msg', 'invalid')}")
    return lines
