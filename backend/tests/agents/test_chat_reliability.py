"""Case chat reliability: model fallback chain, honest "not established" answers, and runs that always end visibly."""
from __future__ import annotations

import httpx

from app.db.session import session_factory
from app.domain.enums import RunStatus
from app.llm import providers
from app.llm.providers import GeminiProvider, LLMRouter, set_provider
from app.llm.schemas import IntentOut
from app.models import AgentRun
from app.services import runs

from .test_runtime import _script, _setup

TEMPLATE = ["CASE TITLE\n[Plaintiff / Complainant] vs. [Defendant / Respondent]\n"
            "PARTIES\nPlaintiff / Complainant: [Full Name]\nDefendant / Respondent: [Full Name]\nWitnesses: [Names]\n"
            "CASE INFORMATION\nFiling Date: [DD/MM/YYYY]\nCase Number: [Court Case Number]\n"
            "CASE SUMMARY\nBackground: Describe the events leading to the dispute.\n"
            "Defendant / Respondent Position: [Argument 1, supporting evidence, and legal basis.]"]


def _fake_gemini(monkeypatch, limited: set[str]):
    seen: list[str] = []

    def post(url, **_kw):
        model = url.split("/models/")[1].split(":")[0]
        seen.append(model)
        req = httpx.Request("POST", url)
        if model in limited:
            return httpx.Response(429, json={"error": {"message": "quota"}}, request=req)
        return httpx.Response(200, request=req, json={"candidates": [{"content": {"parts": [{"text": '{"intent": "EVIDENCE_QA"}'}]}}]})

    monkeypatch.setattr(providers.httpx, "post", post)
    monkeypatch.setattr(providers, "_gemini_cooldown", {})
    return seen


def test_rate_limited_primary_falls_back_to_next_gemini_model(monkeypatch):
    seen = _fake_gemini(monkeypatch, limited={"primary"})
    router = LLMRouter([GeminiProvider("k", "primary,second,lite")])
    obj, _tokens, label = router.generate("compose", system_prompt="s", user_prompt="u", schema=IntentOut)
    assert obj.intent == "EVIDENCE_QA"
    assert seen == ["primary", "second"]  # the explicitly routed model no longer disables the fallback chain
    assert label == "gemini:second"  # the model that actually answered is recorded

    seen.clear()  # the exhausted model is tried last while it cools down
    router.generate("compose", system_prompt="s", user_prompt="u", schema=IntentOut)
    assert seen == ["second"]


def test_unanswerable_question_says_so_instead_of_quoting_unrelated_text(api):
    s, case = _setup(api)
    set_provider(_script(ComposeOut=[{"summary": "The case documents do not establish this.", "sentences": [],
                                      "limitations": ["The FIR does not name the investigating officer's rank."]}]))
    r = api.ask(s, case["id"], "What is the rank of the investigating officer?")["result"]
    assert r["answer"]["summary"] == "The case documents do not establish this."
    assert r["answer"]["limitations"][0] == "The FIR does not name the investigating officer's rank."
    assert r["answer"]["claimIds"] == [] and not r["unverified"]  # no unrelated passages presented as the answer
    assert r["answer"]["assessment"]["level"] == "insufficient"
    assert not any(st["origin"] == "replan" for st in r["plan"])


def test_template_only_case_reports_incomplete_analysis_and_missing_fields(api):
    s, case = _setup(api, pages=TEMPLATE, name="case_form.txt")
    docs = api.c.get(f"/api/v1/cases/{case['id']}/documents", headers=s.h).json()
    assert docs[0]["docType"] == "template"
    for question, model in (("Who is the accused?", True), ("Review this case and identify the biggest weaknesses.", False)):
        if model:
            set_provider(_script(ComposeOut=[{"summary": "Plaintiff is [Full Name].", "sentences": []}]))
        else:
            set_provider(None)
        r = api.ask(s, case["id"], question)["result"]
        a = r["answer"]
        assert a["summary"].startswith("CASE ANALYSIS INCOMPLETE — The supplied document contains template fields")
        assert a["assessment"]["level"] == "not_assessed"
        assert any("Plaintiff / Complainant" in lim and "Case Number" in lim for lim in a["limitations"])
        titles = {m["title"] for m in r["missing"] if m["basis"] == "template_field"}
        assert {"Plaintiff / Complainant", "Defendant / Respondent", "Filing Date", "Case Number"} <= titles
        shown = " ".join(c["text"] for c in r["claims"] if c["id"] in a["claimIds"]) + " ".join(p["name"] for p in r["parties"])
        assert "[" not in shown and "Full Name" not in shown  # placeholders never become facts or parties
    assert r["report"]["documents"]["templates"] == ["case_form.txt"]
    assert r["report"]["nextSteps"][0].startswith("Upload the completed case documents")


def test_template_alongside_real_documents_is_excluded_not_fatal(api):
    s, case = _setup(api)
    api.upload_text(s, case["id"], "blank_form.txt", TEMPLATE)
    r = api.ask(s, case["id"], "When was the accused arrested?")["result"]
    assert not r["answer"]["summary"].startswith("CASE ANALYSIS INCOMPLETE")
    assert "12 March 2026" in " ".join(c["text"] for c in r["claims"])
    assert all(e["documentName"] != "blank_form.txt" for e in r["evidence"])


def test_assessment_labels_replace_generic_confidence(api):
    s, case = _setup(api)
    r = api.ask(s, case["id"], "When was the accused arrested?")["result"]
    assert r["answer"]["assessment"] == {"level": "strong", "label": "Strong documentary support",
                                         "reason": r["answer"]["assessment"]["reason"]}
    assert "not whether their contents are true" in r["answer"]["assessment"]["reason"]


def test_case_review_report_has_sourced_overview_and_next_steps(api):
    s, case = _setup(api, pages=["Police Station: Saket, New Delhi. FIR No. DEMO-7/2026. Offence: Section 303(2) BNS (theft).\n"
                                 "The accused Arjun Kumar was arrested on 12 March 2026 at his residence. The arrest memo was prepared."])
    r = api.ask(s, case["id"], "Review this case")["result"]
    rep = r["report"]
    fields = {f["key"]: f for f in rep["overview"]["fields"]}
    assert fields["case_number"]["value"] == "FIR No. DEMO-7/2026" and fields["case_number"]["citation"]["page"] == 1
    assert fields["police_station"]["value"] == "Saket"
    assert fields["court"]["value"] is None  # shown as "Not found in the provided documents."
    assert rep["notFound"] == "Not found in the provided documents."
    assert [p["value"] for p in rep["overview"]["provisions"]] == ["Section 303(2) BNS"]
    assert any("not independently verified" in st for st in rep["nextSteps"])
    assert rep["nextSteps"][-1].startswith("Have a qualified lawyer review")


def test_template_detection_ignores_judgment_conventions():
    from app.ingestion.profile import is_placeholder_only, is_template
    assert not is_placeholder_only("STATE OF GOA v. JOSE MARIA ALBERT VALES @ ROBERT 179 VALES [AMITAVA ROY, J.]")
    assert not is_placeholder_only("554 SUPREME COURT REPORTS [2016] 7 S.C.R. A change in the prices.\" [Emphasis supplied by us].")
    assert not is_template("The accused [sic] was arrested on 12 March 2026 at Saket. A phone was recovered [Annexure P-1].")
    assert is_template(TEMPLATE[0])


def test_crashed_run_leaves_a_visible_answer_and_terminal_event(api, monkeypatch):
    s, case = _setup(api)
    monkeypatch.setattr(runs, "_execute", lambda db, run_id: 1 / 0)
    run = api.ask(s, case["id"], "When was the accused arrested?")
    assert run["status"] == "failed"
    msgs = api.c.get(f"/api/v1/threads/{run['threadId']}/messages", headers=s.h).json()
    assert msgs[-1]["role"] == "assistant" and "Please ask again" in msgs[-1]["content"]
    body = api.c.get(f"/api/v1/runs/{run['id']}/events", headers=s.h).text
    assert "event: run.failed" in body


def test_runs_interrupted_by_a_restart_are_closed(api):
    s, case = _setup(api)
    run = api.ask(s, case["id"], "When was the accused arrested?")
    with session_factory()() as db:  # simulate a run that was executing when the server restarted
        db.get(AgentRun, run["id"]).status = RunStatus.RUNNING
        db.commit()
    runs.ev._channels.pop(run["id"], None)
    assert runs.fail_interrupted() == 1
    assert api.c.get(f"/api/v1/runs/{run['id']}", headers=s.h).json()["status"] == "failed"
    msgs = api.c.get(f"/api/v1/threads/{run['threadId']}/messages", headers=s.h).json()
    assert "server restarted" in msgs[-1]["content"]


def test_budget_stop_still_answers_from_verified_evidence(api):
    from app.core.config import AgentLimits

    from .test_runtime import run_direct
    _, case = _setup(api)
    result, events = run_direct(case["id"], "Review this case", AgentLimits(max_agent_steps=4))
    assert result["status"] == "partial" and "MAX_AGENT_STEPS" in result["stopReason"]
    assert result["answer"]["summary"] != "No answer could be composed."
    shown = [c for c in result["claims"] if c["id"] in result["answer"]["claimIds"]]
    assert shown and all(c["status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED") for c in shown)
    assert events[-1][0] == "run.completed"
