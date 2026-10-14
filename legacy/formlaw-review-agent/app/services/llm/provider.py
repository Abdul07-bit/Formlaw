"""OpenAI-compatible chat/completions provider (works with any compatible endpoint)."""

from typing import Any

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from app.config import Settings
from app.errors import (
    LLMFailureError,
    LLMNotConfiguredError,
    StructuredOutputError,
    summarize_validation_error,
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        model: str,
    ) -> BaseModel:
        payload: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": False,
                },
            },
        }
        response = await self._post(payload)
        content = self._extract_content(response)
        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            raise StructuredOutputError(
                "Model output failed schema validation.",
                details=summarize_validation_error(exc),
            ) from exc

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
            )
        except httpx.TimeoutException as exc:
            raise LLMFailureError("LLM provider request timed out.", retryable=True) from exc
        except httpx.TransportError as exc:
            raise LLMFailureError("LLM provider unreachable.", retryable=True) from exc

        status = response.status_code
        if status == 429 or status >= 500:
            raise LLMFailureError(
                f"LLM provider temporarily unavailable (status {status}).", retryable=True
            )
        if status >= 400:
            raise LLMFailureError(
                f"LLM provider rejected the request (status {status}).", retryable=False
            )
        return response

    @staticmethod
    def _extract_content(response: httpx.Response) -> str:
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise StructuredOutputError("Provider response had an unexpected shape.") from exc
        if not isinstance(content, str) or not content.strip():
            raise StructuredOutputError("Provider returned empty content.")
        return content


def build_provider(settings: Settings) -> OpenAICompatibleProvider:
    if not settings.llm_configured or settings.llm_api_key is None:
        raise LLMNotConfiguredError("LLM_API_KEY and LLM_MODEL must be configured.")
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )
