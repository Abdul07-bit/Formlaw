"""Orchestrator runtime: budgets, gateway, observe→adapt rules, grounding of model output, failure recovery."""
from __future__ import annotations

import pytest

from app.agents.runtime.budget import Budget
from app.agents.runtime.engine import Orchestrator, RunState
from app.agents.runtime.gateway import Gateway, Tool, ToolDenied
from app.agents.runtime.tools import build_tools
from app.core.config import AgentLimits
from app.db.session import session_factory
from app.domain.enums import Risk
from app.llm.providers import ScriptedProvider, set_provider
from app.models import Case

ONE_DOC = ["ACTION TAKEN\nThe accused Arjun Kumar was arrested on 12 March 2026 at his residence in Malviya Nagar. "
           "A mobile phone was recovered from him."]


def _setup(api, pages=ONE_DOC, name="FIR.txt", matter="criminal"):
    s = api.register()
    case = api.case(s, "Runtime test", matter_type=matter)
    api.upload_text(s, case["id"], name, pages)
    return s, case


def run_direct(case_id: str, goal: str, limits: AgentLimits | None = None, router=None):
    events: list[tuple] = []
    with session_factory()() as db:
        c = db.get(Case, case_id)
        st = RunState(run_id="r-test", task_id="T-TEST", organization_id=c.organization_id, case_id=c.id, user_id=c.created_by,
                      case_title=c.title, matter_type=c.matter_type, goal=goal, limits=limits or AgentLimits(), llm_enabled=router is not None)
        tools = build_tools(db, organization_id=c.organization_id, case_id=c.id, router=router, prompt_refs=st.prompt_refs)
        result = Orchestrator(tools, lambda t, **kw: events.append((str(t), kw))).run(st)
    return result, events


def test_step_budget_stops_safely(api):
    _, case = _setup(api)
    result, events = run_direct(case["id"], "Review this case", AgentLimits(max_agent_steps=3))
    assert result["status"] == "partial" and "MAX_AGENT_STEPS" in result["stopReason"]
    assert any(st["status"] == "skipped" for st in result["plan"])
    assert events[-1][0] == "run.completed"


def test_tool_call_budget_stops_safely(api):
    _, case = _setup(api)
    result, _ = run_direct(case["id"], "Review this case", AgentLimits(max_tool_calls=4))
    assert result["status"] == "partial" and "MAX_TOOL_CALLS" in result["stopReason"]


def test_gateway_default_deny_and_no_high_risk_tools():
    calls = []
    tools = {"case_search": Tool("case_search", lambda **k: calls.append(k), Risk.LOW, ""),
             "send_email": Tool("send_email", lambda **k: calls.append(k), Risk.HIGH, "")}
    g = Gateway(tools, Budget(AgentLimits()), max_retries=1)
    with pytest.raises(ToolDenied):
        g.call(agent="Drafting Agent", allowed=frozenset({"llm_structured"}), step_id=None, tool="case_search", query="x")
    with pytest.raises(ToolDenied):  # even if an allow-list were misconfigured, HIGH-risk tools never run inside an agent
        g.call(agent="Rogue", allowed=frozenset({"send_email"}), step_id=None, tool="send_email", to="x")
    assert not calls and {c.status for c in g.calls} == {"denied"}


def test_weak_retrieval_is_broadened(api):
    s, case = _setup(api)
    r = api.ask(s, case["id"], "Was the defendant apprehended?")["result"]  # vocabulary differs from the document
    broadened = [st for st in r["plan"] if st["action"] == "retrieval.search" and st["origin"] == "adapt"]
    assert broadened, r["plan"]
    assert r["evidence"], "synonym expansion (apprehended → arrested) should find the passage"


def test_research_reformulates_then_reports_absence(api):
    s, case = _setup(api)
    r = api.ask(s, case["id"], "Find authorities on anticipatory bail for economic offences")["result"]
    attempts = [st for st in r["plan"] if st["action"] == "research.search"]
    assert len(attempts) == 2 and attempts[1]["origin"] == "adapt"
    assert r["authorities"] == []
    assert any("No authority has been generated" in l for l in r["answer"]["limitations"])


def _script(**extra):
    base = {
        "IntentOut": [{"intent": "EVIDENCE_QA", "topic": "arrest"}],
        "PlanOut": [{"queries": ["arrested on"], "focus_topics": ["arrest"], "rationale": "Find the arrest record."}],
        "ContradictionsOut": [{"contradictions": []}],
        "JudgeOut": [{"verdicts": []}],
    }
    base.update(extra)
    return ScriptedProvider(responses=base)


def test_unverifiable_model_answer_triggers_replan_from_verified_evidence(api):
    s, case = _setup(api)
    fabricated = "The accused was arrested on 20 March 2026 by the Crime Branch."
    p = _script(ComposeOut=[{"summary": fabricated, "sentences": [
        {"text": fabricated, "passage_ids": ["P1"], "quote": "The accused Arjun Kumar was arrested on 12 March 2026"}]}])
    set_provider(p)
    r = api.ask(s, case["id"], "When was the accused arrested?")["result"]
    assert any(st["origin"] == "replan" and st["action"] == "answer.compose" for st in r["plan"]), r["plan"]
    shown = [c["text"] for c in r["claims"] if c["id"] in r["answer"]["claimIds"]]
    assert all("20 March" not in t for t in shown) and "20 March" not in r["answer"]["summary"]
    assert any("20 March" in c["text"] and c["status"] in ("UNSUPPORTED", "CONTRADICTED") for c in r["unverified"])
    assert r["stats"]["replans"] == 1


def test_judge_can_downgrade_but_never_upgrade(api):
    s, case = _setup(api)
    good = "The FIR records that Arjun Kumar was arrested on 12 March 2026."
    bad = "Arjun Kumar was arrested on 30 March 2026."
    p = _script(ComposeOut=[{"summary": good, "sentences": [
        {"text": good, "passage_ids": ["P1"], "quote": "The accused Arjun Kumar was arrested on 12 March 2026"},
        {"text": bad, "passage_ids": ["P1"], "quote": "The accused Arjun Kumar was arrested on 12 March 2026"}]}],
        JudgeOut=[lambda prompt: {"verdicts": [{"claim_id": cid, "verdict": "SUPPORTED", "reason": "looks fine"}
                                               for cid in __import__("re").findall(r'"claim_id": "(c\d+)"', prompt)]}])
    set_provider(p)
    r = api.ask(s, case["id"], "When was the accused arrested?")["result"]
    statuses = {c["text"]: c["status"] for c in r["claims"] + r["unverified"]}
    assert statuses[bad] in ("UNSUPPORTED", "CONTRADICTED")  # the judge's "SUPPORTED" did not upgrade it
    assert statuses[good] == "SUPPORTED"


def test_ungrounded_extraction_is_discarded(api):
    s, case = _setup(api)
    p = _script(IntentOut=[{"intent": "CASE_REVIEW"}], ComposeOut=[RuntimeError("force deterministic")],
                ExtractOut=[{"facts": [
                    {"text": "The FIR records the arrest of Arjun Kumar on 12 March 2026.", "kind": "fact", "passage_id": "P1",
                     "quote": "The accused Arjun Kumar was arrested on 12 March 2026 at his residence in Malviya Nagar."},
                    {"text": "The accused confessed to the theft.", "kind": "admission", "passage_id": "P1", "quote": "The accused confessed to the theft."},
                    {"text": "Section 420 IPC is attracted on these facts.", "kind": "fact", "passage_id": "P1",
                     "quote": "A mobile phone was recovered from him."},
                    {"text": "A phone was recovered.", "kind": "fact", "passage_id": "P99", "quote": "A mobile phone was recovered from him."}],
                    "events": [], "parties": [], "issues": []}])
    p.responses["ComposeOut"] = [ValueError("no compose")]  # compose falls back to deterministic
    set_provider(p)
    r = api.ask(s, case["id"], "Review this case")["result"]
    texts = " ".join(c["text"] for c in r["claims"] + r["unverified"])
    assert "confessed" not in texts and "420" not in texts
    assert "The FIR records the arrest of Arjun Kumar on 12 March 2026." in texts
    step = next(st for st in r["plan"] if st["action"] == "case_analysis.extract")
    assert "3 ungrounded discarded" in step["summary"]


def test_agent_crash_is_contained(api, monkeypatch):
    from app.agents.missing_information.agent import MissingInformationAgent
    s, case = _setup(api)
    monkeypatch.setattr(MissingInformationAgent, "run", lambda self, ctx, step: 1 / 0)
    run = api.ask(s, case["id"], "Review this case")
    r = run["result"]
    assert run["status"] == "partial"
    assert any(st["action"] == "missing_information.detect" and st["status"] == "failed" for st in r["plan"])
    assert r["answer"]["summary"] and r["stats"]["failures"][0]["kind"] == "ZeroDivisionError"


def test_events_stream_replays_plan_and_completion(api):
    s, case = _setup(api)
    run = api.ask(s, case["id"], "When was the accused arrested?")
    body = api.c.get(f"/api/v1/runs/{run['id']}/events", headers=s.h).text
    for t in ("run.started", "intent", "plan", "step.started", "step.completed", "verification", "run.completed"):
        assert f"event: {t}" in body
