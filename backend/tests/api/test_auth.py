"""Authentication: sessions, refresh rotation and reuse detection, CSRF, lockout, token tampering (carried over from v1)."""
from datetime import timedelta

from app.db import session as db_session
from app.db.base import utcnow
from app.models import User
from app.security.tokens import REFRESH_COOKIE
from tests.helpers import PASSWORD

CSRF = {"x-requested-with": "formlaw"}


def test_register_login_me(api):
    s = api.register("client", email="asha@example.com")
    assert s.user["role"] == "client"
    r = api.c.post("/api/v1/auth/login", json={"email": "ASHA@example.com", "password": PASSWORD})
    assert r.status_code == 200
    me = api.c.get("/api/v1/auth/me", headers={"authorization": f"Bearer {r.json()['accessToken']}"})
    assert me.json()["email"] == "asha@example.com"


def test_refresh_cookie_is_httponly_strict(api):
    r = api.c.post("/api/v1/auth/register", json={"name": "A B", "email": "c@example.com", "password": PASSWORD, "role": "client"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie


def test_admin_cannot_self_register(api):
    r = api.c.post("/api/v1/auth/register", json={"name": "Eve", "email": "e@example.com", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 422


def test_weak_password_rejected(api):
    r = api.c.post("/api/v1/auth/register", json={"name": "Eve", "email": "e@example.com", "password": "password123", "role": "client"})
    assert r.status_code == 422


def test_duplicate_email(api):
    api.register(email="dup@example.com")
    r = api.c.post("/api/v1/auth/register", json={"name": "X Y", "email": "dup@example.com", "password": PASSWORD, "role": "client"})
    assert r.status_code == 409


def test_login_does_not_reveal_whether_account_exists(api):
    api.register(email="real@example.com")
    a = api.c.post("/api/v1/auth/login", json={"email": "real@example.com", "password": "Wrong-Pass-99"})
    b = api.c.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "Wrong-Pass-99"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


def test_brute_force_lockout(api):
    api.register(email="victim@example.com")
    for _ in range(5):
        api.c.post("/api/v1/auth/login", json={"email": "victim@example.com", "password": "Wrong-Pass-99"})
    # Even the right password is refused while locked.
    r = api.c.post("/api/v1/auth/login", json={"email": "victim@example.com", "password": PASSWORD})
    assert r.status_code == 429


def test_ip_rate_limit_on_auth(api):
    codes = [api.c.post("/api/v1/auth/login", json={"email": f"n{i}@example.com", "password": "Wrong-Pass-99"}).status_code for i in range(12)]
    assert 429 in codes


def test_refresh_rotation_and_reuse_detection(api):
    api.register(email="rot@example.com")
    old = api.c.cookies.get(REFRESH_COOKIE)
    r1 = api.c.post("/api/v1/auth/refresh", headers=CSRF)
    assert r1.status_code == 200
    new = api.c.cookies.get(REFRESH_COOKIE)
    assert new and new != old
    # Replay of the rotated token → whole family revoked, including the newest token.
    api.c.cookies.set(REFRESH_COOKIE, old, path="/api/v1/auth")
    assert api.c.post("/api/v1/auth/refresh", headers=CSRF).json()["error"]["code"] == "refresh_reuse_detected"
    api.c.cookies.set(REFRESH_COOKIE, new, path="/api/v1/auth")
    assert api.c.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401


def test_refresh_requires_csrf_header(api):
    api.register(email="csrf@example.com")
    assert api.c.post("/api/v1/auth/refresh").status_code == 403


def test_logout_revokes_refresh(api):
    api.register(email="out@example.com")
    assert api.c.post("/api/v1/auth/logout", headers=CSRF).status_code == 200
    assert api.c.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401


def test_tampered_and_missing_tokens(api):
    s = api.register()
    assert api.c.get("/api/v1/auth/me").status_code == 401
    bad = s.token[:-4] + ("AAAA" if not s.token.endswith("AAAA") else "BBBB")
    assert api.c.get("/api/v1/auth/me", headers={"authorization": f"Bearer {bad}"}).status_code == 401
    import jwt
    forged = jwt.encode({"sub": s.user["id"], "role": "admin", "typ": "access"}, "not-the-secret", algorithm="HS256")
    assert api.c.get("/api/v1/auth/me", headers={"authorization": f"Bearer {forged}"}).status_code == 401
    none_alg = jwt.encode({"sub": s.user["id"], "role": "admin", "typ": "access"}, None, algorithm="none")
    assert api.c.get("/api/v1/auth/me", headers={"authorization": f"Bearer {none_alg}"}).status_code == 401


def test_role_change_invalidates_old_tokens(api):
    s = api.register()
    with db_session.session_factory()() as db:
        db.get(User, s.user["id"]).role = "client"
        db.commit()
    assert api.c.get("/api/v1/auth/me", headers=s.h).json()["error"]["code"] == "role_changed"


def test_disabled_account_rejected(api):
    s = api.register()
    with db_session.session_factory()() as db:
        db.get(User, s.user["id"]).status = "disabled"
        db.commit()
    assert api.c.get("/api/v1/auth/me", headers=s.h).status_code == 401


def test_demo_login_requires_seed(api, seeded):
    assert api.demo("client").user["isDemo"] is True
