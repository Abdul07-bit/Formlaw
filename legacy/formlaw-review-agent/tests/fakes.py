"""Deterministic LLM test doubles. No network, no API key."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

Scripted = BaseModel | Exception | Callable[[], Awaitable[BaseModel]]


class ScriptedLLMProvider:
    """Returns/raises scripted items in order; the final item repeats forever."""

    def __init__(self, *script: Scripted) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel], model: str
    ) -> BaseModel:
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt, "schema": schema, "model": model}
        )
        item = self._script.pop(0) if len(self._script) > 1 else self._script[0]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, BaseModel):
            return item
        return await item()


class HangingLLMProvider:
    """Never answers within any sane timeout."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, **_: Any) -> BaseModel:
        self.calls += 1
        await asyncio.sleep(30)
        raise AssertionError("unreachable")
