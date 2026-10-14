"""Provider-agnostic LLM interface. Agents depend on this, never on a vendor SDK."""

from typing import Protocol

from pydantic import BaseModel


class LLMProvider(Protocol):
    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        model: str,
    ) -> BaseModel:
        """Return an instance of `schema`.

        Implementations must raise:
          - LLMFailureError for transport/provider failures (set `retryable`),
          - StructuredOutputError if the model's output does not validate.
        """
        ...
