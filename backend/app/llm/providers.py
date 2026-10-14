"""
Model-provider abstraction. Agents depend on `LLMRouter` / `LLMProvider`, never on a vendor SDK, so models are
replaced by configuration. Providers: Gemini, OpenAI, Anthropic (Claude). Keys live only in backend env.

When no provider is configured, `get_router()` returns None and every agent uses its deterministic path —
FormLaw never depends on a model for correctness, only for quality.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..core.config import get_settings

log = logging.getLogger("formlaw.llm")
M = TypeVar("M", bound=BaseModel)
Tier = Literal["fast", "strong"]

# Task → tier. Cheap, high-volume decisions go to the fast tier; anything that reasons over evidence goes to strong.
TASK_TIERS: dict[str, Tier] = {
    "classify": "fast", "intake": "fast",
    "plan": "strong", "extract": "strong", "compose": "strong", "draft": "strong", "judge": "strong",
    "contradiction": "strong", "contract": "strong",
}


class LLMError(Exception):
    """Transient or provider-side failure (retryable / fall through to the next provider)."""


class LLMOutputError(Exception):
    """Model output failed schema validation or was refused. Never trusted; not retried blindly."""


class LLMProvider(Protocol):
    name: str
    default_models: dict[str, str]

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: type[M], model: str | None = None) -> tuple[M, int]:
        """Returns (validated object, tokens used)."""
        ...


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dim: int

    def embed(self, texts: list[str], *, task: str = "document") -> list[list[float]]:
        """task: 'document' (indexing) or 'query' (search)."""
        ...


def _parse(schema: type[M], raw: str) -> M:
    try:
        return schema.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        raise LLMOutputError(f"Model output failed schema validation: {type(e).__name__}") from e


def _schema_hint(schema: type[BaseModel]) -> str:
    """For providers without native schema enforcement, the JSON Schema is appended to the system prompt."""
    return "\n\nRespond with a single JSON object that validates against this JSON Schema:\n" + json.dumps(schema.model_json_schema())


GEMINI_COOLDOWN_SECONDS = 300
_gemini_cooldown: dict[str, float] = {}  # model → monotonic time until which it is tried last (process-wide)
_last_model = threading.local()  # label of the model that actually answered the latest call on this thread


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float = 60):
        # GEMINI_MODEL may list fallbacks: "gemini-flash-latest,gemini-3.5-flash" — tried in order on 429/5xx.
        self._key, self._timeout = api_key, timeout
        self.models = [m.strip() for m in model.split(",") if m.strip()]
        self.default_models = {"fast": self.models[-1], "strong": self.models[0]}

    def generate_structured(self, *, system_prompt, user_prompt, schema, model=None):
        # The requested model first, then the rest of the configured chain: a quota-exhausted (429) primary must not
        # disable every model-backed step while the fallbacks are still available. Models that were just rate limited
        # are tried last, so a run does not spend a round trip per call on a model that is known to be out of quota.
        order = ([model] if model else []) + [m for m in self.models if m != model]
        now = time.monotonic()
        order = [m for m in order if _gemini_cooldown.get(m, 0) <= now] + [m for m in order if _gemini_cooldown.get(m, 0) > now]
        last: LLMError | None = None
        for m in order:
            try:
                out = self._generate(m, system_prompt, user_prompt, schema)
                _gemini_cooldown.pop(m, None)
                _last_model.name = f"{self.name}:{m}"
                return out
            except LLMError as e:
                if "(429)" in str(e):
                    _gemini_cooldown[m] = time.monotonic() + GEMINI_COOLDOWN_SECONDS
                log.warning("gemini model %s unavailable (%s); trying next", m, e)
                last = e
        raise last or LLMError("No Gemini model configured")

    def _generate(self, model, system_prompt, user_prompt, schema):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt + _schema_hint(schema)}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        try:
            r = httpx.post(url, json=body, headers={"x-goog-api-key": self._key}, timeout=self._timeout)
        except httpx.HTTPError as e:
            raise LLMError(f"Gemini request failed: {type(e).__name__}") from e
        if r.status_code >= 500 or r.status_code == 429:
            raise LLMError(f"Gemini unavailable ({r.status_code})")
        if r.status_code >= 400:
            raise LLMOutputError(f"Gemini rejected the request ({r.status_code})")
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise LLMOutputError("Gemini returned no content") from e
        tokens = int(data.get("usageMetadata", {}).get("totalTokenCount", 0))
        return _parse(schema, text), tokens


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: float = 60):
        self._key, self._timeout = api_key, timeout
        self.default_models = {"fast": model, "strong": model}

    def generate_structured(self, *, system_prompt, user_prompt, schema, model=None):
        body = {
            "model": model or self.default_models["strong"], "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system_prompt + _schema_hint(schema)}, {"role": "user", "content": user_prompt}],
        }
        try:
            r = httpx.post("https://api.openai.com/v1/chat/completions", json=body,
                           headers={"authorization": f"Bearer {self._key}"}, timeout=self._timeout)
        except httpx.HTTPError as e:
            raise LLMError(f"OpenAI request failed: {type(e).__name__}") from e
        if r.status_code >= 500 or r.status_code == 429:
            raise LLMError(f"OpenAI unavailable ({r.status_code})")
        if r.status_code >= 400:
            raise LLMOutputError(f"OpenAI rejected the request ({r.status_code})")
        data = r.json()
        tokens = int(data.get("usage", {}).get("total_tokens", 0))
        return _parse(schema, data["choices"][0]["message"]["content"]), tokens


class AnthropicProvider:
    """
    Claude via the official `anthropic` SDK (optional dependency, imported only when configured).
    Structured output uses `messages.parse(output_format=<Pydantic model>)`, which constrains and validates the
    response. A refusal is surfaced as LLMOutputError so FormLaw's own chain (next provider → deterministic path) applies.
    """
    name = "anthropic"
    default_models = {"fast": "claude-haiku-5-5", "strong": "claude-opus-5-5"}

    def __init__(self, api_key: str, timeout: float = 120):
        try:
            import anthropic  # noqa: PLC0415 — optional dependency
        except ImportError as e:
            raise RuntimeError("LLM_PROVIDER=anthropic requires `pip install anthropic`") from e
        self._sdk = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    def generate_structured(self, *, system_prompt, user_prompt, schema, model=None):
        a = self._sdk
        try:
            response = self._client.messages.parse(
                model=model or self.default_models["strong"], max_tokens=16000, system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}], output_format=schema,
            )
        except (a.RateLimitError, a.APIConnectionError) as e:
            raise LLMError(f"Claude unavailable ({type(e).__name__})") from e
        except a.APIStatusError as e:
            if e.status_code >= 500:
                raise LLMError(f"Claude unavailable ({e.status_code})") from e
            raise LLMOutputError(f"Claude rejected the request ({e.status_code})") from e
        if response.stop_reason == "refusal":
            raise LLMOutputError("Claude declined the request")
        if response.parsed_output is None:
            raise LLMOutputError("Claude returned no structured output")
        usage = response.usage
        return response.parsed_output, int(usage.input_tokens + usage.output_tokens)


class GeminiEmbeddings:
    name, dim = "gemini", 768
    BATCH = 100

    def __init__(self, api_key: str, model: str = "gemini-embedding-001", timeout: float = 60):
        self._key, self.model, self._timeout = api_key, model, timeout

    def embed(self, texts, *, task="document"):
        out: list[list[float]] = []
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        for i in range(0, len(texts), self.BATCH):
            batch = texts[i:i + self.BATCH]
            body = {"requests": [{"model": f"models/{self.model}", "content": {"parts": [{"text": t[:8000]}]},
                                  "taskType": task_type, "outputDimensionality": self.dim} for t in batch]}
            try:
                r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents",
                               json=body, headers={"x-goog-api-key": self._key}, timeout=self._timeout)
            except httpx.HTTPError as e:
                raise LLMError(f"Gemini embedding request failed: {type(e).__name__}") from e
            if r.status_code >= 500 or r.status_code == 429:
                raise LLMError(f"Gemini embeddings unavailable ({r.status_code})")
            if r.status_code >= 400:
                raise LLMOutputError(f"Gemini rejected the embedding request ({r.status_code})")
            vecs = [e["values"] for e in r.json().get("embeddings", [])]
            if len(vecs) != len(batch) or any(len(v) != self.dim for v in vecs):
                raise LLMOutputError("Gemini returned malformed embeddings")
            out.extend(vecs)
        return out


@dataclass
class ScriptedProvider:
    """
    Deterministic test double. `responses` maps a schema class name to a list of outputs (dict, BaseModel,
    callable(user_prompt) -> dict, or Exception to raise), consumed in order. Every call is recorded.
    """
    responses: dict[str, list[Any]] = field(default_factory=dict)
    name: str = "scripted"
    default_models: dict[str, str] = field(default_factory=lambda: {"fast": "scripted-fast", "strong": "scripted-strong"})
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate_structured(self, *, system_prompt, user_prompt, schema, model=None):
        self.calls.append({"schema": schema.__name__, "system": system_prompt, "user": user_prompt, "model": model})
        queue = self.responses.get(schema.__name__)
        if not queue:
            raise LLMError(f"No scripted response for {schema.__name__}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        if callable(item) and not isinstance(item, BaseModel):
            item = item(user_prompt)
        data = item.model_dump() if isinstance(item, BaseModel) else item
        return _parse(schema, json.dumps(data)), 100


@dataclass(frozen=True)
class Route:
    provider: LLMProvider
    model: str | None
    tier: Tier

    @property
    def label(self) -> str:
        return f"{self.provider.name}:{self.model or 'default'}"


class LLMRouter:
    """Routes a task to (provider, model) and falls through the provider chain on transient errors."""

    def __init__(self, chain: list[LLMProvider], overrides: dict[str, str] | None = None):
        self.chain = chain
        self.overrides = {k: v for k, v in (overrides or {}).items() if v}

    @property
    def name(self) -> str:
        return "+".join(p.name for p in self.chain)

    def route(self, task: str) -> Route:
        tier = TASK_TIERS.get(task, "strong")
        primary = self.chain[0]
        return Route(primary, self.overrides.get(tier) or getattr(primary, "default_models", {}).get(tier), tier)

    def generate(self, task: str, *, system_prompt: str, user_prompt: str, schema: type[M]) -> tuple[M, int, str]:
        """Returns (validated object, tokens, model label). Raises the last error if every provider fails."""
        tier = TASK_TIERS.get(task, "strong")
        last: Exception | None = None
        for i, p in enumerate(self.chain):
            model = (self.overrides.get(tier) if i == 0 else None) or getattr(p, "default_models", {}).get(tier)
            try:
                _last_model.name = None
                obj, tokens = p.generate_structured(system_prompt=system_prompt, user_prompt=user_prompt, schema=schema, model=model)
                return obj, tokens, _last_model.name or f"{p.name}:{model}"
            except LLMError as e:
                log.warning("provider %s failed for task %s (%s); trying next", p.name, task, e)
                last = e
        assert last is not None
        raise last


_router_override: LLMRouter | None = None
_override_set = False
_embed_override: EmbeddingProvider | None = None
_embed_override_set = False


def set_provider(p: LLMProvider | None) -> None:
    """Test hook / dependency injection. None restores configuration-based selection."""
    global _router_override, _override_set
    _router_override = LLMRouter([p]) if p else None
    _override_set = p is not None


def disable_llm() -> None:
    """Force deterministic mode regardless of configuration (tests)."""
    global _router_override, _override_set
    _router_override, _override_set = None, True


def set_embedder(p: EmbeddingProvider | None) -> None:
    global _embed_override, _embed_override_set
    _embed_override, _embed_override_set = p, p is not None


def disable_embeddings() -> None:
    global _embed_override, _embed_override_set
    _embed_override, _embed_override_set = None, True


def get_embedder() -> EmbeddingProvider | None:
    if _embed_override_set:
        return _embed_override
    s = get_settings()
    if s.gemini_api_key and s.llm_provider != "none":
        return GeminiEmbeddings(s.gemini_api_key, s.models.embedding or "gemini-embedding-001")
    return None


def get_router() -> LLMRouter | None:
    if _override_set:
        return _router_override
    s = get_settings()
    available: dict[str, Callable[[], LLMProvider]] = {}
    if s.gemini_api_key:
        available["gemini"] = lambda: GeminiProvider(s.gemini_api_key, s.gemini_model)  # type: ignore[arg-type]
    if s.openai_api_key:
        available["openai"] = lambda: OpenAIProvider(s.openai_api_key, s.openai_model)  # type: ignore[arg-type]
    if s.anthropic_api_key:
        available["anthropic"] = lambda: AnthropicProvider(s.anthropic_api_key)  # type: ignore[arg-type]
    if s.llm_provider not in available:
        return None
    order = [s.llm_provider] + [k for k in available if k != s.llm_provider]
    chain: list[LLMProvider] = []
    for k in order:
        try:
            chain.append(available[k]())
        except RuntimeError as e:  # e.g. SDK not installed
            log.warning("LLM provider %s unavailable: %s", k, e)
    if not chain:
        return None
    return LLMRouter(chain, {"fast": s.models.fast, "strong": s.models.strong})
