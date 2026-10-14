"""Uniform error envelope: {"error": {"code", "message", "request_id"}}.

Never exposes stack traces, prompts, document text, or request bodies.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import FormLawError, http_status_for
from app.logging import log_event

logger = logging.getLogger("formlaw.api")


def request_id_of(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def error_response(
    *, status_code: int, code: str, message: str, request_id: str, details: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "request_id": request_id}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FormLawError)
    async def _domain_error(request: Request, exc: FormLawError) -> JSONResponse:
        return error_response(
            status_code=http_status_for(exc.code),
            code=exc.code,
            message=exc.message,
            request_id=request_id_of(request),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default handler echoes the submitted input (i.e. the document). We don't.
        details = [
            {"loc": [str(p) for p in err.get("loc", ())], "msg": err.get("msg", "invalid")}
            for err in exc.errors()
        ]
        return error_response(
            status_code=422,
            code="INVALID_INPUT",
            message="Request validation failed.",
            request_id=request_id_of(request),
            details=details,
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log_event(
            logger,
            "unhandled_exception",
            level=logging.ERROR,
            request_id=request_id_of(request),
            error_type=type(exc).__name__,
        )
        return error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="An internal error occurred.",
            request_id=request_id_of(request),
        )
