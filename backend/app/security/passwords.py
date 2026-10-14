"""Password hashing with scrypt (stdlib, memory-hard). Format: scrypt$n$r$p$salt$hash (base64)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from ..core.errors import Unprocessable

_N, _R, _P, _LEN = 2**14, 8, 1, 32
_COMMON = {"password", "password123", "1234567890", "qwertyuiop", "letmein123", "formlaw123", "iloveyou12", "admin12345"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_LEN)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        # Burn comparable time so unknown accounts are not distinguishable by latency.
        hashlib.scrypt(password.encode(), salt=b"0" * 16, n=_N, r=_R, p=_P, dklen=_LEN)
        return False
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(base64.b64decode(digest)))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def check_password_policy(password: str, email: str = "") -> None:
    problems = []
    if len(password) < 10:
        problems.append("at least 10 characters")
    if len(password) > 128:
        problems.append("at most 128 characters")
    if password.lower() in _COMMON or len(set(password)) < 4:
        problems.append("not a common or repetitive password")
    if email and email.split("@")[0].lower() in password.lower() and len(email.split("@")[0]) >= 4:
        problems.append("not containing your email name")
    if problems:
        raise Unprocessable("Password must be " + ", ".join(problems) + ".", code="weak_password")
