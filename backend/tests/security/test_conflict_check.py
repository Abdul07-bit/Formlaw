"""Conflict checks run before an advocate sees a client's matter, and never reveal another client's identity."""
from __future__ import annotations

from app.services.conflicts import _matches, normalise


def _request(api, *, parties: list[str], title="Bail for my brother"):
    client = api.register("client", name="Meena Pillai", city="New Delhi")
    intake = api.c.post("/api/v1/intakes", headers=client.h, json={
        "title": title, "city": "New Delhi", "otherParties": parties,
        "description": "SYNTHETIC test matter. My brother was arrested by Delhi police last week after an FIR. We need bail."}).json()
    lawyer_id = next(m for m in api.c.post("/api/v1/matching", json={"intakeId": intake["id"]}, headers=client.h).json()["matches"]
                     if m["lawyer"]["name"].startswith("Adv. Meera Iyer"))["lawyer"]["id"]
    policy = api.c.get("/api/v1/connection-policy").json()
    a = api.c.post(f"/api/v1/intakes/{intake['id']}/connect", headers=client.h,
                   json={"lawyerId": lawyer_id, "policyVersion": policy["version"], "disclosureHash": policy["disclosureHash"]}).json()
    assert api.c.post(f"/api/v1/approvals/{a['approvalId']}/decision", json={"approve": True}, headers=client.h).json()["status"] == "executed"
    lawyer = api.demo("lawyer")
    req = next(r for r in api.c.get("/api/v1/requests", headers=lawyer.h).json()
               if any(n["name"] == "Meena Pillai" for n in r["conflictCheck"]["names"]))
    return client, intake, lawyer, req


def test_name_matching_rules():
    assert normalise("Adv. Meera Iyer (demo)") == ("meera", "iyer")
    assert normalise("ABC Components Pvt. Ltd.") == ("abc", "components")
    assert _matches(normalise("Arjun Kumar"), normalise("State v. Arjun Kumar"))
    assert _matches(normalise("ABC Components Pvt Ltd"), normalise("ABC Components — Supply Agreement"))
    assert not _matches(normalise("Kumar"), normalise("State v. Arjun Kumar"))  # a surname alone is too weak
    assert not _matches(normalise("Arjun Kumar"), normalise("Arjun Kumarswamy"))


def test_hit_is_reported_by_reference_only(api, seeded):
    _, _, _, req = _request(api, parties=["Arjun Kumar", "Northwind Retail"])
    hits = req["conflictCheck"]["automatedHits"]
    assert {(h["reference"], h["name"], h["field"]) for h in hits} >= {("FL-2026-0001", "Arjun Kumar", "title")}
    text = str(req)
    assert "State v." not in text and "Sunita" not in text and "Supply Agreement" not in text  # nothing about other clients
    assert "title" not in req["intake"] and "note" not in req and "clientName" not in req


def test_declining_for_conflict_tells_the_client_nothing(api, seeded):
    client, intake, lawyer, req = _request(api, parties=["Arjun Kumar"])
    out = api.c.post(f"/api/v1/requests/{req['id']}/conflict-check", json={"clear": False, "note": "Acting for the accused in FL-2026-0001"},
                     headers=lawyer.h).json()
    assert out["status"] == "CONFLICT"
    assert api.c.post(f"/api/v1/requests/{req['id']}/conflict-check", json={"clear": True}, headers=lawyer.h).status_code == 409
    seen = api.c.get(f"/api/v1/intakes/{intake['id']}", headers=client.h).json()
    assert seen["connections"][0]["status"] == "declined" and seen["connections"][0]["lawyerNote"] == ""
    assert "conflict" not in str(seen).lower() and "FL-2026-0001" not in str(seen)
    notes = api.c.get("/api/v1/notifications", headers=client.h).json()
    assert any("unable to take on your matter" in n["body"] for n in notes)
    assert not any("FL-2026" in n["body"] or "accused" in n["body"] for n in notes)


def test_only_the_requested_advocate_can_run_the_check(api, seeded):
    _, _, _, req = _request(api, parties=[])
    other = api.register(name="Adv. Someone Else")
    assert api.c.post(f"/api/v1/requests/{req['id']}/conflict-check", json={"clear": True}, headers=other.h).status_code == 404
    assert not any(r["id"] == req["id"] for r in api.c.get("/api/v1/requests", headers=other.h).json())
