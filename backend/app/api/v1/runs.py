"""Chat and workflow runs, run results, live event stream (SSE) and conversation history."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...agents.registry import directory
from ...agents.runtime import events as ev
from ...core.errors import NotFound
from ...db.session import get_db, session_factory
from ...domain.enums import Intent, RunStatus
from ...models import AgentRun, ChatMessage, ChatThread
from ...repositories.access import get_case
from ...schemas.workspace import ChatIn, WorkflowIn
from ...security.deps import Principal, require_lawyer
from ...services import runs
from ...services.serializers import iso

router = APIRouter(tags=["agents"])


def _started(run: AgentRun) -> dict:
    return {"runId": run.id, "threadId": run.thread_id, "taskId": run.task_id, "status": run.status}


@router.post("/cases/{case_id}/chat", status_code=202)
def chat(case_id: str, body: ChatIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "agent.run")
    return _started(runs.start(db, a, p, body.message, thread_id=body.thread_id))


def _workflow(intent: Intent, default: str):
    def handler(case_id: str, body: WorkflowIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
        a = get_case(db, p, case_id, "agent.run")
        msg = body.instructions.strip() or default
        return _started(runs.start(db, a, p, msg, thread_id=body.thread_id, intent=intent,
                                   params={"draft_kind": body.draft_kind} if body.draft_kind else None))
    return handler


router.post("/cases/{case_id}/review", status_code=202)(_workflow(Intent.CASE_REVIEW, "Review this case and identify the biggest weaknesses."))
router.post("/cases/{case_id}/research", status_code=202)(_workflow(Intent.LEGAL_RESEARCH, "Research authorities relevant to the main legal issue."))
router.post("/cases/{case_id}/draft", status_code=202)(_workflow(Intent.DRAFT, "Draft a case summary for senior counsel."))


def _run(db: Session, p: Principal, run_id: str) -> AgentRun:
    r = db.get(AgentRun, run_id)
    if not r:
        raise NotFound("Run not found")
    get_case(db, p, r.case_id)
    return r


@router.get("/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    r = _run(db, p, run_id)
    result = r.result if r.result and "_params" not in r.result else None
    return {"id": r.id, "taskId": r.task_id, "caseId": r.case_id, "threadId": r.thread_id, "goal": r.goal, "intent": r.intent,
            "status": r.status, "error": r.error, "createdAt": iso(r.created_at), "finishedAt": iso(r.finished_at), "result": result}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, p: Principal = Depends(require_lawyer)):
    with session_factory()() as db:  # authorisation check, then release the session for the long-lived stream
        _run(db, p, run_id)

    async def stream():
        sent = 0
        ch = ev.get_channel(run_id)
        if ch is None:  # finished in another process or long ago: replay from the database
            with session_factory()() as db:
                stored = runs.stored_events(db, run_id)
                run = db.get(AgentRun, run_id)
                status, error = (run.status, run.error) if run else (RunStatus.FAILED, None)
            for e in stored:
                yield f"event: {e['type']}\ndata: {json.dumps(e)}\n\n"
            if not any(e["type"] in ev.TERMINAL for e in stored):
                # A crashed or interrupted run persisted no terminal event: always end the stream with one, so the
                # client stops waiting and shows the run's final message.
                t = ev.EventType.RUN_FAILED if status in (RunStatus.FAILED, RunStatus.QUEUED, RunStatus.RUNNING) else ev.EventType.RUN_COMPLETED
                e = ev.Event(len(stored), 0, t, "Orchestrator", None, error or "").wire()
                yield f"event: {e['type']}\ndata: {json.dumps(e)}\n\n"
            return
        while True:
            if await request.is_disconnected():
                return
            batch = await asyncio.to_thread(ch.wait, sent, 10.0)
            for e in batch:
                yield f"event: {e.type}\ndata: {json.dumps(e.wire())}\n\n"
            sent += len(batch)
            if ch.done and sent >= len(ch.events):
                return
            if not batch:
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"cache-control": "no-store", "x-accel-buffering": "no"})


@router.get("/cases/{case_id}/threads")
def threads(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    rows = db.scalars(select(ChatThread).where(ChatThread.case_id == case_id, ChatThread.organization_id == a.case.organization_id)
                      .order_by(ChatThread.updated_at.desc().nullslast(), ChatThread.created_at.desc())).all()
    return [{"id": t.id, "title": t.title, "createdAt": iso(t.created_at), "updatedAt": iso(t.updated_at)} for t in rows]


@router.get("/threads/{thread_id}/messages")
def messages(thread_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    t = db.get(ChatThread, thread_id)
    if not t:
        raise NotFound("Conversation not found")
    get_case(db, p, t.case_id)
    out = []
    for m in db.scalars(select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at)):
        run = db.get(AgentRun, m.run_id) if m.run_id else None
        out.append({"id": m.id, "role": m.role, "content": m.content, "runId": m.run_id, "result": m.result, "createdAt": iso(m.created_at),
                    "runStatus": run.status if run else None})
    return out


@router.get("/agents")
def agents(_: Principal = Depends(require_lawyer)):
    return directory()
