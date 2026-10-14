"""
Settings, read from environment variables (and a project-root .env file if present).
Secrets never have production defaults: the app refuses to start in production without them.
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
log = logging.getLogger("formlaw.config")


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE lines). Real environment variables always win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _int(name: str, default: int) -> int:
    return int(_env(name, str(default)))  # type: ignore[arg-type]


def _bool(name: str, default: bool) -> bool:
    return (_env(name, str(default)) or "").lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class AgentLimits:
    max_agent_steps: int = 40
    max_retries: int = 2
    max_tool_calls: int = 80
    max_execution_seconds: float = 120.0
    max_token_budget: int = 200_000
    max_replans: int = 3


@dataclass(frozen=True)
class ModelRouting:
    """Which model serves which kind of task. Empty = provider default for that tier."""
    fast: str = ""      # classification, intake structuring
    strong: str = ""    # planning, extraction, composition, drafting, judging
    embedding: str = ""


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    jwt_secret: str
    access_token_minutes: int
    refresh_token_days: int
    demo_mode: bool
    storage_dir: Path
    file_encryption_key: str | None
    llm_provider: str
    gemini_api_key: str | None
    gemini_model: str
    openai_api_key: str | None
    openai_model: str
    anthropic_api_key: str | None
    vector_database_url: str | None
    kyc_provider: str
    kyc_provider_key: str | None
    cors_origins: list[str]
    cookie_secure: bool
    max_upload_bytes: int = 15 * 1024 * 1024
    limits: AgentLimits = field(default_factory=AgentLimits)
    models: ModelRouting = field(default_factory=ModelRouting)
    run_inline: bool = False  # execute agent runs in the request thread (tests); otherwise a worker pool
    # The public assistant on the landing page is unauthenticated: it answers with verbatim corpus passages unless this is
    # explicitly enabled, so anonymous visitors cannot run up model costs.
    public_assistant_model: bool = False

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(ROOT_DIR / ".env")
    env = _env("FORMLAW_ENV", "development")
    jwt_secret = _env("JWT_SECRET")
    if not jwt_secret:
        if env == "production":
            raise RuntimeError("JWT_SECRET must be set in production")
        jwt_secret = secrets.token_urlsafe(48)
        log.warning("JWT_SECRET not set - using a random per-process secret (sessions reset on restart).")
    if env == "production" and _bool("DEMO_MODE", False):
        raise RuntimeError("DEMO_MODE must be off in production")

    return Settings(
        env=env,
        database_url=_env("DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'formlaw.db').as_posix()}"),  # type: ignore[arg-type]
        jwt_secret=jwt_secret,
        access_token_minutes=_int("ACCESS_TOKEN_MINUTES", 15),
        refresh_token_days=_int("REFRESH_TOKEN_DAYS", 14),
        demo_mode=_bool("DEMO_MODE", env != "production"),
        storage_dir=Path(_env("STORAGE_DIR", str(BACKEND_DIR / "storage"))),  # type: ignore[arg-type]
        file_encryption_key=_env("FILE_ENCRYPTION_KEY"),
        llm_provider=(_env("LLM_PROVIDER", "none") or "none").lower(),
        gemini_api_key=_env("GEMINI_API_KEY"),
        gemini_model=_env("GEMINI_MODEL", "gemini-flash-latest,gemini-3.5-flash,gemini-3.1-flash-lite"),  # type: ignore[arg-type]
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_model=_env("OPENAI_MODEL", "gpt-4o"),  # type: ignore[arg-type]
        anthropic_api_key=_env("ANTHROPIC_API_KEY"),
        vector_database_url=_env("VECTOR_DATABASE_URL"),
        kyc_provider=(_env("KYC_PROVIDER", "demo") or "demo").lower(),
        kyc_provider_key=_env("KYC_PROVIDER_KEY"),
        cors_origins=[o.strip() for o in (_env("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174") or "").split(",") if o.strip()],
        cookie_secure=_bool("COOKIE_SECURE", env == "production"),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 15 * 1024 * 1024),
        limits=AgentLimits(
            max_agent_steps=_int("MAX_AGENT_STEPS", 40),
            max_retries=_int("MAX_RETRIES", 2),
            max_tool_calls=_int("MAX_TOOL_CALLS", 80),
            max_execution_seconds=float(_env("MAX_EXECUTION_SECONDS", "120")),  # type: ignore[arg-type]
            max_token_budget=_int("MAX_TOKEN_BUDGET", 200_000),
            max_replans=_int("MAX_REPLANS", 3),
        ),
        models=ModelRouting(fast=_env("LLM_MODEL_FAST", "") or "", strong=_env("LLM_MODEL_STRONG", "") or "",
                            embedding=_env("EMBEDDING_MODEL", "") or ""),
        run_inline=_bool("RUN_AGENTS_INLINE", env == "test"),
        public_assistant_model=_bool("PUBLIC_ASSISTANT_MODEL", False),
    )
