"""Conversation threads and agent-run observability (runs → steps → tool calls)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, IdMixin, JsonType, TimestampMixin
from ..domain.enums import Risk, RunStatus, check_in


class ChatThread(IdMixin, TimestampMixin, Base):
    __tablename__ = "chat_threads"

    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (CheckConstraint("role IN ('user','assistant')", name="ck_message_role"),)

    thread_id: Mapped[str] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    author_id: Mapped[str | None] = mapped_column(String(36))
    content: Mapped[str] = mapped_column(Text, default="")  # user text, or the assistant's summary line
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    result: Mapped[dict | None] = mapped_column(JsonType)  # structured run result for assistant messages


class AgentRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (CheckConstraint(check_in("status", RunStatus), name="ck_run_status"),)

    task_id: Mapped[str] = mapped_column(String(24), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    thread_id: Mapped[str | None] = mapped_column(String(36))
    goal: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default=RunStatus.QUEUED)
    plan: Mapped[list] = mapped_column(JsonType, default=list)
    result: Mapped[dict | None] = mapped_column(JsonType)
    engine: Mapped[str] = mapped_column(String(60), default="deterministic")  # model(s) used, or deterministic
    steps: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    replans: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(300))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentStep(IdMixin, Base):
    """One observable event of a run. `summary` is a short reasoning summary, never chain-of-thought."""
    __tablename__ = "agent_steps"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    t_ms: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(24))  # see agents.runtime.events.EventType
    agent: Mapped[str | None] = mapped_column(String(40))
    step_id: Mapped[str | None] = mapped_column(String(12))
    summary: Mapped[str] = mapped_column(String(400), default="")
    data: Mapped[dict] = mapped_column(JsonType, default=dict)


class ToolCall(IdMixin, TimestampMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (CheckConstraint(check_in("risk", Risk), name="ck_tool_risk"),)

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(String(12))
    agent: Mapped[str] = mapped_column(String(40))
    tool: Mapped[str] = mapped_column(String(40))
    risk: Mapped[str] = mapped_column(String(6), default=Risk.LOW)
    status: Mapped[str] = mapped_column(String(10))  # ok | retry | error | denied
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(String(200))
