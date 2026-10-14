"""
Agent runs: create → execute (worker pool, or inline in tests) → stream events → persist.

Persistence happens only after the run's verification gate: case knowledge (claims, evidence, contradictions,
missing information, timeline, authorities, drafts), the assistant message, tool calls, memory and audit.
"""
from __future__ import annotations

import logging
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.runtime import events as ev
from ..agents.runtime.engine import Orchestrator, RunState
from ..agents.runtime.tools import build_tools
from ..core.config import get_settings
from ..db.base import utcnow
from ..db.session import session_factory
from ..domain.enums import Intent, RunStatus
from ..llm.providers import get_router
from ..memory import service as memory
from ..models import AgentRun, AgentStep, Case, ChatMessage, ChatThread, ToolCall
from ..repositories.access import CaseAccess
from ..security import rate_limit
from . import audit
from .knowledge import Writer

log = logging.getLogger("formlaw.runs")
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="formlaw-run")
_lock = threading.Lock()


def new_task_id() -> str:
    return "T-" + secrets.token_hex(5).upper()


def start(db: Session, access: CaseAccess, principal, message: str, *, thread_id: str | None = None,
          intent: Intent | None = None, params: dict[str, Any] | None = None) -> AgentRun:
    rate_limit.hit("agent", principal.id)
    org, case_id = access.scope
    if thread_id:
        thread = db.get(ChatThread, thread_id)
        if thread is None or thread.case_id != case_id:
            from ..core.errors import NotFound
            raise NotFound("Conversation not found")
    else:
        thread = ChatThread(case_id=case_id, organization_id=org, created_by=principal.id, title=message.strip()[:80] or "New conversation")
        db.add(thread)
        db.flush()
    thread.updated_at = utcnow()
    run = AgentRun(task_id=new_task_id(), case_id=case_id, organization_id=org, user_id=principal.id, thread_id=thread.id,
                   goal=message.strip(), intent=intent.value if intent else None, status=RunStatus.QUEUED,
                   result={"_params": params or {}} if params else None)
    db.add(run)
    db.flush()
    db.add(ChatMessage(thread_id=thread.id, case_id=case_id, role="user", author_id=principal.id, content=message.strip(), run_id=run.id))
    audit.record(db, action="agent.run", result="pending", actor=principal, resource_type="case", resource_id=case_id,
                 organization_id=org, case_id=case_id, task_id=run.task_id, detail=(intent.value if intent else "chat"))
    ev.open_channel(run.id)
    db.commit()  # the worker reads the run in its own session
    if get_settings().run_inline:
        execute(run.id)
    else:
        _pool.submit(execute, run.id)
    return run


def execute(run_id: str) -> None:
    db = session_factory()()
    try:
        _execute(db, run_id)
    except Exception:
        log.exception("run %s crashed", run_id)
        db.rollback()
        run = db.get(AgentRun, run_id)
        if run:
            _fail(db, run, "Internal error — the run was stopped safely",
                  "FormLaw could not complete this request because of an internal error. Nothing was changed. Please ask again.")
        ch = ev.get_channel(run_id)
        if ch:
            ch.publish(ev.Event(len(ch.events), 0, ev.EventType.RUN_FAILED, "Orchestrator", None, "The run failed and was stopped safely"))
    finally:
        db.close()


def _fail(db: Session, run: AgentRun, error: str, message: str) -> None:
    """Mark a run failed and leave an assistant message, so the conversation never ends on an unanswered question."""
    run.status, run.error, run.finished_at = RunStatus.FAILED, error, utcnow()
    db.add(ChatMessage(thread_id=run.thread_id, case_id=run.case_id, role="assistant", content=message, run_id=run.id, result=None))
    db.commit()


def fail_interrupted() -> int:
    """
    At startup: runs execute in this process's worker pool, so any run still queued or running was interrupted by a
    restart (e.g. `uvicorn --reload`). Left alone, its conversation would wait forever for an answer.
    """
    with session_factory()() as db:
        stale = db.scalars(select(AgentRun).where(AgentRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]))).all()
        for run in stale:
            _fail(db, run, "Interrupted by a server restart",
                  "This request was interrupted because the FormLaw server restarted. Please ask again.")
        return len(stale)


def _execute(db: Session, run_id: str) -> None:
    run = db.get(AgentRun, run_id)
    case = db.get(Case, run.case_id)
    s = get_settings()
    router = get_router()
    run.status = RunStatus.RUNNING
    db.commit()
    channel = ev.get_channel(run_id) or ev.open_channel(run_id)
    params = (run.result or {}).get("_params", {})
    st = RunState(run_id=run.id, task_id=run.task_id, organization_id=case.organization_id, case_id=case.id, user_id=run.user_id,
                  case_title=case.title, matter_type=case.matter_type, goal=run.goal, limits=s.limits, llm_enabled=router is not None,
                  forced_intent=Intent(run.intent) if run.intent else None, forced_params=params)
    st.board.memory = memory.read(db, case.organization_id, case.id)
    steps: list[AgentStep] = []

    def emit(type_: str, *, agent: str | None = None, step_id: str | None = None, summary: str = "", data: dict | None = None) -> None:
        e = ev.Event(len(channel.events), st.budget.elapsed_ms, str(type_), agent, step_id, summary[:400], data or {})
        steps.append(AgentStep(run_id=run.id, seq=e.seq, t_ms=e.t_ms, type=e.type, agent=agent, step_id=step_id, summary=e.summary, data=e.data))
        if e.type not in (ev.EventType.RUN_COMPLETED, ev.EventType.RUN_FAILED):
            channel.publish(e)
        else:
            _final_event[0] = e

    _final_event: list[ev.Event | None] = [None]
    tools = build_tools(db, organization_id=case.organization_id, case_id=case.id, router=router, prompt_refs=st.prompt_refs)
    orch = Orchestrator(tools, emit)
    result = orch.run(st)

    # ---------------------------------------------------------------- persist
    w = Writer(db, case.organization_id, case.id, run.id, result)
    counts = w.write_all()
    draft_id = w.draft(run.user_id)
    if draft_id:
        result["draft"]["id"] = draft_id
    result["persisted"] = counts
    db.add_all(steps)
    for c in orch.gateway.calls:
        db.add(ToolCall(run_id=run.id, step_id=c.step_id, agent=c.agent, tool=c.tool, risk=str(c.risk), status=c.status,
                        latency_ms=c.latency_ms, tokens=c.tokens, model=c.model, error=c.error))
    run.status, run.result, run.plan = st.status, result, result["plan"]
    run.intent, run.steps, run.tool_calls, run.replans, run.tokens = st.intent.value, st.budget.steps, st.budget.tool_calls, st.budget.replans, st.budget.tokens
    run.latency_ms, run.finished_at = st.budget.elapsed_ms, utcnow()
    run.engine = ",".join(sorted(st.engines))[:60] or "deterministic"
    db.add(ChatMessage(thread_id=run.thread_id, case_id=case.id, role="assistant", content=result["answer"]["summary"][:4000],
                       run_id=run.id, result=result))
    for sitem in result["security"]:
        if sitem["action"] == "request_refused":
            audit.security_event(db, kind=sitem["kind"], source="chat request", snippet=sitem["snippet"],
                                 actions=["Request refused", "No tool was called", "Security event logged"], risk="MEDIUM",
                                 organization_id=case.organization_id, case_id=case.id, run_id=run.id, actor_id=run.user_id)
    if st.status != RunStatus.REFUSED:
        memory.remember_run(db, organization_id=case.organization_id, case_id=case.id, run_id=run.id, result=result)
    audit.record(db, action="agent.run", result="blocked" if st.status == RunStatus.REFUSED else "success", resource_type="case",
                 resource_id=case.id, organization_id=case.organization_id, case_id=case.id, task_id=run.task_id,
                 agent="Orchestrator", latency_ms=run.latency_ms, risk="MEDIUM" if st.status == RunStatus.REFUSED else "LOW",
                 verification_status=f"{len(result['claims']) - len(result['unverified'])} verified / {len(result['unverified'])} unverified")
    db.commit()
    if _final_event[0] is not None:
        channel.publish(_final_event[0])  # only after everything is committed, so clients can fetch the final run


def get_run(db: Session, run_id: str) -> AgentRun | None:
    return db.get(AgentRun, run_id)


def stored_events(db: Session, run_id: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.seq)).all()
    return [{"seq": r.seq, "tMs": r.t_ms, "type": r.type, "agent": r.agent, "stepId": r.step_id, "summary": r.summary, "data": r.data} for r in rows]
