"""
Run events. Each run has an in-process channel that SSE subscribers tail while the run executes; every event is also
persisted as an `agent_steps` row so finished runs replay identically.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    RUN_STARTED = "run.started"
    INTENT = "intent"
    PLAN = "plan"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    ADAPT = "adapt"
    REPLAN = "replan"
    SECURITY = "security"
    VERIFICATION = "verification"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


TERMINAL = {EventType.RUN_COMPLETED, EventType.RUN_FAILED}


@dataclass
class Event:
    seq: int
    t_ms: int
    type: str
    agent: str | None = None
    step_id: str | None = None
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def wire(self) -> dict[str, Any]:
        return {"seq": self.seq, "tMs": self.t_ms, "type": self.type, "agent": self.agent, "stepId": self.step_id,
                "summary": self.summary, "data": self.data}


class Channel:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self.done = False
        self.cond = threading.Condition()
        self.created = time.monotonic()

    def publish(self, ev: Event) -> None:
        with self.cond:
            self.events.append(ev)
            if ev.type in TERMINAL:
                self.done = True
            self.cond.notify_all()

    def wait(self, after: int, timeout: float = 15.0) -> list[Event]:
        with self.cond:
            if len(self.events) <= after and not self.done:
                self.cond.wait(timeout)
            return self.events[after:]


_channels: dict[str, Channel] = {}
_lock = threading.Lock()


def open_channel(run_id: str) -> Channel:
    with _lock:
        # Drop channels of runs finished more than 10 minutes ago.
        for k in [k for k, c in _channels.items() if c.done and time.monotonic() - c.created > 600]:
            _channels.pop(k, None)
        ch = _channels[run_id] = Channel()
        return ch


def get_channel(run_id: str) -> Channel | None:
    with _lock:
        return _channels.get(run_id)
