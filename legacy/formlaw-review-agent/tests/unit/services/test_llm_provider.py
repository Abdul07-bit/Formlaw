import json

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.agents.review.schemas import ReviewAnalysis
from app.errors import LLMFailureError, LLMNotConfiguredError, StructuredOutputError
from app.services.llm.provider import OpenAICompatibleProvider, build_provider
from tests.fixtures import arrest_analysis

KEY = "sk-test-super-secret"


def _provider(handler: httpx.MockTransport | object) -> OpenAICompatibleProvider:
    transport = handler if isinstance(handler, httpx.MockTransport) else httpx.MockTransport(handler)  # type: ignore[arg-type]
    return OpenAICompatibleProvider(
        base_url="https://llm.test/v1/", api_key=SecretStr(KEY), timeout_seconds=5,
        client=httpx.AsyncClient(transport=transport),
    )  # fmt: skip


async def _call(provider: OpenAICompatibleProvider) -> object:
    return await provider.generate_structured(
        system_prompt="SYS", user_prompt="USR", schema=ReviewAnalysis, model="m1"
    )


async def test_success_parses_into_schema_and_sends_expected_request() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        content = arrest_analysis().model_dump_json()
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    result = await _call(_provider(handler))
    assert isinstance(result, ReviewAnalysis)
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "m1" and body["temperature"] == 0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize(("status", "retryable"), [(429, True), (503, True), (400, False), (401, False)])
async def test_http_errors_are_classified(status: int, retryable: bool) -> None:
    provider = _provider(lambda _r: httpx.Response(status, text="upstream body with details"))
    with pytest.raises(LLMFailureError) as exc:
        await _call(provider)
    assert exc.value.retryable is retryable
    assert "upstream body" not in exc.value.message and KEY not in exc.value.message


@pytest.mark.parametrize("error_cls", [httpx.ConnectError, httpx.ReadTimeout])
async def test_transport_errors_are_retryable(error_cls: type[httpx.TransportError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_cls("boom", request=request)

    with pytest.raises(LLMFailureError) as exc:
        await _call(_provider(handler))
    assert exc.value.retryable is True


async def test_invalid_model_json_raises_structured_output_error_without_content() -> None:
    bad = json.dumps({"summary": "SENSITIVE-TEXT", "confidence": 9})
    provider = _provider(lambda _r: httpx.Response(200, json={"choices": [{"message": {"content": bad}}]}))
    with pytest.raises(StructuredOutputError) as exc:
        await _call(provider)
    assert exc.value.details
    assert "SENSITIVE-TEXT" not in exc.value.message + " ".join(exc.value.details)


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}])
async def test_unexpected_response_shapes(payload: dict[str, object]) -> None:
    with pytest.raises(StructuredOutputError):
        await _call(_provider(lambda _r: httpx.Response(200, json=payload)))


def test_build_provider_requires_key_and_model() -> None:
    with pytest.raises(LLMNotConfiguredError):
        build_provider(Settings(_env_file=None, llm_api_key=None, llm_model="x"))  # type: ignore[call-arg]
    with pytest.raises(LLMNotConfiguredError):
        build_provider(Settings(_env_file=None, llm_api_key=SecretStr("k"), llm_model=""))  # type: ignore[call-arg]
    configured = Settings(_env_file=None, llm_api_key=SecretStr("k"), llm_model="m")  # type: ignore[call-arg]
    assert isinstance(build_provider(configured), OpenAICompatibleProvider)
