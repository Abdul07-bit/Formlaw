import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.errors import LLMFailureError
from app.main import create_app
from tests.fakes import ScriptedLLMProvider
from tests.fixtures import ARJUN_DOC, arrest_analysis

URL = "/api/v1/reviews"


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "request": "When was Arjun Kumar arrested?",
        "workflow_type": "case_review",
        "document_text": ARJUN_DOC,
        "document_name": "case_001.pdf",
    }
    body.update(overrides)
    return body


async def test_review_endpoint_returns_structured_result(settings: Settings) -> None:
    provider = ScriptedLLMProvider(arrest_analysis())
    async with _client(create_app(settings, provider)) as client:
        resp = await client.post(URL, json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "COMPLETED" and body["workflow_type"] == "case_review"
    assert body["review_id"] == body["result"]["review_id"]
    result = body["result"]
    assert len(result["contradictions"]) == 1
    assert {"facts", "issues", "missing_information", "claims", "evidence"} <= result.keys()
    assert "X-Request-ID" in resp.headers


@pytest.mark.parametrize(
    "overrides",
    [
        {"request": ""},
        {"request": "   "},
        {"document_text": ""},
        {"document_text": "   "},
        {"workflow_type": "legal_research"},
        {"unexpected_field": 1},
    ],
)
async def test_invalid_input_is_rejected_with_structured_error(
    settings: Settings, overrides: dict[str, object]
) -> None:
    provider = ScriptedLLMProvider(arrest_analysis())
    async with _client(create_app(settings, provider)) as client:
        resp = await client.post(URL, json=_payload(**overrides))
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "INVALID_INPUT" and err["request_id"]
    assert provider.calls == []


async def test_validation_error_does_not_echo_document(settings: Settings) -> None:
    marker = "ECHO-MARKER-7731"
    async with _client(create_app(settings, ScriptedLLMProvider(arrest_analysis()))) as client:
        resp = await client.post(URL, json=_payload(request="  ", document_text=marker))
    assert resp.status_code == 422
    assert marker not in resp.text


async def test_oversized_document_returns_413(settings: Settings) -> None:
    provider = ScriptedLLMProvider(arrest_analysis())
    async with _client(create_app(settings, provider)) as client:
        resp = await client.post(URL, json=_payload(document_text="A" * 6000))
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "DOCUMENT_TOO_LARGE"
    assert provider.calls == []


async def test_llm_not_configured_returns_503() -> None:
    unconfigured = Settings(_env_file=None, llm_api_key=None, llm_model="")  # type: ignore[call-arg]
    async with _client(create_app(unconfigured)) as client:
        resp = await client.post(URL, json=_payload())
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "LLM_NOT_CONFIGURED"


async def test_persistent_llm_failure_returns_502_without_internals(settings: Settings) -> None:
    provider = ScriptedLLMProvider(LLMFailureError("secret upstream detail", retryable=True))
    async with _client(create_app(settings, provider)) as client:
        resp = await client.post(URL, json=_payload())
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "RETRY_EXHAUSTED"
    assert "Traceback" not in resp.text and "ScriptedLLMProvider" not in resp.text


async def test_health(settings: Settings) -> None:
    async with _client(create_app(settings, ScriptedLLMProvider(arrest_analysis()))) as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
