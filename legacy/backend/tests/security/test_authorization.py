"""IDOR / BOLA, RBAC, tenant and client–lawyer isolation, mass assignment."""
import pytest

from tests.helpers import make_pdf

FIR = ["FIR No. 1/2026. Offence: Theft under Section 303 BNS.", "The accused was arrested on 14 March 2026."]


@pytest.fixture
def world(api, seeded):
    alice, bob = api.register(email="alice@example.com"), api.register(email="bob@example.com")
    case = api.case(alice, "Alice's matter")
    api.upload(alice, case["id"], "fir.pdf", make_pdf(FIR), "application/pdf")
    api.c.post(f"/api/v1/cases/{case['id']}/review", headers=alice.h)
    return {"alice": alice, "bob": bob, "case": case, "lawyer": api.demo("lawyer"), "admin": api.demo("admin")}


@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/cases/{id}"), ("post", "/api/v1/cases/{id}/review"), ("get", "/api/v1/cases/{id}/evidence"),
    ("get", "/api/v1/cases/{id}/lawyer-matches"),
])
def test_other_client_gets_404_not_403(api, world, method, path):
    r = getattr(api.c, method)(path.format(id=world["case"]["id"]), headers=world["bob"].h)
    assert r.status_code in (403, 404)
    if method == "get" and path == "/api/v1/cases/{id}":
        assert r.status_code == 404  # no existence oracle


def test_other_client_cannot_upload_chat_or_draft(api, world):
    cid, h = world["case"]["id"], world["bob"].h
    assert api.upload(world["bob"], cid, "x.txt", b"hello", "text/plain").status_code == 404
    assert api.c.post(f"/api/v1/cases/{cid}/chat", json={"question": "who?"}, headers=h).status_code == 404
    assert api.c.post(f"/api/v1/cases/{cid}/draft", json={"docType": "bail"}, headers=h).status_code == 404


def test_other_client_cannot_list_or_probe(api, world):
    assert api.c.get("/api/v1/cases", headers=world["bob"].h).json() == []
    assert api.c.get("/api/v1/cases/00000000-0000-0000-0000-000000000000", headers=world["bob"].h).status_code == 404


def test_lawyer_without_accepted_connection_cannot_read_case(api, world):
    assert api.c.get(f"/api/v1/cases/{world['case']['id']}", headers=world["lawyer"].h).status_code == 404


def test_admin_cannot_read_client_case_files(api, world):
    assert api.c.get(f"/api/v1/cases/{world['case']['id']}", headers=world["admin"].h).status_code == 404


def test_counsel_reads_brief_but_not_raw_text_or_security_log(api, world):
    alice, lawyer, cid = world["alice"], world["lawyer"], world["case"]["id"]
    req = api.c.post("/api/v1/approvals", json={"action": "connection.request", "resourceId": cid,
                                                "params": {"lawyerId": lawyer.user["lawyerId"], "note": "Please help"}}, headers=alice.h).json()
    api.c.post(f"/api/v1/approvals/{req['id']}/decision", json={"approve": True}, headers=alice.h)
    conn = api.c.get("/api/v1/connections", headers=lawyer.h).json()[0]
    api.c.post(f"/api/v1/connections/{conn['id']}/respond", json={"accept": True}, headers=lawyer.h)
    got = api.c.get(f"/api/v1/cases/{cid}", headers=lawyer.h).json()
    assert got["access"] == "counsel" and got["budget"] == 0
    assert all(d["text"] == "" for d in got["documents"])
    assert got["analysis"]["security"] == []
    # Counsel cannot write to the client's case or chat over raw documents.
    assert api.upload(lawyer, cid, "x.txt", b"hello", "text/plain").status_code == 403
    assert api.c.post(f"/api/v1/cases/{cid}/chat", json={"question": "who?"}, headers=lawyer.h).status_code == 404


def test_other_lawyer_cannot_see_or_answer_connection(api, world):
    alice, lawyer, cid = world["alice"], world["lawyer"], world["case"]["id"]
    req = api.c.post("/api/v1/approvals", json={"action": "connection.request", "resourceId": cid,
                                                "params": {"lawyerId": lawyer.user["lawyerId"]}}, headers=alice.h).json()
    conn_id = api.c.post(f"/api/v1/approvals/{req['id']}/decision", json={"approve": True}, headers=alice.h).json()["result"]["connectionId"]
    other = api.register("lawyer")
    assert api.c.get("/api/v1/connections", headers=other.h).json() == []
    assert api.c.post(f"/api/v1/connections/{conn_id}/respond", json={"accept": True}, headers=other.h).status_code == 404
    assert api.c.post(f"/api/v1/connections/{conn_id}/messages", json={"text": "hi"}, headers=world["bob"].h).status_code == 404


@pytest.mark.parametrize("path", ["/api/v1/admin/kyc", "/api/v1/admin/security-events", "/api/v1/admin/audit", "/api/v1/admin/users", "/api/v1/admin/health"])
def test_rbac_admin_routes(api, world, path):
    assert api.c.get(path, headers=world["alice"].h).status_code == 403
    assert api.c.get(path, headers=world["lawyer"].h).status_code == 403
    assert api.c.get(path, headers=world["admin"].h).status_code == 200


def test_rbac_role_specific_actions(api, world):
    lawyer, alice = world["lawyer"], world["alice"]
    assert api.c.post("/api/v1/cases", json={"title": "Lawyer case"}, headers=lawyer.h).status_code == 403
    assert api.c.patch("/api/v1/lawyers/me", json={"bio": "x"}, headers=alice.h).status_code == 403
    assert api.c.post(f"/api/v1/admin/kyc/{lawyer.user['lawyerId']}/decision", json={"approve": True, "note": "x"}, headers=lawyer.h).status_code == 403


def test_mass_assignment_rejected(api, world):
    h = world["alice"].h
    r = api.c.post("/api/v1/cases", json={"title": "x title", "ownerId": world["bob"].user["id"], "status": "reviewed", "isDemo": True}, headers=h)
    assert r.status_code == 422
    r = api.c.post("/api/v1/auth/register", json={"name": "Eve Y", "email": "eve@example.com", "password": "Correct-Horse-42", "role": "client", "isAdmin": True})
    assert r.status_code == 422


def test_cannot_connect_to_unverified_lawyer(api, world):
    unverified = api.register("lawyer")
    r = api.c.post("/api/v1/approvals", json={"action": "connection.request", "resourceId": world["case"]["id"],
                                              "params": {"lawyerId": unverified.user["lawyerId"]}}, headers=world["alice"].h)
    assert r.json()["error"]["code"] == "lawyer_not_verified"


def test_approval_cannot_be_decided_by_someone_else(api, world):
    req = api.c.post("/api/v1/approvals", json={"action": "case.delete", "resourceId": world["case"]["id"]}, headers=world["alice"].h).json()
    assert api.c.post(f"/api/v1/approvals/{req['id']}/decision", json={"approve": True}, headers=world["bob"].h).status_code == 404
    assert api.c.get(f"/api/v1/cases/{world['case']['id']}", headers=world["alice"].h).status_code == 200
