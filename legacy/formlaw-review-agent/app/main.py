"""FastAPI application factory. Run with:
    uvicorn app.main:create_app --factory
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.agents.review.prompts import PromptLibrary
from app.api.errors import register_error_handlers
from app.api.reviews import router as reviews_router
from app.config import Settings, get_settings
from app.logging import configure_logging
from app.services.llm.base import LLMProvider
from app.services.llm.provider import OpenAICompatibleProvider, build_provider


def create_app(
    settings: Settings | None = None, llm_provider: LLMProvider | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    owned_provider: OpenAICompatibleProvider | None = None
    if llm_provider is None and settings.llm_configured:
        owned_provider = build_provider(settings)
        llm_provider = owned_provider

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_provider is not None:
            await owned_provider.aclose()

    app = FastAPI(title="FormLaw Review Agent", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.llm_provider = llm_provider
    app.state.prompts = PromptLibrary(settings.prompts_dir)  # fail fast on missing prompts

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    register_error_handlers(app)
    app.include_router(reviews_router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
