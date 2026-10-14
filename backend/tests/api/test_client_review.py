"""Client portal: review of the client's own files, budget and advocate fees (policy-gated)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "database" / "seeds"))
import demo_documents as D  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def _intake(api, client, **extra):
    r = api.c.post("/api/v1/intakes", headers=client.h, json={
        "title": "My son was arrested", "city": "New Delhi",
        "description": "SYNTHETIC. Police arrested my son in Delhi after an FIR. We need bail urgently.", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _upload(api, client, intake_id, *files):
    r = api.c.post(f"/api/v1/intakes/{intake_id}/documents", headers=client.h, files=[("files", f) for f in files])
    assert r.status_code == 201, r.text
    return r.json()


def test_review_organises_the_clients_own_files(api):
    client = api.register("client")
    i = _intake(api, client)
    _upload(api, client, i["id"], ("FIR.pdf", D.pdf_bytes(D.FIR), "application/pdf"),
            ("Remand_Report.pdf", D.pdf_bytes(D.REMAND), "application/pdf"), ("photo.png", PNG, "image/png"))
    out = api.c.post(f"/api/v1/intakes/{i['id']}/review", headers=client.h).json()
    rv = out["review"]
    assert "not legal advice" in rv["disclaimer"] and rv["engine"].startswith("rules")
    types = {d["name"]: (d["type"], d["status"]) for d in rv["documents"]}
    assert types["FIR.pdf"] == ("fir", "read") and types["Remand_Report.pdf"][0] == "remand_report"
    assert types["photo.png"][1] == "scanned"  # an image is reported honestly, not guessed at
    # Conflicting arrest dates: both sides kept with their sources; nothing is chosen.
    arrest = next(c for c in rv["conflicts"] if c["event"] == "Arrest")
    assert {s["date"] for s in arrest["sides"]} == {"2026-03-12", "2026-03-14"}
    assert {s["source"] for s in arrest["sides"]} == {"FIR.pdf", "Remand_Report.pdf"}
    mentioned = {m["title"]: m for m in rv["missing"] if m["basis"] == "mentioned"}
    assert "Arrest memo" in mentioned and "FIR.pdf" in mentioned["Arrest memo"]["mentionedIn"]
    assert all(t["source"] for t in rv["timeline"]) and out["reviewStale"] is False


def test_review_goes_stale_and_files_belong_to_their_owner(api):
    client = api.register("client")
    i = _intake(api, client)
    first = _upload(api, client, i["id"], ("FIR.pdf", D.pdf_bytes(D.FIR), "application/pdf"))
    api.c.post(f"/api/v1/intakes/{i['id']}/review", headers=client.h)
    after = _upload(api, client, i["id"], ("Remand_Report.pdf", D.pdf_bytes(D.REMAND), "application/pdf"))
    assert after["reviewStale"] is True
    other = api.register("client")
    doc_id = first["documents"][0]["id"]
    assert api.c.post(f"/api/v1/intakes/{i['id']}/review", headers=other.h).status_code == 404
    assert api.c.delete(f"/api/v1/intakes/{i['id']}/documents/{doc_id}", headers=other.h).status_code == 404
    left = api.c.delete(f"/api/v1/intakes/{i['id']}/documents/{doc_id}", headers=client.h).json()
    assert [d["filename"] for d in left["documents"]] == ["Remand_Report.pdf"]


def test_budget_fit_is_shown_only_when_the_policy_shows_fees(api, seeded):
    client = api.register("client", city="New Delhi")
    i = _intake(api, client, budgetMax=20_000)
    m = api.c.post("/api/v1/matching", json={"intakeId": i["id"]}, headers=client.h).json()
    assert m["budgetMax"] == 20_000
    meera = next(x for x in m["matches"] if x["lawyer"]["name"].startswith("Adv. Meera Iyer"))
    assert meera["lawyer"]["feeRange"] == {"min": 20_000, "max": 80_000} and meera["lawyer"]["feesSelfDeclared"] is True
    assert meera["budgetFit"] == "partly"
    assert all(x["budgetFit"] in ("within", "partly", "above", "not_declared") for x in m["matches"])
    # Under a reviewed policy that hides fees, neither fees nor budget fit are disclosed.
    from tests.security.test_connection_policy import GOOD_POLICY, _approve_policy
    _approve_policy(api, GOOD_POLICY)
    m = api.c.post("/api/v1/matching", json={"intakeId": i["id"]}, headers=client.h).json()
    assert all(x["budgetFit"] is None and "feeRange" not in x["lawyer"] and "consultationFee" not in x["lawyer"] for x in m["matches"])


def test_parties_lock_after_contacting_an_advocate_and_fee_range_is_validated(api, seeded):
    client = api.register("client", city="New Delhi")
    i = _intake(api, client)
    assert api.c.patch(f"/api/v1/intakes/{i['id']}", json={"otherParties": ["Arjun Kumar"], "budgetMax": 50_000},
                       headers=client.h).json()["declaredParties"] == ["Arjun Kumar"]
    lawyer_id = api.c.post("/api/v1/matching", json={"intakeId": i["id"]}, headers=client.h).json()["matches"][0]["lawyer"]["id"]
    policy = api.c.get("/api/v1/connection-policy").json()
    a = api.c.post(f"/api/v1/intakes/{i['id']}/connect", headers=client.h,
                   json={"lawyerId": lawyer_id, "policyVersion": policy["version"], "disclosureHash": policy["disclosureHash"]}).json()
    api.c.post(f"/api/v1/approvals/{a['approvalId']}/decision", json={"approve": True}, headers=client.h)
    r = api.c.patch(f"/api/v1/intakes/{i['id']}", json={"otherParties": ["Someone Else"]}, headers=client.h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "parties_locked"
    assert api.c.patch(f"/api/v1/intakes/{i['id']}", json={"budgetMax": 60_000}, headers=client.h).json()["budgetMax"] == 60_000
    lawyer = api.register()
    r = api.c.put("/api/v1/lawyers/profile", json={"feeRangeMin": 50_000, "feeRangeMax": 10_000}, headers=lawyer.h)
    assert r.status_code == 422
