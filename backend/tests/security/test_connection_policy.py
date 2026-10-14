"""
ConnectionPolicy compliance gate, consent records, and the advocate verification lifecycle (suspension, history).

Advocate discovery, matching and client→advocate requests must be unavailable until a human compliance reviewer approves
a specific policy version; the gate is enforced at request time and again when a client's approval executes.
"""
from __future__ import annotations

import dataclasses

from sqlalchemy import select

from app.db import session as db_session
from app.models import VERIFICATION_TYPES, Connection, Consent, Membership, Organization, User
from app.policies import connection as connection_policy
from app.security.passwords import hash_password
from tests.helpers import PASSWORD, Session

DISABLED = "connection_feature_disabled"
GOOD_POLICY = {
    "publicDiscoveryEnabled": True, "matchingEnabled": True, "clientRequestsEnabled": True, "showFees": False,
    "visibleProfileFields": ["city", "languages", "verifiedAreas"],
    "requiredDisclosures": ["FormLaw does not recommend or rank advocates.", "No advocate pays to appear here."],
    "professionalRules": ["BCI Rules Part VI Ch. II r.36"], "rationale": "SYNTHETIC test policy for automated tests.",
}
REVIEW = {"approve": True, "reviewReference": "TEST-OPINION-1", "note": "Synthetic test review", "counselReviewed": True}


def _admin(api, email: str, role: str = "admin") -> Session:
    with db_session.session_factory()() as db:
        org = Organization(name=f"Platform {email}", type="platform")
        db.add(org)
        db.flush()
        u = User(organization_id=org.id, role=role, email=email, name="Test Staff", city="Delhi", password_hash=hash_password(PASSWORD))
        db.add(u)
        db.flush()
        db.add(Membership(organization_id=org.id, user_id=u.id, role="owner"))
        db.commit()
    r = api.c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return Session(r.json()["accessToken"], r.json()["user"])


_n = iter(range(1, 10_000))


def _approve_policy(api, body=GOOD_POLICY) -> dict:
    i = next(_n)
    drafter, reviewer = _admin(api, f"drafter{i}@example.com"), _admin(api, f"reviewer{i}@example.com", "compliance")
    draft = api.c.post("/api/v1/admin/connection-policies", json=body, headers=drafter.h)
    assert draft.status_code == 201, draft.text
    r = api.c.post(f"/api/v1/compliance/connection-policies/{draft.json()['id']}/review", json=REVIEW, headers=reviewer.h)
    assert r.status_code == 200, r.text
    return r.json() | {"_reviewer": reviewer}


def _intake(api, client) -> dict:
    r = api.c.post("/api/v1/intakes", json={"title": "Unpaid salary", "city": "Pune",
                                            "description": "My employer terminated me without notice and has not paid two months of salary."},
                   headers=client.h)
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ safe default
def test_everything_is_off_without_a_reviewed_policy(api):
    p = api.c.get("/api/v1/connection-policy").json()
    assert p["source"] == "default" and not any(p["features"].values())
    for path in ("/api/v1/lawyers", "/api/v1/lawyers/some-id"):
        r = api.c.get(path)
        assert r.status_code == 403 and r.json()["error"]["code"] == DISABLED
    client = api.register("client")
    intake = _intake(api, client)
    r = api.c.post("/api/v1/matching", json={"intakeId": intake["id"]}, headers=client.h)
    assert r.status_code == 403 and r.json()["error"]["code"] == DISABLED
    r = api.c.post(f"/api/v1/intakes/{intake['id']}/connect", json={"lawyerId": "x", "policyVersion": 1, "disclosureHash": "0" * 64},
                   headers=client.h)
    assert r.status_code == 403 and r.json()["error"]["code"] == DISABLED
    # The generic approvals endpoint cannot be used to get around the gate.
    r = api.c.post("/api/v1/approvals", json={"action": "connection.request", "resourceId": intake["id"],
                                              "params": {"lawyerId": "x", "policyVersion": "1", "disclosureHash": "0" * 64}}, headers=client.h)
    assert r.status_code == 403 and r.json()["error"]["code"] == DISABLED


def test_demo_policy_is_ignored_outside_demo_mode(api, seeded, monkeypatch):
    assert api.c.get("/api/v1/connection-policy").json()["source"] == "demo"
    off = dataclasses.replace(connection_policy.get_settings(), demo_mode=False)
    monkeypatch.setattr(connection_policy, "get_settings", lambda: off)
    assert api.c.get("/api/v1/connection-policy").json()["source"] == "default"
    assert api.c.get("/api/v1/lawyers").status_code == 403


# ------------------------------------------------------------------ compliance decision point
def test_policy_review_requires_a_compliance_reviewer_counsel_and_disclosures(api):
    a, b = _admin(api, "a@example.com"), _admin(api, "b@example.com", "compliance")
    other_admin = _admin(api, "c@example.com")
    r = api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY | {"requiredDisclosures": []}, headers=a.h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "disclosures_required"
    r = api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY | {"visibleProfileFields": ["email"]}, headers=a.h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "field_not_allowed"
    r = api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY | {"visibleProfileFields": ["consultationFee"]}, headers=a.h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "field_not_allowed"  # fees need showFees
    draft = api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY, headers=a.h).json()
    assert api.c.get("/api/v1/connection-policy").json()["source"] == "default"  # a draft changes nothing
    review = f"/api/v1/compliance/connection-policies/{draft['id']}/review"
    for admin in (a, other_admin):  # administrators can never approve — not even one who did not draft it
        assert api.c.post(review, json=REVIEW, headers=admin.h).status_code == 403
    assert api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY, headers=b.h).status_code == 403  # reviewers don't draft
    r = api.c.post(review, json=REVIEW | {"counselReviewed": False}, headers=b.h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "counsel_review_required"
    assert api.c.post(review, json=REVIEW, headers=b.h).json()["reviewStatus"] == "APPROVED"
    assert api.c.get("/api/v1/connection-policy").json()["source"] == "approved"
    # Lawyers and clients cannot touch policies.
    lawyer = api.register()
    assert api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY, headers=lawyer.h).status_code == 403
    assert api.c.get("/api/v1/compliance/connection-policies", headers=lawyer.h).status_code == 403


def test_compliance_reviewer_cannot_review_a_policy_they_drafted_via_role_change(api):
    """Separation of duties holds even if one account somehow drafted and later became a reviewer."""
    a = _admin(api, "switch@example.com")
    draft = api.c.post("/api/v1/admin/connection-policies", json=GOOD_POLICY, headers=a.h).json()
    with db_session.session_factory()() as db:
        db.scalar(select(User).where(User.email == "switch@example.com")).role = "compliance"
        db.commit()
    r = api.c.post("/api/v1/auth/login", json={"email": "switch@example.com", "password": PASSWORD})
    h = {"authorization": f"Bearer {r.json()['accessToken']}"}
    r = api.c.post(f"/api/v1/compliance/connection-policies/{draft['id']}/review", json=REVIEW, headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "separation_of_duties"


def test_staff_accounts_are_created_by_the_operator_command_only(api):
    from app.manage import create_staff
    assert api.c.post("/api/v1/auth/register", json={"name": "Me", "email": "me@example.com", "password": PASSWORD,
                                                     "role": "compliance"}).status_code == 422
    create_staff("compliance", "Officer@Example.com", "Compliance Officer", PASSWORD)
    r = api.c.post("/api/v1/auth/login", json={"email": "officer@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["role"] == "compliance"
    h = {"authorization": f"Bearer {r.json()['accessToken']}"}
    assert api.c.get("/api/v1/compliance/connection-policies", headers=h).status_code == 200
    assert api.c.get("/api/v1/admin/verifications", headers=h).status_code == 403  # no platform administration
    assert api.c.get("/api/v1/cases", headers=h).status_code == 403  # no case content


def test_directory_shows_only_policy_allowed_fields_and_revocation_switches_it_off(api, seeded):
    approved = _approve_policy(api)
    listing = api.c.get("/api/v1/lawyers").json()
    assert listing and all(set(l) <= {"id", "name", "verificationStatus", "isDemo", "experienceSelfDeclared", "feesSelfDeclared",
                                      "city", "languages", "verifiedAreas"} for l in listing)
    assert all("consultationFee" not in l and "feeRange" not in l and "bio" not in l for l in listing)
    assert [l["name"] for l in listing] == sorted(l["name"] for l in listing)  # no ranking
    r = api.c.post(f"/api/v1/compliance/connection-policies/{approved['id']}/revoke", json={"note": "Counsel withdrew opinion"},
                   headers=approved["_reviewer"].h)
    assert r.json()["reviewStatus"] == "REVOKED"
    # The DEMO_ONLY policy from the seed applies again (demo mode); without it the default would apply.
    assert api.c.get("/api/v1/connection-policy").json()["source"] == "demo"


def test_consent_is_recorded_against_the_exact_disclosures(api, seeded):
    client = api.register("client", city="New Delhi")
    intake = _intake(api, client)
    lawyer_id = api.c.post("/api/v1/matching", json={"intakeId": intake["id"]}, headers=client.h).json()["matches"][0]["lawyer"]["id"]
    policy = api.c.get("/api/v1/connection-policy").json()
    r = api.c.post(f"/api/v1/intakes/{intake['id']}/connect", json={"lawyerId": lawyer_id, "policyVersion": policy["version"],
                                                                    "disclosureHash": "f" * 64}, headers=client.h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "policy_changed"
    a = api.c.post(f"/api/v1/intakes/{intake['id']}/connect", json={"lawyerId": lawyer_id, "policyVersion": policy["version"],
                                                                    "disclosureHash": policy["disclosureHash"]}, headers=client.h).json()
    assert api.c.post(f"/api/v1/approvals/{a['approvalId']}/decision", json={"approve": True}, headers=client.h).json()["status"] == "executed"
    with db_session.session_factory()() as db:
        c = db.scalar(select(Consent).where(Consent.subject_id == intake["id"]))
        assert c and c.user_id == client.user["id"] and c.recipient_id == lawyer_id
        assert c.disclosure_hash == policy["disclosureHash"] and c.disclosures == policy["disclosures"]


def test_policy_change_between_request_and_approval_blocks_execution(api, seeded):
    client = api.register("client", city="New Delhi")
    intake = _intake(api, client)
    lawyer_id = api.c.post("/api/v1/matching", json={"intakeId": intake["id"]}, headers=client.h).json()["matches"][0]["lawyer"]["id"]
    policy = api.c.get("/api/v1/connection-policy").json()
    a = api.c.post(f"/api/v1/intakes/{intake['id']}/connect", json={"lawyerId": lawyer_id, "policyVersion": policy["version"],
                                                                    "disclosureHash": policy["disclosureHash"]}, headers=client.h).json()
    _approve_policy(api, GOOD_POLICY | {"requiredDisclosures": ["A different disclosure the client never saw."]})
    r = api.c.post(f"/api/v1/approvals/{a['approvalId']}/decision", json={"approve": True}, headers=client.h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "policy_changed"
    with db_session.session_factory()() as db:
        assert not db.scalar(select(Connection.id).where(Connection.intake_id == intake["id"]))
        assert not db.scalar(select(Consent.id).where(Consent.subject_id == intake["id"]))


def test_advocate_can_decline_but_not_accept_when_requests_are_off(api, seeded):
    lawyer = api.demo("lawyer")
    pending = [r for r in api.c.get("/api/v1/requests", headers=lawyer.h).json() if r["status"] == "requested"]
    assert pending
    approved = _approve_policy(api, GOOD_POLICY | {"clientRequestsEnabled": False, "matchingEnabled": False})
    assert approved["reviewStatus"] == "APPROVED"
    r = api.c.post(f"/api/v1/requests/{pending[0]['id']}/respond", json={"accept": True}, headers=lawyer.h)
    assert r.status_code == 403 and r.json()["error"]["code"] == DISABLED
    r = api.c.post(f"/api/v1/requests/{pending[0]['id']}/respond", json={"accept": False, "note": "Not my practice area"}, headers=lawyer.h)
    assert r.status_code == 200 and r.json()["status"] == "declined"


# ------------------------------------------------------------------ verification lifecycle
def test_no_biometric_verification_type():
    assert "face_match" not in VERIFICATION_TYPES


def test_suspension_hides_profile_and_reinstatement_keeps_original_expiry(api, seeded):
    admin = api.demo("admin")
    lawyer = api.demo("lawyer")
    me = api.c.get("/api/v1/lawyers/profile", headers=lawyer.h).json()
    assert any(l["id"] == me["id"] for l in api.c.get("/api/v1/lawyers").json())
    assert api.c.post(f"/api/v1/admin/verifications/{me['id']}/suspend", json={"note": "x"}, headers=lawyer.h).status_code == 403
    s = api.c.post(f"/api/v1/admin/verifications/{me['id']}/suspend", json={"note": "Bar Council reported suspension"}, headers=admin.h).json()
    assert s["verificationStatus"] == "SUSPENDED" and s["profileStatus"] == "suspended"
    assert not any(l["id"] == me["id"] for l in api.c.get("/api/v1/lawyers").json())
    assert api.c.get(f"/api/v1/lawyers/{me['id']}").status_code == 404
    # A suspended advocate can neither publish nor resubmit around the suspension.
    r = api.c.put("/api/v1/lawyers/profile", json={"publish": True}, headers=lawyer.h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_verified"
    r = api.c.post("/api/v1/lawyers/verification", data={"idType": "PAN"}, headers=lawyer.h,
                   files={"governmentId": ("id.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 64, "image/png"),
                          "qualification": ("q.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 64, "image/png")})
    assert r.status_code == 409 and r.json()["error"]["code"] == "verification_suspended"
    back = api.c.post(f"/api/v1/admin/verifications/{me['id']}/reinstate", json={"note": "Suspension lifted"}, headers=admin.h).json()
    assert back["verificationStatus"] == "VERIFIED" and back["verificationExpiresAt"] == me["verificationExpiresAt"]
    assert back["profileStatus"] == "suspended"  # the advocate decides when to publish again
    r = api.c.post(f"/api/v1/admin/verifications/{me['id']}/reinstate", json={"note": "again"}, headers=admin.h)
    assert r.status_code == 409
    hist = api.c.get(f"/api/v1/admin/verifications/{me['id']}/history", headers=admin.h).json()
    assert {(h["from"], h["to"], h["by"]) for h in hist} >= {("VERIFIED", "SUSPENDED", "admin"), ("SUSPENDED", "VERIFIED", "admin")}


def test_admin_advocate_list_is_admin_only_and_filterable(api, seeded):
    admin = api.demo("admin")
    verified = api.c.get("/api/v1/admin/lawyers?status=verified", headers=admin.h).json()
    assert verified and all(l["verificationStatus"] == "VERIFIED" for l in verified)
    assert api.c.get("/api/v1/admin/lawyers", headers=api.demo("lawyer").h).status_code == 403


def test_illegal_verification_transition_is_rejected(api, seeded):
    admin = api.demo("admin")
    s = api.register()
    r = api.c.post(f"/api/v1/admin/verifications/{s.user['lawyerId']}/suspend", json={"note": "Not verified yet"}, headers=admin.h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_verification_transition"
