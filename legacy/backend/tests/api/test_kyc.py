from pathlib import Path

from app.core.config import get_settings
from tests.helpers import make_pdf

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def _kyc_files():
    return [("degreeCertificate", ("degree.pdf", make_pdf(["LL.B degree"]), "application/pdf")),
            ("idCard", ("bar-id.png", PNG, "image/png")),
            ("selfie", ("selfie.png", PNG + b"selfie-bytes-unique", "image/png"))]


def _lawyer_ready(api):
    s = api.register("lawyer", name="Adv. Test Lawyer")
    r = api.c.patch("/api/v1/lawyers/me", json={"barCouncil": "Bar Council of Delhi", "enrolmentNo": "D/123/2020",
                                                 "practiceAreas": ["Criminal"], "consultationFee": 1000}, headers=s.h)
    assert r.status_code == 200, r.text
    return s


def test_kyc_flow_demo_provider_then_admin_decision(api, seeded):
    s = _lawyer_ready(api)
    r = api.c.post("/api/v1/kyc/submissions", data={"idType": "Bar Council ID"}, files=_kyc_files(), headers=s.h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kyc"] == "pending"
    sub = body["kycSubmission"]
    assert sub["provider"] == "DEMO VERIFICATION PROVIDER" and all(c["demo"] for c in sub["checks"])
    assert sub["faceMatchScore"] is None  # demo provider does not invent a score
    assert {c["type"] for c in sub["checks"]} == {"qualification", "government_id", "professional_registration", "face_match"}

    # Not in the public directory until an admin verifies.
    assert body["id"] not in {l["id"] for l in api.c.get("/api/v1/lawyers").json()}

    admin = api.demo("admin")
    assert api.c.post(f"/api/v1/admin/kyc/{body['id']}/decision", json={"approve": True, "note": ""}, headers=admin.h).status_code == 422
    r = api.c.post(f"/api/v1/admin/kyc/{body['id']}/decision", json={"approve": True, "note": "Checked Bar Council roll manually"}, headers=admin.h)
    assert r.json()["kyc"] == "verified"
    assert body["id"] in {l["id"] for l in api.c.get("/api/v1/lawyers").json()}


def test_selfie_is_not_stored(api, seeded):
    s = _lawyer_ready(api)
    api.c.post("/api/v1/kyc/submissions", data={"idType": "Aadhaar"}, files=_kyc_files(), headers=s.h)
    stored = b"".join(p.read_bytes() for p in Path(get_settings().storage_dir).rglob("*") if p.is_file())
    assert b"selfie-bytes-unique" not in stored


def test_lawyer_cannot_self_verify(api):
    s = _lawyer_ready(api)
    for payload in ({"kyc": "verified"}, {"verificationStatus": "verified"}, {"profileStatus": "published"}, {"rating": 5}):
        assert api.c.patch("/api/v1/lawyers/me", json=payload, headers=s.h).status_code == 422
    assert api.c.get("/api/v1/lawyers/me", headers=s.h).json()["kyc"] == "not_started"


def test_editing_credentials_reopens_verification(api, seeded):
    s = _lawyer_ready(api)
    lawyer_id = api.c.post("/api/v1/kyc/submissions", data={"idType": "PAN"}, files=_kyc_files(), headers=s.h).json()["id"]
    admin = api.demo("admin")
    api.c.post(f"/api/v1/admin/kyc/{lawyer_id}/decision", json={"approve": True, "note": "ok"}, headers=admin.h)
    r = api.c.patch("/api/v1/lawyers/me", json={"enrolmentNo": "D/999/2021"}, headers=s.h).json()
    assert r["kyc"] == "pending" and r["profileStatus"] == "draft"


def test_kyc_rejects_bad_files(api):
    s = _lawyer_ready(api)
    files = _kyc_files()
    files[2] = ("selfie", ("selfie.png", b"not an image", "image/png"))
    assert api.c.post("/api/v1/kyc/submissions", data={"idType": "PAN"}, files=files, headers=s.h).status_code == 422


def test_lawyer_case_history_pii_guard(api):
    s = _lawyer_ready(api)
    base = {"title": "State v. A.B. (anonymised)", "area": "Criminal", "court": "Delhi High Court", "year": 2024, "outcome": "Bail granted",
            "summary": "Bail granted after delay in production before magistrate.", "keywords": ["bail"]}
    assert api.c.post("/api/v1/lawyers/me/cases", json=base, headers=s.h).status_code == 201
    leak = dict(base, summary="Client Ramesh, phone 9876543210, email ramesh@example.com, was granted bail.")
    assert api.c.post("/api/v1/lawyers/me/cases", json=leak, headers=s.h).json()["error"]["code"] == "pii_detected"
    # Unverified history is not public.
    assert all(c["verified"] for c in api.c.get("/api/v1/lawyer-cases").json())
