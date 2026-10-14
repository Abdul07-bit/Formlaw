"""Tenant (organization) and case isolation, client/lawyer separation, and admin least privilege. Outsiders get 404."""
from __future__ import annotations

from app.db.session import session_factory
from app.models import Membership, User
from app.retrieval import case_index

FIR = ["The accused Arjun Kumar was arrested on 12 March 2026 at his residence."]


def _firm_case(api):
    a = api.register(firm="Firm A")
    case = api.case(a, "Confidential matter")
    doc = api.upload_text(a, case["id"], "FIR.txt", FIR)
    run = api.ask(a, case["id"], "Review this case")
    return a, case, doc, run


def test_other_firm_cannot_reach_anything(api):
    a, case, doc, run = _firm_case(api)
    b = api.register(firm="Firm B")
    cid = case["id"]
    for method, path, body in [
        ("get", f"/api/v1/cases/{cid}", None), ("get", f"/api/v1/cases/{cid}/documents", None),
        ("get", f"/api/v1/documents/{doc['id']}/pages", None), ("get", f"/api/v1/documents/{doc['id']}/file", None),
        ("get", f"/api/v1/runs/{run['id']}", None), ("get", f"/api/v1/runs/{run['id']}/events", None),
        ("get", f"/api/v1/cases/{cid}/claims", None), ("get", f"/api/v1/cases/{cid}/evidence", None),
        ("post", f"/api/v1/cases/{cid}/chat", {"message": "summarise"}), ("patch", f"/api/v1/cases/{cid}", {"title": "pwned"}),
        ("get", f"/api/v1/threads/{run['threadId']}/messages", None),
    ]:
        r = getattr(api.c, method)(path, headers=b.h, **({"json": body} if body else {}))
        assert r.status_code == 404, (path, r.status_code)
    claims = api.c.get(f"/api/v1/cases/{cid}/claims", headers=a.h).json()
    assert claims and api.c.patch(f"/api/v1/claims/{claims[0]['id']}", json={"decision": "rejected"}, headers=b.h).status_code == 404
    assert all(c["id"] != cid for c in api.c.get("/api/v1/cases", headers=b.h).json())


def test_same_firm_requires_case_membership(api):
    a, case, _, _ = _firm_case(api)
    colleague = api.register(email="colleague@example.com")
    with session_factory()() as db:  # colleague joins Firm A as an ordinary member
        u = db.query(User).filter_by(email="colleague@example.com").one()
        db.add(Membership(organization_id=a.user["organizationId"], user_id=u.id, role="member"))
        db.commit()
    colleague = api.c.post("/api/v1/auth/login", json={"email": "colleague@example.com", "password": "Correct-Horse-42"}).json()
    h = {"authorization": f"Bearer {colleague['accessToken']}"}
    assert api.c.get(f"/api/v1/cases/{case['id']}", headers=h).status_code == 404
    r = api.c.post(f"/api/v1/cases/{case['id']}/members", json={"email": "colleague@example.com", "role": "viewer"}, headers=a.h)
    assert r.status_code == 201
    assert api.c.get(f"/api/v1/cases/{case['id']}", headers=h).status_code == 200
    # Viewers can read but cannot run agents or upload.
    assert api.c.post(f"/api/v1/cases/{case['id']}/chat", json={"message": "hi"}, headers=h).status_code == 403


def _associate_of(api, owner, email: str):
    """A lawyer whose home organization is the owner's firm (as a firm would onboard staff)."""
    from app.models import Lawyer
    from app.security.passwords import hash_password
    from tests.helpers import PASSWORD, Session
    with session_factory()() as db:
        u = User(organization_id=owner.user["organizationId"], role="lawyer", email=email, name="Associate", password_hash=hash_password(PASSWORD))
        db.add(u)
        db.flush()
        db.add_all([Membership(organization_id=owner.user["organizationId"], user_id=u.id, role="member"),
                    Lawyer(user_id=u.id, name="Associate")])
        db.commit()
    r = api.c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()
    return Session(r["accessToken"], r["user"])


def test_firm_owner_gets_no_access_to_matters_they_are_not_on(api):
    owner = api.register(firm="Mehta & Co")
    assoc = _associate_of(api, owner, "assoc@example.com")
    case = api.case(assoc, "Confidential: Sharma divorce")
    doc = api.upload_text(assoc, case["id"], "Petition.txt", ["Petition filed on 2 May 2026."])
    run = api.ask(assoc, case["id"], "Review this case")
    cid = case["id"]
    for method, path, body in [
        ("get", f"/api/v1/cases/{cid}", None), ("get", f"/api/v1/cases/{cid}/documents", None),
        ("get", f"/api/v1/documents/{doc['id']}/pages", None), ("get", f"/api/v1/documents/{doc['id']}/file", None),
        ("get", f"/api/v1/cases/{cid}/claims", None), ("get", f"/api/v1/cases/{cid}/evidence", None),
        ("get", f"/api/v1/runs/{run['id']}", None), ("get", f"/api/v1/cases/{cid}/members", None),
        ("post", f"/api/v1/cases/{cid}/chat", {"message": "summarise"}),
        ("post", f"/api/v1/cases/{cid}/members", {"email": "assoc@example.com"}),
    ]:
        r = getattr(api.c, method)(path, headers=owner.h, **({"json": body} if body else {}))
        assert r.status_code == 404, (path, r.status_code)
    assert all(c["id"] != cid for c in api.c.get("/api/v1/cases", headers=owner.h).json())
    # The owner can see that the matter exists — without its title, client or content.
    register = api.c.get("/api/v1/firm/matters", headers=owner.h).json()
    row = next(m for m in register if m["id"] == cid)
    assert row["leads"] == ["Associate"] and row["iAmMember"] is False
    assert "Sharma" not in str(register) and "title" not in row and "clientName" not in row
    # An ordinary member is not firm management.
    r = api.c.get("/api/v1/firm/matters", headers=assoc.h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_firm_admin"
    # Access comes only from the matter lead adding the owner.
    assert api.c.post(f"/api/v1/cases/{cid}/members", json={"email": owner.user["email"], "role": "viewer"}, headers=assoc.h).status_code == 201
    assert api.c.get(f"/api/v1/cases/{cid}", headers=owner.h).json()["myRole"] == "viewer"


def test_platform_admin_and_compliance_cannot_bypass_matter_authorization(api, seeded):
    lawyer = api.demo("lawyer")
    case = next(c for c in api.c.get("/api/v1/cases", headers=lawyer.h).json() if c["title"] == "State v. Arjun Kumar")
    for persona in ("admin", "compliance"):
        s = api.demo(persona)
        for path in (f"/api/v1/cases/{case['id']}", f"/api/v1/cases/{case['id']}/documents", f"/api/v1/portal/cases/{case['id']}"):
            assert api.c.get(path, headers=s.h).status_code in (403, 404), (persona, path)


def test_outside_lawyer_cannot_be_added_to_case(api):
    a, case, _, _ = _firm_case(api)
    api.register(email="outsider@example.com", firm="Other Firm")
    r = api.c.post(f"/api/v1/cases/{case['id']}/members", json={"email": "outsider@example.com"}, headers=a.h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_in_organization"


def test_clients_and_admins_cannot_use_lawyer_workspace(api, seeded):
    a, case, _, _ = _firm_case(api)
    client = api.register("client")
    admin = api.demo("admin")
    for who in (client, admin):
        assert api.c.get(f"/api/v1/cases/{case['id']}", headers=who.h).status_code == 403
        assert api.c.get(f"/api/v1/cases/{case['id']}/claims", headers=who.h).status_code == 403
    # A client who is not a member of the case cannot see it in the portal either.
    assert api.c.get(f"/api/v1/portal/cases/{case['id']}", headers=client.h).status_code == 404


def test_retrieval_is_scoped_to_org_and_case(api):
    a, case, doc, _ = _firm_case(api)
    with session_factory()() as db:
        assert case_index.search(db, organization_id="other-org", case_id=case["id"], query="arrested").hits == []
        mine = case_index.search(db, organization_id=a.user["organizationId"], case_id=case["id"], query="arrested").hits
        assert mine
        assert case_index.get_chunks(db, organization_id=a.user["organizationId"], case_id="other-case", chunk_ids=[mine[0].chunk_id]) == []
