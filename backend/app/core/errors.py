"""
Structured errors. Every API error has the same shape:

    {"error": {"code": "not_found", "message": "Case not found", "request_id": "..."}}

Internal details (stack traces, SQL, file paths) never reach the client.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("formlaw.errors")


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.details = details


class NotFound(AppError):
    status, code = 404, "not_found"


class Unauthorized(AppError):
    status, code = 401, "unauthorized"


class Forbidden(AppError):
    status, code = 403, "forbidden"


class Conflict(AppError):
    status, code = 409, "conflict"


class TooLarge(AppError):
    status, code = 413, "payload_too_large"


class Unprocessable(AppError):
    status, code = 422, "unprocessable"


class RateLimited(AppError):
    status, code = 429, "rate_limited"


class ApprovalRequired(AppError):
    """A HIGH-risk action was requested without explicit human approval."""
    status, code = 428, "approval_required"


class AgentLimitExceeded(AppError):
    status, code = 503, "agent_limit_exceeded"


def _body(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        err["details"] = details
    return {"error": err}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(_body(request, "validation_error", "Request validation failed", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}.get(exc.status_code, "http_error")
        return JSONResponse(_body(request, code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Logged with the request id for correlation; the client gets a generic message.
        log.exception("Unhandled error request_id=%s", getattr(request.state, "request_id", None))
        return JSONResponse(_body(request, "internal_error", "Something went wrong. Please try again."), status_code=500)
