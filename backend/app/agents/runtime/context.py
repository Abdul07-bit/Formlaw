"""What an agent sees during a step: the run state (read/write blackboard) and its gateway-bound tools."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from ...llm.prompts import PromptPassage
from ...llm.providers import LLMOutputError
from ...retrieval.case_index import EvidenceHit
from .budget import BudgetExceeded
from .gateway import Gateway
from .tools import LLMUnavailable

log = logging.getLogger("formlaw.agents")

if TYPE_CHECKING:
    from ..base import AgentSpec
    from .engine import RunState

M = TypeVar("M", bound=BaseModel)


@dataclass
class PassageMap:
    """Short passage ids for prompts (P1, P2, …) ↔ chunk ids. Models only ever see the short ids."""
    by_pid: dict[str, EvidenceHit] = field(default_factory=dict)

    def prompt(self) -> list[PromptPassage]:
        return [PromptPassage(pid, h.label, h.text) for pid, h in self.by_pid.items()]

    def resolve(self, pid: str) -> EvidenceHit | None:
        return self.by_pid.get(pid.strip())


@dataclass
class AgentContext:
    state: RunState
    spec: AgentSpec
    gateway: Gateway
    step_id: str | None = None
    engines: list[str] = field(default_factory=list)

    @property
    def board(self):
        return self.state.board

    @property
    def llm_available(self) -> bool:
        return self.state.llm_enabled

    def tool(self, name: str, **kwargs: Any) -> Any:
        return self.gateway.call(agent=self.spec.name, allowed=self.spec.tools, step_id=self.step_id, tool=name, **kwargs)

    def passages(self, hits: list[EvidenceHit]) -> PassageMap:
        """Build prompt passages. Flagged (instruction-bearing) chunks never enter a prompt."""
        return PassageMap({f"P{i + 1}": h for i, h in enumerate(h for h in hits if not h.flagged)})

    def llm(self, task: str, prompt_id: str, schema: type[M], *, request: str, passages: PassageMap | None = None,
            context: dict[str, Any] | None = None) -> M | None:
        """Structured model call. Returns None when no model is available or output was invalid → deterministic path."""
        if not self.llm_available:
            return None
        try:
            out = self.tool("llm_structured", task=task, prompt_id=prompt_id, schema=schema, request=request,
                            passages=passages.prompt() if passages else [], context=context)
        except (LLMUnavailable, LLMOutputError) as e:
            log.warning("%s: model call %s failed (%s); using the deterministic path", self.spec.name, task, e)
            return None
        except BudgetExceeded:
            raise
        except Exception as e:  # provider down after retries, or a client bug: the agent falls back to its deterministic path
            self.state.note_failure(self.spec.name, f"llm_{type(e).__name__}")
            return None
        model = self.gateway.calls[-1].model if self.gateway.calls else None
        if model:
            self.engines.append(model)
        return out["obj"]
