"""The headline scenario: conflicting arrest dates are detected, not resolved by guessing, and every claim is cited."""
from __future__ import annotations

FIR = ["FIRST INFORMATION REPORT\nFIR registered on 11 March 2026 at PS Saket. The complainant Rohan Mehta stated his phone was snatched on 10 March 2026.",
       "ACTION TAKEN\nThe accused Arjun Kumar was arrested on 12 March 2026 at his residence. The arrest memo was prepared at the spot. "
       "A seizure memo was prepared for the recovered phone."]
REMAND = ["REMAND REPORT\nThe accused Arjun Kumar was arrested on 14 March 2026 at 11:00 am near Saket Metro Station and is produced before the court."]


def _case(api):
    s = api.register("lawyer")
    case = api.case(s, "State v. Arjun Kumar")
    api.upload_text(s, case["id"], "FIR.txt", FIR)
    api.upload_text(s, case["id"], "RemandReport.txt", REMAND)
    return s, case


def test_contradiction_found_with_both_sources_cited(api):
    s, case = _case(api)
    run = api.ask(s, case["id"], "Find contradictions in the arrest timeline and identify which document is more reliable.")
    r = run["result"]
    assert run["status"] == "completed", run
    assert r["intent"] == "CONTRADICTIONS"
    arrest = [x for x in r["contradictions"] if x["topic"] == "Date of arrest"]
    assert arrest, r["contradictions"]
    x = arrest[0]
    assert {x["a"]["value"], x["b"]["value"]} == {"12 March 2026", "14 March 2026"}
    assert {x["a"]["citation"]["documentName"], x["b"]["citation"]["documentName"]} == {"FIR.txt", "RemandReport.txt"}
    # Provenance step ran and did not pick a winner.
    assert "does not choose" in x["provenance"]["assessment"]
    # The missing arrest memo is flagged, referenced from the FIR text.
    assert any("arrest memo" in m["title"].lower() for m in r["missing"])
    # Adaptation is visible in the plan.
    assert any(st["action"] == "contradiction.resolve" and st["origin"] == "adapt" for st in r["plan"])
    # The answer never states one date as fact.
    assert "conflict" in r["answer"]["summary"].lower()
    assert r["answer"]["requiresLawyerReview"]
    for c in r["claims"]:
        if c["id"] in r["answer"]["claimIds"]:
            assert c["status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED") and c["citations"], c


def test_evidence_question_adapts_to_conflict(api):
    """Asked a simple question, the orchestrator notices the conflict in retrieved evidence and launches the contradiction agent."""
    s, case = _case(api)
    r = api.ask(s, case["id"], "Which document establishes the arrest date?")["result"]
    assert r["intent"] == "EVIDENCE_QA"
    assert any(st["action"] == "contradiction.detect" and st["origin"] == "adapt" for st in r["plan"]), r["plan"]
    assert r["contradictions"]
    assert "12 March 2026" in r["answer"]["summary"] and "14 March 2026" in r["answer"]["summary"]


def test_workspace_views_persist_findings(api):
    s, case = _case(api)
    api.ask(s, case["id"], "Review this case and identify the biggest weaknesses.")
    cid = case["id"]
    timeline = api.c.get(f"/api/v1/cases/{cid}/timeline", headers=s.h).json()
    assert any(t["status"] == "conflicted" for t in timeline)
    contradictions = api.c.get(f"/api/v1/cases/{cid}/contradictions", headers=s.h).json()
    assert contradictions and contradictions[0]["a"]["quote"]
    missing = api.c.get(f"/api/v1/cases/{cid}/missing-information", headers=s.h).json()
    assert any(m["basis"] == "referenced_in_documents" and m["citation"] for m in missing)
    activity = api.c.get(f"/api/v1/cases/{cid}/activity", headers=s.h).json()
    assert activity[0]["tools"] and activity[0]["status"] == "completed"
