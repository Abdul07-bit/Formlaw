"""
Short-lived JWT access tokens (Authorization header) + opaque rotating refresh tokens
(httpOnly SameSite=Strict cookie, only a SHA-256 hash stored server-side).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import Unauthorized
from ..db.base import new_id, utcnow
from ..models import RefreshToken, User

ISSUER, AUDIENCE, ALGO = "formlaw-api", "formlaw-web", "HS256"
REFRESH_COOKIE = "formlaw_refresh"


def create_access_token(user: User) -> tuple[str, int]:
    s = get_settings()
    ttl = s.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user.id, "role": user.role, "org": user.organization_id, "typ": "access",
        "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + timedelta(seconds=ttl), "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm=ALGO), ttl


def decode_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGO], audience=AUDIENCE, issuer=ISSUER,
                            options={"require": ["exp", "iat", "sub", "typ"]})
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("Session expired", code="token_expired") from e
    except jwt.PyJWTError as e:
        raise Unauthorized("Invalid token", code="invalid_token") from e
    if claims.get("typ") != "access":
        raise Unauthorized("Invalid token", code="invalid_token")
    return claims


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(db: Session, user_id: str, family_id: str | None = None) -> str:
    token = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user_id, family_id=family_id or new_id(), token_hash=_hash(token),
                        expires_at=utcnow() + timedelta(days=get_settings().refresh_token_days)))
    db.flush()
    return token


def rotate_refresh_token(db: Session, token: str) -> tuple[User, str]:
    """Exchange a refresh token for a new one. Presenting an already-rotated token revokes its whole family."""
    rec = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    if rec is None:
        raise Unauthorized("Invalid session", code="invalid_refresh")
    if rec.revoked_at is not None:
        # Token reuse: somebody replayed an old token. Kill every session in this family.
        db.execute(update(RefreshToken).where(RefreshToken.family_id == rec.family_id, RefreshToken.revoked_at.is_(None))
                   .values(revoked_at=utcnow()))
        db.commit()
        raise Unauthorized("Session revoked", code="refresh_reuse_detected")
    if _aware(rec.expires_at) < utcnow():
        raise Unauthorized("Session expired", code="refresh_expired")
    user = db.get(User, rec.user_id)
    if user is None or user.status != "active":
        raise Unauthorized("Account unavailable", code="account_inactive")
    new_token = issue_refresh_token(db, user.id, rec.family_id)
    rec.revoked_at = utcnow()
    rec.replaced_by = _hash(new_token)[:36]
    return user, new_token


def revoke_refresh_token(db: Session, token: str) -> None:
    rec = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    if rec and rec.revoked_at is None:
        rec.revoked_at = utcnow()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite drops tzinfo
