"""End-to-end product flows through the public API."""
from __future__ import annotations

import sys
from pathlib import Path

from tests.helpers import make_pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "database" / "seeds"))
import demo_documents as D  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def test_register_lawyer_creates_practice(api):
    s = api.register(firm="Rao & Co")
    assert s.user["role"] == "lawyer" and s.user["organizationName"] == "Rao & Co" and s.user["verificationStatus"] == "NOT_STARTED"
    assert api.c.post("/api/v1/auth/register", json={"name": "X Admin", "email": "a@x.com", "password": "Correct-Horse-42", "role": "admin"}).status_code == 422


def test_kyc_verification_flow(api, seeded):
    s = api.register(name="Adv. Test Lawyer")
    api.c.put("/api/v1/lawyers/profile", json={"barCouncil": "Bar Council of Delhi", "enrolmentNumber": "D/1234/2015",
                                               "practiceAreas": ["criminal", "family"], "city": "New Delhi"}, headers=s.h)
    files = {"governmentId": ("id.png", PNG, "image/png"), "qualification": ("llb.pdf", make_pdf(["LL.B."]), "application/pdf")}
    r = api.c.post("/api/v1/lawyers/verification", data={"idType": "Bar Council ID"}, files=files, headers=s.h)
    assert r.status_code == 201 and r.json()["verificationStatus"] == "UNDER_REVIEW"
    ver = api.c.get("/api/v1/lawyers/verification", headers=s.h).json()
    assert {c["type"] for c in ver["checks"]} == {"government_id", "qualification", "bar_registration"} and all(c["demo"] for c in ver["checks"])
    assert {(e["from"], e["to"]) for e in ver["history"]} == {("NOT_STARTED", "PENDING"), ("PENDING", "UNDER_REVIEW")}
    assert all(l["id"] != s.user["lawyerId"] for l in api.c.get("/api/v1/lawyers").json())  # not public yet
    admin = api.demo("admin")
    queue = api.c.get("/api/v1/admin/verifications", headers=admin.h).json()
    assert any(q["lawyer"]["id"] == s.user["lawyerId"] for q in queue)
    url = f"/api/v1/admin/verifications/{s.user['lawyerId']}/decision"
    base = {"approve": True, "note": "Documents reviewed", "verifiedAreas": ["criminal"], "judicialStatus": True}
    roll = {"source": "Bar Council of Delhi - roll of advocates", "reference": "SYNTHETIC test reference", "checkedOn": "2026-10-12",
            "enrolmentNumberMatches": True, "nameMatches": True}
    for body, code in [(base, "bar_roll_check_required"), (base | {"barRollCheck": roll | {"nameMatches": False}}, "bar_roll_mismatch"),
                       (base | {"barRollCheck": roll | {"checkedOn": "2099-01-01"}}, "bar_roll_date")]:
        r = api.c.post(url, json=body, headers=admin.h)
        assert r.status_code == 422 and r.json()["error"]["code"] == code, r.text
    d = api.c.post(url, json=base | {"barRollCheck": roll}, headers=admin.h).json()
    hist = api.c.get(f"/api/v1/admin/verifications/{s.user['lawyerId']}/history", headers=admin.h).json()
    assert any(h["to"] == "VERIFIED" and "Bar Council of Delhi" in h["reason"] for h in hist)
    assert d["verificationStatus"] == "VERIFIED" and d["verifiedAreas"] == ["criminal"]
    assert d["judicialStatusVerified"] is False  # no judicial-status check was submitted, so it cannot be granted
    api.c.put("/api/v1/lawyers/profile", json={"publish": True}, headers=s.h)
    assert any(l["id"] == s.user["lawyerId"] for l in api.c.get("/api/v1/lawyers?area=criminal").json())


def test_client_intake_matching_connection_and_portal(api, seeded):
    client = api.register("client", city="New Delhi")
    intake = api.c.post("/api/v1/intakes", json={
        "title": "My son was arrested", "city": "New Delhi",
        "description": "Police arrested my son Arjun on 12 March 2026 in Delhi for a phone theft. An FIR was registered. "
                       "We need bail urgently. I have a copy of the FIR."}, headers=client.h).json()
    assert intake["matterType"] == "criminal" and intake["urgency"] == "urgent"
    assert any(t["date_text"] == "12 March 2026" for t in intake["structured"]["timeline"])
    m = api.c.post("/api/v1/matching", json={"intakeId": intake["id"]}, headers=client.h).json()
    assert m["matches"] and "does not predict" in m["disclaimer"]
    top = m["matches"][0]
    assert "Verified criminal practice" in top["reasons"] and top["lawyer"]["verificationStatus"] == "VERIFIED"
    assert "rating" not in str(m).lower() and "win" not in str(m["matches"]).lower()
    demo_lawyer = next(x for x in m["matches"] if x["lawyer"]["name"].startswith("Adv. Meera Iyer"))["lawyer"]
    policy = api.c.get("/api/v1/connection-policy").json()
    assert policy["source"] == "demo" and policy["disclosures"]
    a = api.c.post(f"/api/v1/intakes/{intake['id']}/connect", json={"lawyerId": demo_lawyer["id"], "policyVersion": policy["version"],
                                                                    "disclosureHash": policy["disclosureHash"]}, headers=client.h).json()
    lawyer = api.demo("lawyer")
    before = {r["id"] for r in api.c.get("/api/v1/requests", headers=lawyer.h).json()}
    api.c.post(f"/api/v1/approvals/{a['approvalId']}/decision", json={"approve": True}, headers=client.h)
    req = next(r for r in api.c.get("/api/v1/requests", headers=lawyer.h).json() if r["id"] not in before)
    # Conflict check first: names only — no title, summary, note or client contact details yet.
    assert req["conflictCheck"]["status"] == "PENDING_REVIEW" and "title" not in req["intake"] and "structured" not in req["intake"]
    assert {n["role"] for n in req["conflictCheck"]["names"]} == {"client"}
    r = api.c.post(f"/api/v1/requests/{req['id']}/respond", json={"accept": True}, headers=lawyer.h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict_check_required"
    assert api.c.post(f"/api/v1/requests/{req['id']}/conflict-check", json={"clear": True}, headers=lawyer.h).json()["status"] == "CLEARED"
    req = next(r for r in api.c.get("/api/v1/requests", headers=lawyer.h).json() if r["id"] == req["id"])
    assert req["intake"]["title"] == "My son was arrested"
    acc = api.c.post(f"/api/v1/requests/{req['id']}/respond", json={"accept": True}, headers=lawyer.h).json()
    assert acc["status"] == "accepted" and acc["caseId"]
    lawyer_case = api.c.get(f"/api/v1/cases/{acc['caseId']}", headers=lawyer.h).json()
    assert lawyer_case["matterType"] == "criminal" and lawyer_case["myRole"] == "lead"
    # The client sees a client-safe projection only.
    portal = api.c.get(f"/api/v1/portal/cases/{acc['caseId']}", headers=client.h).json()
    assert set(portal) == {"id", "reference", "title", "status", "matterType", "lawyers", "updatedAt", "updates", "documents", "messages"}
    api.c.post(f"/api/v1/portal/cases/{acc['caseId']}/messages", json={"body": "Thank you"}, headers=client.h)
    assert api.c.get(f"/api/v1/cases/{acc['caseId']}/messages", headers=lawyer.h).json()[0]["body"] == "Thank you"
    up = api.c.post(f"/api/v1/portal/cases/{acc['caseId']}/documents", files=[("files", ("fir.txt", b"FIR copy: arrested on 12 March 2026.", "text/plain"))], headers=client.h)
    assert up.status_code == 201 and "contentHash" not in up.json()[0]


def test_draft_workflow_is_lawyer_controlled(api):
    s = api.register()
    case = api.case(s, "State v. Arjun Kumar")
    api.upload(s, case["id"], "FIR.pdf", D.pdf_bytes(D.FIR), "application/pdf")
    api.upload(s, case["id"], "Remand.pdf", D.pdf_bytes(D.REMAND), "application/pdf")
    r = api.c.post(f"/api/v1/cases/{case['id']}/draft", json={"draftKind": "cross_examination_questions"}, headers=s.h)
    run = api.c.get(f"/api/v1/runs/{r.json()['runId']}", headers=s.h).json()["result"]
    draft = run["draft"]
    assert draft and draft["kind"] == "cross_examination_questions" and "QUESTIONS" in draft["body"]
    assert "[PLACEHOLDER" in draft["body"]
    steps = [st["action"] for st in run["plan"]]
    assert steps.index("verification.verify") < steps.index("drafting.compose")  # facts verified before drafting
    drafts = api.c.get(f"/api/v1/cases/{case['id']}/drafts", headers=s.h).json()
    assert drafts[0]["status"] == "draft"
    edited = api.c.patch(f"/api/v1/drafts/{drafts[0]['id']}", json={"body": drafts[0]["body"] + "\nEdited by counsel."}, headers=s.h).json()
    assert edited["version"] == 2
    assert api.c.post(f"/api/v1/drafts/{drafts[0]['id']}/approve", headers=s.h).json()["status"] == "approved"


def test_contract_review_finds_risks_conflicts_and_missing_annexures(api):
    s = api.register()
    case = api.case(s, "Supply agreement", matter_type="contract")
    api.upload(s, case["id"], "Master_Supply_Agreement.pdf", D.pdf_bytes(D.CONTRACT), "application/pdf")
    r = api.ask(s, case["id"], "Review this contract for risks")["result"]
    assert r["intent"] == "CONTRACT_REVIEW"
    kinds = {c["kind"] for c in r["claims"]}
    assert {"contract_termination", "contract_unusual"} <= kinds
    assert any(c["meta"].get("risk") == "high" for c in r["claims"])
    assert any(x["topic"] == "Notice period" for x in r["contradictions"])  # 30 days vs 90 days


def test_missing_records_referenced_in_documents(api):
    s = api.register()
    case = api.case(s, "State v. Arjun Kumar")
    api.upload(s, case["id"], "FIR.pdf", D.pdf_bytes(D.FIR), "application/pdf")
    r = api.ask(s, case["id"], "What documents are missing?")["result"]
    ref = {m["title"] for m in r["missing"] if m["basis"] == "referenced_in_documents"}
    assert {"Arrest memo", "Seizure / recovery memo", "Witness statement(s)"} <= ref
    assert all(m["citation"] and m["citation"]["documentName"] == "FIR.pdf" for m in r["missing"] if m["basis"] == "referenced_in_documents")


def test_findings_tasks_and_review(api):
    s = api.register()
    case = api.case(s)
    api.upload_text(s, case["id"], "FIR.txt", ["The accused was arrested on 12 March 2026 at his residence."])
    api.ask(s, case["id"], "Review this case")
    claims = api.c.get(f"/api/v1/cases/{case['id']}/claims", headers=s.h).json()
    assert api.c.patch(f"/api/v1/claims/{claims[0]['id']}", json={"decision": "accepted", "note": "checked"}, headers=s.h).json()["reviewStatus"] == "accepted"
    api.ask(s, case["id"], "Review this case")  # a re-run refreshes verification but keeps the lawyer's decision
    again = {c["id"]: c for c in api.c.get(f"/api/v1/cases/{case['id']}/claims", headers=s.h).json()}
    assert again[claims[0]["id"]]["reviewStatus"] == "accepted"
    assert api.c.post(f"/api/v1/cases/{case['id']}/tasks", json={"title": "Obtain arrest memo"}, headers=s.h).status_code == 201
    assert api.c.post(f"/api/v1/cases/{case['id']}/findings", json={"title": "Arrest date conflict", "content": {"x": 1}}, headers=s.h).status_code == 201
    ov = api.c.get(f"/api/v1/cases/{case['id']}/overview", headers=s.h).json()
    assert ov["openTasks"] == 1 and ov["runs"] == 2
