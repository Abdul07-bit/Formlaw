"""Application configuration, loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class Settings(BaseSettings):
    """Runtime settings. Nothing secret has a default value."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    max_document_chars: int = Field(default=200_000, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)

    prompts_dir: Path = DEFAULT_PROMPTS_DIR

    @property
    def llm_configured(self) -> bool:
        key = self.llm_api_key.get_secret_value() if self.llm_api_key else ""
        return bool(key and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings for the FastAPI app. Tests build Settings directly."""
    return Settings()
