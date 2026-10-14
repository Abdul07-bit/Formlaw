from __future__ import annotations

from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import Conflict, Forbidden, RateLimited, Unauthorized
from ...db.base import utcnow
from ...db.session import get_db
from ...models import Lawyer, Membership, Organization, User
from ...schemas.auth import DemoLoginIn, LoginIn, RegisterIn, SessionOut, UserOut
from ...schemas.common import Ok
from ...security import rate_limit
from ...security.deps import Principal, current_principal
from ...security.passwords import check_password_policy, hash_password, verify_password
from ...security.tokens import REFRESH_COOKIE, create_access_token, issue_refresh_token, revoke_refresh_token, rotate_refresh_token
from ...services import audit
from ...services.serializers import user_out

router = APIRouter(prefix="/auth", tags=["auth"])
LOCK_AFTER, LOCK_MINUTES = 5, 15
DEMO_EMAILS = {"client": "client@demo.formlaw.in", "lawyer": "lawyer@demo.formlaw.in", "admin": "admin@demo.formlaw.in",
               "compliance": "compliance@demo.formlaw.in"}


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_csrf_header(request: Request) -> None:
    # Cookie-authenticated endpoints need a custom header, which cross-site forms cannot send.
    if request.headers.get("x-requested-with") != "formlaw":
        raise Forbidden("Missing CSRF header", code="csrf")


def _session(db: Session, response: Response, user: User, family: str | None = None, refresh: str | None = None) -> dict:
    s = get_settings()
    token, ttl = create_access_token(user)
    refresh = refresh or issue_refresh_token(db, user.id, family)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_days * 86400, httponly=True, secure=s.cookie_secure,
                        samesite="strict", path="/api/v1/auth")
    return {"access_token": token, "expires_in": ttl, "user": user_out(db, user)}


@router.post("/register", response_model=SessionOut, status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    rate_limit.hit("auth", _ip(request))
    email = body.email.lower()
    check_password_policy(body.password, email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise Conflict("An account with this email already exists", code="email_taken")
    if body.role == "lawyer":
        org = Organization(name=body.firm_name or f"{body.name} — Chambers", type="law_firm" if body.firm_name else "individual")
    else:
        org = Organization(name=f"{body.name} (personal)", type="individual")
    db.add(org)
    db.flush()
    user = User(organization_id=org.id, role=body.role, email=email, name=body.name, city=body.city, phone=body.phone,
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    if body.role == "lawyer":
        db.add(Lawyer(user_id=user.id, name=body.name, city=body.city or "", languages=["English"]))
    audit.record(db, action="auth.register", result="success", actor=user, resource_type="user", resource_id=user.id, ip=_ip(request))
    return _session(db, response, user)


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    rate_limit.hit("auth", _ip(request))
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    now = utcnow()
    if user and user.locked_until and user.locked_until.replace(tzinfo=user.locked_until.tzinfo or timezone.utc) > now:
        audit.record(db, action="auth.login", result="denied", actor=user, risk="MEDIUM", detail="account locked", ip=_ip(request))
        raise RateLimited("Too many failed attempts. Try again later.")
    if not user or user.status != "active" or not verify_password(body.password, user.password_hash if user else None):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= LOCK_AFTER:
                user.locked_until, user.failed_logins = now + timedelta(minutes=LOCK_MINUTES), 0
                audit.security_event(db, kind="auth_abuse", source="login", snippet="Repeated failed logins - account temporarily locked",
                                     actions=["Account locked for 15 minutes", "Security event logged"], risk="MEDIUM", actor_id=user.id)
            db.commit()  # persist the counter even though the request fails
        audit.record(db, action="auth.login", result="denied", risk="MEDIUM", ip=_ip(request))
        db.commit()
        raise Unauthorized("Invalid email or password", code="invalid_credentials")
    user.failed_logins, user.locked_until = 0, None
    audit.record(db, action="auth.login", result="success", actor=user, ip=_ip(request))
    return _session(db, response, user)


@router.post("/demo", response_model=SessionOut, summary="Sign in as a DEMO persona (DEMO_MODE only)")
def demo_login(body: DemoLoginIn, request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    if not get_settings().demo_mode:
        raise Forbidden("Demo sign-in is disabled", code="demo_disabled")
    rate_limit.hit("auth", _ip(request))
    user = db.scalar(select(User).where(User.email == DEMO_EMAILS[body.persona], User.is_demo.is_(True)))
    if not user:
        raise Unauthorized("Demo data not seeded. Run: python -m database.seeds.seed", code="demo_not_seeded")
    audit.record(db, action="auth.demo_login", result="success", actor=user, ip=_ip(request))
    return _session(db, response, user)


@router.post("/refresh", response_model=SessionOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    _require_csrf_header(request)
    rate_limit.hit("auth", _ip(request))
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise Unauthorized("No session", code="no_session")
    user, new_refresh = rotate_refresh_token(db, token)
    return _session(db, response, user, refresh=new_refresh)


@router.post("/logout", response_model=Ok)
def logout(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    _require_csrf_header(request)
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        revoke_refresh_token(db, token)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(p: Principal = Depends(current_principal), db: Session = Depends(get_db, scope="function")):
    return user_out(db, p.user)
