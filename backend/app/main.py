"""
FormLaw API.

    uvicorn app.main:app --reload --port 8000        (from backend/)

OpenAPI docs: /api/docs (disabled in production).
"""
from __future__ import annotations

import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import admin, approvals, auth, cases, client, compliance, knowledge, lawyers, public, research, runs
from .core import errors, logging as app_logging
from .core.config import get_settings

MAX_BODY = 64 * 1024 * 1024  # whole request; per-file limits are enforced separately


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from .services.runs import fail_interrupted
    try:
        if n := fail_interrupted():
            logging.getLogger("formlaw.runs").warning("%d run(s) interrupted by the last restart were marked failed", n)
    except Exception:  # e.g. migrations not applied yet: never block startup on housekeeping
        logging.getLogger("formlaw.runs").exception("could not reconcile interrupted runs")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app_logging.configure()
    app = FastAPI(
        title="FormLaw API", version="2.0.0",
        description="FormLaw — agentic legal workbench for lawyers. Evidence is the source of truth; the backend enforces security.",
        docs_url=None if s.is_production else "/api/docs", redoc_url=None,
        openapi_url=None if s.is_production else "/api/openapi.json", lifespan=_lifespan,
    )
    errors.install(app)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["authorization", "content-type", "x-requested-with"])

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id", "")[:64] or secrets.token_hex(8)
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY:
            return JSONResponse({"error": {"code": "payload_too_large", "message": "Request too large", "request_id": request.state.request_id}}, 413)
        t0 = time.monotonic()
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers.setdefault("cache-control", "no-store")
        response.headers["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
        if s.is_production:
            response.headers["strict-transport-security"] = "max-age=63072000; includeSubDomains"
        response.headers["server-timing"] = f"app;dur={int((time.monotonic() - t0) * 1000)}"
        return response

    v1 = APIRouter(prefix="/api/v1")

    @v1.get("/health", tags=["health"])
    def health():
        return {"ok": True, "version": app.version}

    for r in (auth.router, cases.router, knowledge.router, runs.router, research.router, lawyers.router, client.router,
              approvals.router, admin.router, compliance.router, public.router):
        v1.include_router(r)
    app.include_router(v1)
    return app


app = create_app()
