import json
from pathlib import Path

import pytest

from app.agents.engine.chunking import DocText, chunk_documents, markers_to_form_feeds
from app.agents.engine.contract_review import review_contract
from app.agents.engine.orchestrator import AnalysisInput, analyse
from app.agents.gateway import AgentRun
from app.core.config import AgentLimits
from app.core.errors import AgentLimitExceeded, Forbidden

SEED = json.loads((Path(__file__).resolve().parents[3] / "database" / "seeds" / "demo_data.json").read_text(encoding="utf-8"))["demoCase"]


def _docs(malicious=False):
    docs = SEED["documents"] + ([SEED["maliciousDocument"]] if malicious else [])
    return [DocText(f"D{i}", d["name"], d["text"]) for i, d in enumerate(docs)]


def _run(docs, limits=AgentLimits()):
    return analyse(AnalysisInput("TASK-T", SEED["title"], SEED["description"], "New Delhi", 150000, docs, 0, [], [], limits))


def test_demo_case_review():
    r = _run(_docs())
    assert r.area == "Criminal"
    assert [c.topic for c in r.contradictions] == ["Arrest date"]
    assert {r.contradictions[0].a_value, r.contradictions[0].b_value} == {"12 March 2026", "14 March 2026"}
    assert all(f.evidence for f in r.facts), "every claim must cite evidence"
    labels = {e.label for e in r.evidence}
    assert all(l in labels for f in r.facts for l in f.evidence)
    assert "Arrest memo" in [g.title for g in r.missing]
    assert not r.security
    assert "[E0" in r.draft_body and "enrolled advocate" in r.draft_body


def test_injected_document_is_quarantined_and_review_continues():
    clean, attacked = _run(_docs()), _run(_docs(malicious=True))
    assert [h.doc_name for h in attacked.security] == ["suspicious_affidavit.txt"]
    assert attacked.security[0].kind == "exfiltration"
    assert "External tool / network access denied" in attacked.security[0].actions
    assert not any(e.doc_name == "suspicious_affidavit.txt" for e in attacked.evidence)
    assert "guilty" not in attacked.summary.lower() and "guilty" not in attacked.draft_body.lower()
    assert len(attacked.facts) == len(clean.facts)  # legitimate review unaffected
    assert any(t.kind == "danger" for t in attacked.run.trace)


def test_step_limit_stops_safely():
    with pytest.raises(AgentLimitExceeded):
        _run(_docs(), AgentLimits(max_agent_steps=3))


def test_tool_call_limit_stops_safely():
    with pytest.raises(AgentLimitExceeded):
        _run(_docs(), AgentLimits(max_tool_calls=2))


def test_gateway_denies_tools_outside_allowlist():
    run = AgentRun("T", AgentLimits())
    with pytest.raises(Forbidden):
        run.call("Drafting Agent", "search_verified_lawyers", lambda: None)
    with pytest.raises(Forbidden):
        run.call("Case Review Agent", "send_email", lambda: None)


def test_gateway_bounded_retries():
    run = AgentRun("T", AgentLimits(max_retries=2))
    calls = []

    def flaky():
        calls.append(1)
        raise TimeoutError

    with pytest.raises(TimeoutError):
        run.call("Research Agent", "search_legal_corpus", flaky, retryable=(TimeoutError,))
    assert len(calls) == 3  # first try + MAX_RETRIES


def test_contract_review():
    text = ("[[PAGE 1]]\nThis Agreement is made between the parties. The Vendor shall deliver goods within 30 days. "
            "The Company may terminate this agreement at any time without notice. This agreement shall automatically renew each year.")
    out = review_contract(chunk_documents([DocText("c", "msa.txt", text)]))
    risks = {f.title for f in out.findings if f.kind == "risk"}
    assert {"One-sided termination", "Automatic renewal"} <= risks
    assert "Governing law" in out.missing_clauses and "Termination" in out.clauses_found
    assert any(f.kind == "obligation" for f in out.findings)


def test_page_markers_preserved_for_legacy_agents():
    assert markers_to_form_feeds("Head\n[[PAGE 1]]\nA\n[[PAGE 2]]\nB\n[[PAGE 4]]\nD") == "Head\nA\fB\f\fD"
