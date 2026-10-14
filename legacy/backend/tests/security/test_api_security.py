"""SQL injection, XSS, error hygiene, headers, rate limits, data exposure."""
import pytest


@pytest.mark.parametrize("payload", ["' OR 1=1 --", "x'; DROP TABLE users; --", "\" OR \"\"=\""])
def test_sql_injection_is_inert(api, payload):
    s = api.register()
    r = api.c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": payload})
    assert r.status_code == 401
    case = api.case(s, f"Matter {payload}")
    assert case["title"] == f"Matter {payload}"
    assert api.c.get(f"/api/v1/cases/{payload}", headers=s.h).status_code == 404
    assert api.c.get("/api/v1/lawyers", params={"city": payload}).json() == []
    assert api.c.get("/api/v1/auth/me", headers=s.h).status_code == 200  # users table intact


def test_xss_stored_as_inert_text(api):
    s = api.register()
    case = api.case(s, "<img src=x onerror=alert(1)>")
    r = api.c.get(f"/api/v1/cases/{case['id']}", headers=s.h)
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["title"] == "<img src=x onerror=alert(1)>"  # returned as data; React renders text, never HTML


def test_security_headers(client):
    r = client.get("/api/v1/health")
    for h, v in {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer", "cache-control": "no-store"}.items():
        assert r.headers[h] == v
    assert r.headers["x-request-id"]


def test_errors_are_structured_and_leak_nothing(api):
    r = api.c.get("/api/v1/cases/abc")
    body = r.json()
    assert r.status_code == 401 and set(body["error"]) >= {"code", "message", "request_id"}
    v = api.c.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert v.status_code == 422 and v.json()["error"]["code"] == "validation_error"
    assert "Traceback" not in v.text and "sqlalchemy" not in v.text.lower()


def test_cors_rejects_unknown_origin(client):
    r = client.options("/api/v1/health", headers={"origin": "https://evil.example", "access-control-request-method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_public_directory_exposes_no_private_fields(api, seeded):
    lawyers = api.c.get("/api/v1/lawyers").json()
    assert lawyers and all("kycSubmission" not in l or l["kycSubmission"] is None for l in lawyers)
    assert all(l["isDemo"] and l["enrolmentNo"].startswith("DEMO-") for l in lawyers)
    assert all("email" not in l and "userId" not in l for l in lawyers)


def test_agent_rate_limit(api, seeded):
    s = api.register()
    case = api.case(s)
    api.upload(s, case["id"], "a.txt", b"[[PAGE 1]]\nThe accused was arrested on 14 March 2026.", "text/plain")
    codes = [api.c.post(f"/api/v1/cases/{case['id']}/chat", json={"question": "arrest?"}, headers=s.h).status_code for _ in range(22)]
    assert codes.count(429) >= 1


def test_request_body_limit(client):
    r = client.post("/api/v1/auth/login", content=b"x", headers={"content-length": str(200 * 1024 * 1024), "content-type": "application/json"})
    assert r.status_code == 413


def test_demo_login_disabled_outside_demo_mode(api, seeded, monkeypatch):
    from app.core import config
    s = config.get_settings()
    monkeypatch.setattr(config, "get_settings", lambda: type(s)(**{**vars(s), "demo_mode": False}))
    import app.api.v1.auth as auth_mod
    monkeypatch.setattr(auth_mod, "get_settings", config.get_settings)
    assert api.c.post("/api/v1/auth/demo", json={"persona": "admin"}).status_code == 403
