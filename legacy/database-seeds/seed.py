"""
Seed DEMO DATA (synthetic) and legal-source configuration. Idempotent.

    cd backend && python ../database/seeds/seed.py

Demo accounts get random, unusable passwords: they can only be entered through POST /api/v1/auth/demo,
which is disabled unless DEMO_MODE=true (always off in production).
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import app  # noqa: E402,F401
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import session_factory  # noqa: E402
from app.models import Lawyer, LawyerCase, LawyerExpertise, Organization, User  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402

DATA = json.loads((Path(__file__).parent / "demo_data.json").read_text(encoding="utf-8"))


def _user(db: Session, email: str, name: str, role: str, city: str | None, org_type: str = "individual") -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u:
        return u
    org = Organization(name=name, type=org_type)
    db.add(org)
    db.flush()
    u = User(organization_id=org.id, role=role, email=email, name=name, city=city, is_demo=True,
             password_hash=hash_password(secrets.token_urlsafe(32)))  # unusable: demo personas use /auth/demo only
    db.add(u)
    db.flush()
    return u


def seed_demo(db: Session) -> dict[str, int]:
    _user(db, "admin@demo.formlaw.in", "Verification Desk (DEMO)", "admin", None, "platform")
    _user(db, "priya@demo.formlaw.in", "Priya Sharma (DEMO)", "client", "New Delhi")
    id_map: dict[str, str] = {}
    for l in DATA["lawyers"]:
        email = "mi@demo.formlaw.in" if l["id"] == "LAW-101" else f"{l['id'].lower()}@demo.formlaw.in"
        u = _user(db, email, l["name"], l["role"], l["city"])
        row = db.scalar(select(Lawyer).where(Lawyer.user_id == u.id))
        if not row:
            row = Lawyer(user_id=u.id, name=l["name"], title=l["title"], professional_status=l["role"], photo_hue=l["photoHue"],
                         city=l["city"], state=l["state"], jurisdiction=l["state"], courts=l["courts"], bar_council=l["barCouncil"],
                         bar_or_registration_number=l["enrolmentNo"], experience_years=l["experienceYears"], languages=l["languages"],
                         consultation_fee=l["consultationFee"], hearing_fee=l["hearingFee"], response_hours=l["responseHours"],
                         bio=l["bio"], rating=l["rating"], reviews=l["reviews"], cases_handled=l["casesHandled"],
                         verification_status="verified", profile_status="published", is_demo=True)
            db.add(row)
            db.flush()
            for area in l["practiceAreas"]:
                db.add(LawyerExpertise(lawyer_id=row.id, practice_area=area, jurisdiction=l["state"], verified=True))
        id_map[l["id"]] = row.id
    added = 0
    for c in DATA["lawyerCases"]:
        lawyer_id = id_map.get(c["lawyerId"])
        if not lawyer_id or db.scalar(select(LawyerCase.id).where(LawyerCase.case_reference == c["title"], LawyerCase.lawyer_id == lawyer_id)):
            continue
        db.add(LawyerCase(lawyer_id=lawyer_id, case_reference=c["title"], legal_category=c["area"], court=c["court"], year=c["year"],
                          outcome=c["outcome"], sections=c["sections"], summary=c["summary"], keywords=c["keywords"],
                          duration_months=c["durationMonths"], verification_status="verified" if c["verified"] else "pending", is_demo=True))
        added += 1
    return {"lawyers": len(id_map), "lawyerCases": added}


def seed_sources(db: Session) -> int:
    """Legal source registry (terms audit) — see legal-data/source-config/sources.json."""
    from app.ingestion import registry

    return len(registry.sync(db))


def main() -> None:
    with session_factory()() as db:
        demo = seed_demo(db)
        sources = seed_sources(db)
        db.commit()
    print(f"Seeded DEMO DATA: {demo['lawyers']} lawyers, {demo['lawyerCases']} new case records; {sources} legal sources synced from the registry.")


if __name__ == "__main__":
    main()
