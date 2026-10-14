"""
Operator commands (run from backend/).

    python -m app.manage create-staff --role compliance --email reviewer@example.org --name "A. Reviewer"
    python -m app.manage disable-user --email reviewer@example.org

Staff accounts (admin, compliance) are never self-registered. The password is read from FORMLAW_NEW_PASSWORD or
prompted for (never passed on the command line, where it would land in shell history).
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from .db.session import session_factory
from .models import Membership, Organization, User
from .security.passwords import check_password_policy, hash_password
from .services import audit

STAFF_ORG = "FormLaw Platform"


def create_staff(role: str, email: str, name: str, password: str) -> str:
    email = email.strip().lower()
    check_password_policy(password, email)
    with session_factory()() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit(f"An account with {email} already exists")
        org = db.scalar(select(Organization).where(Organization.name == STAFF_ORG, Organization.type == "platform"))
        if not org:
            org = Organization(name=STAFF_ORG, type="platform")
            db.add(org)
            db.flush()
        u = User(organization_id=org.id, role=role, email=email, name=name, password_hash=hash_password(password))
        db.add(u)
        db.flush()
        db.add(Membership(organization_id=org.id, user_id=u.id, role="member"))
        audit.record(db, action="staff.create", result="success", resource_type="user", resource_id=u.id, risk="HIGH",
                     detail=f"role={role} via manage.py")
        db.commit()
        return u.id


def disable_user(email: str) -> None:
    with session_factory()() as db:
        u = db.scalar(select(User).where(User.email == email.strip().lower()))
        if not u:
            raise SystemExit("No such user")
        u.status = "disabled"
        audit.record(db, action="user.disable", result="success", resource_type="user", resource_id=u.id, risk="HIGH", detail="via manage.py")
        db.commit()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m app.manage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-staff", help="create an admin or compliance reviewer account")
    c.add_argument("--role", choices=["admin", "compliance"], required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--name", required=True)
    d = sub.add_parser("disable-user", help="disable an account (tokens stop working on the next request)")
    d.add_argument("--email", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "create-staff":
        pw = os.environ.get("FORMLAW_NEW_PASSWORD") or getpass.getpass("Password: ")
        print(f"Created {a.role} account {a.email} ({create_staff(a.role, a.email, a.name, pw)})")
    elif a.cmd == "disable-user":
        disable_user(a.email)
        print(f"Disabled {a.email}")


if __name__ == "__main__":
    main(sys.argv[1:])
