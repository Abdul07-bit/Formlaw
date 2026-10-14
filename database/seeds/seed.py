"""
DEMO DATA seeder (DEMO_MODE only). Everything created here is synthetic and flagged `is_demo`.

    cd backend && python ../database/seeds/seed.py

Creates: a demo law firm with two lawyers, a client, an admin, five verified demo lawyers for matching (enrolment
numbers DEMO-xxxx), the synthetic matters "State v. Arjun Kumar" and "ABC Components — Supply Agreement", a pending
client request, and writes demo upload files (including a malicious affidavit) to demo/.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # type: ignore[import-not-found]  # noqa: E402,F401
assert app is not None
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import demo_documents as D  # noqa: E402
from app.db.base import utcnow  # type: ignore[import-not-found]  # noqa: E402
from app.db.session import session_factory  # type: ignore[import-not-found]  # noqa: E402
from app.ingestion.case_documents import ingest  # type: ignore[import-not-found]  # noqa: E402
from app.models import (Case, CaseMember, ClientUpdate, ConnectionPolicy, Connection, Intake, Lawyer, LawyerPracticeArea,  # noqa: E402  # type: ignore[import-not-found]
                        Membership, Organization, User, VerificationEvent)
from app.security.passwords import hash_password  # type: ignore[import-not-found]  # noqa: E402

DEMO_PASSWORD = "FormLaw-Demo-2026"
DEMO_DIR = ROOT / "demo"


def _user(db: Session, org: Organization, email: str, name: str, role: str, city: str, member_role: str = "owner") -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u:
        return u
    u = User(organization_id=org.id, role=role, email=email, name=name, city=city, password_hash=hash_password(DEMO_PASSWORD), is_demo=True)
    db.add(u)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=u.id, role=member_role))
    return u


def _org(db: Session, name: str, type_: str) -> Organization:
    o = db.scalar(select(Organization).where(Organization.name == name))
    if not o:
        o = Organization(name=name, type=type_)
        db.add(o)
        db.flush()
    return o


def _lawyer(db: Session, user: User, *, areas: list[str], verified: bool, city: str, state: str, years: int, langs: list[str],
            headline: str, n: int) -> Lawyer:
    # Synthetic, self-declared fees (INR) so the demo can show budget fit. Not real market rates.
    fee = 1500 + 500 * (n % 5)
    l = db.scalar(select(Lawyer).where(Lawyer.user_id == user.id))
    if l:
        if l.is_demo and l.fee_range_min is None:
            l.consultation_fee, l.fee_range_min, l.fee_range_max = fee, fee * 10, fee * 40
        return l
    l = Lawyer(user_id=user.id, name=user.name, headline=headline, city=city, state=state, jurisdictions=[f"{state} courts"],
               bar_council=f"Bar Council of {state}", enrolment_number=f"DEMO-{n:04d}", experience_years=years, languages=langs,
               education=["LL.B. (demo record)"], bio="Synthetic demo profile.", is_demo=True,
               consultation_fee=fee, fee_range_min=fee * 10, fee_range_max=fee * 40,
               verification_status="VERIFIED" if verified else "NOT_STARTED", profile_status="published" if verified else "draft",
               verified_at=utcnow() if verified else None, verification_expires_at=utcnow() + timedelta(days=365) if verified else None)
    db.add(l)
    db.flush()
    for a in areas:
        db.add(LawyerPracticeArea(lawyer_id=l.id, area=a, verified=verified))
    if verified:
        db.add(VerificationEvent(lawyer_id=l.id, from_status="NOT_STARTED", to_status="VERIFIED", actor_role="system",
                                 reason="SYNTHETIC demo record created by the seeder; no verification was performed"))
    return l


DEMO_DISCLOSURES = [
    "DEMO ONLY: this connection flow uses synthetic advocates and has not been reviewed for compliance with Bar Council of India rules.",
    "FormLaw is a technology platform, not a law firm, and does not give legal advice or recommend an advocate.",
    "Suggestions are based on verified practice area, location and language only. They are not a ranking and do not predict any outcome.",
    "No advocate pays FormLaw to appear here, and FormLaw takes no referral fee.",
    "Fees shown are declared by each advocate and are not verified or negotiated by FormLaw. Agree fees directly in writing.",
    "If you send a request, the advocate sees your matter summary and the number of documents you uploaded. Your documents are "
    "shared only if they accept.",
]


def seed_demo_connection_policy(db: Session) -> None:
    """A DEMO_ONLY policy. Honoured only while DEMO_MODE is on (never in production); it is not a compliance review."""
    current = db.scalar(select(ConnectionPolicy).where(ConnectionPolicy.review_status == "DEMO_ONLY")
                        .order_by(ConnectionPolicy.version.desc()).limit(1))
    if current and current.show_fees and current.required_disclosures == DEMO_DISCLOSURES:
        return
    if current:  # policies are append-only: an older demo version is superseded, never edited
        current.review_status = "SUPERSEDED"
    version = (db.scalar(select(ConnectionPolicy.version).order_by(ConnectionPolicy.version.desc()).limit(1)) or 0) + 1
    db.add(ConnectionPolicy(jurisdiction="IN", version=version, public_discovery_enabled=True, matching_enabled=True,
                            client_requests_enabled=True, show_fees=True,
                            visible_profile_fields=["headline", "city", "state", "jurisdictions", "languages", "experienceYears",
                                                    "acceptingClients", "verifiedAreas", "practiceAreas", "judicialStatusVerified",
                                                    "consultationFee", "feeRange"],
                            required_disclosures=DEMO_DISCLOSURES, professional_rules=["DEMO — not reviewed"],
                            rationale="Synthetic demonstration environment only.", review_status="DEMO_ONLY",
                            review_reference="NONE — DEMO", review_note="Not a legal or compliance review."))


def seed_demo(db: Session) -> dict[str, int]:
    seed_demo_connection_policy(db)
    firm = _org(db, "Iyer & Mehta Chambers (DEMO)", "law_firm")
    lead = _user(db, firm, "lawyer@demo.formlaw.in", "Adv. Meera Iyer (demo)", "lawyer", "New Delhi")
    assoc = _user(db, firm, "associate@demo.formlaw.in", "Adv. Kabir Mehta (demo)", "lawyer", "New Delhi", "member")
    _lawyer(db, lead, areas=["criminal", "constitutional"], verified=True, city="New Delhi", state="Delhi", years=14,
            langs=["English", "Hindi"], headline="Criminal trials and bail (demo profile)", n=1)
    _lawyer(db, assoc, areas=["contract", "corporate"], verified=False, city="New Delhi", state="Delhi", years=4,
            langs=["English"], headline="Commercial contracts (demo profile)", n=2)
    platform = _org(db, "FormLaw Platform", "platform")
    _user(db, platform, "admin@demo.formlaw.in", "Platform Admin (demo)", "admin", "Bengaluru")
    _user(db, platform, "compliance@demo.formlaw.in", "Compliance Reviewer (demo)", "compliance", "Bengaluru", "member")
    client_org = _org(db, "Sunita Kumar (personal, demo)", "individual")
    client = _user(db, client_org, "client@demo.formlaw.in", "Sunita Kumar (demo)", "client", "New Delhi")

    others = [("Adv. Farah Khan (demo)", ["employment", "civil"], "Pune", "Maharashtra", 11, ["English", "Hindi", "Marathi"]),
              ("Adv. Joseph Mathew (demo)", ["property", "civil"], "Kochi", "Kerala", 18, ["English", "Malayalam"]),
              ("Adv. Ananya Rao (demo)", ["contract", "corporate", "consumer"], "Bengaluru", "Karnataka", 9, ["English", "Kannada"]),
              ("Adv. Vikram Singh (demo)", ["criminal", "cyber"], "New Delhi", "Delhi", 7, ["English", "Hindi", "Punjabi"]),
              ("Adv. Lakshmi Narayanan (demo)", ["family", "civil"], "Chennai", "Tamil Nadu", 21, ["English", "Tamil"])]
    for i, (name, areas, city, state, yrs, langs) in enumerate(others, start=3):
        o = _org(db, f"{name} — Chambers", "individual")
        u = _user(db, o, f"lawyer{i}@demo.formlaw.in", name, "lawyer", city)
        _lawyer(db, u, areas=areas, verified=True, city=city, state=state, years=yrs, langs=langs,
                headline=f"{areas[0].capitalize()} practice (demo profile)", n=i)
    db.flush()

    made = 0
    if not db.scalar(select(Case.id).where(Case.organization_id == firm.id, Case.title == "State v. Arjun Kumar")):
        c = Case(organization_id=firm.id, created_by=lead.id, reference="FL-2026-0001", title="State v. Arjun Kumar", matter_type="criminal",
                 description="Defence brief for the accused in a phone-snatching FIR (SYNTHETIC DEMO MATTER).", jurisdiction="Delhi",
                 court="Metropolitan Magistrate, Saket Courts", client_name="Sunita Kumar (mother of the accused)", is_demo=True)
        db.add(c)
        db.flush()
        db.add_all([CaseMember(case_id=c.id, user_id=lead.id, role="lead"), CaseMember(case_id=c.id, user_id=assoc.id, role="member"),
                    CaseMember(case_id=c.id, user_id=client.id, role="client")])
        for name, pages in (("FIR_DEMO-118-2026.pdf", D.FIR), ("Remand_Report.pdf", D.REMAND), ("Witness_Statement_Neha_Sinha.pdf", D.WITNESS)):
            ingest(db, organization_id=firm.id, case_id=c.id, uploaded_by=lead.id, filename=name, declared_type="application/pdf",
                   data=D.pdf_bytes(pages), is_demo=True)
        db.add(ClientUpdate(case_id=c.id, author_id=lead.id, approval_id="seed", title="Bail application being prepared",
                            body="We have reviewed the FIR and remand report and are preparing the bail application. (Demo update.)"))
        made += 1
    if not db.scalar(select(Case.id).where(Case.organization_id == firm.id, Case.title == "ABC Components — Supply Agreement")):
        c = Case(organization_id=firm.id, created_by=lead.id, reference="FL-2026-0002", title="ABC Components — Supply Agreement",
                 matter_type="contract", description="Review of a master supply agreement for the Buyer (SYNTHETIC DEMO MATTER).",
                 jurisdiction="Maharashtra", client_name="Northwind Retail Pvt Ltd", is_demo=True)
        db.add(c)
        db.flush()
        db.add_all([CaseMember(case_id=c.id, user_id=lead.id, role="lead"), CaseMember(case_id=c.id, user_id=assoc.id, role="member")])
        ingest(db, organization_id=firm.id, case_id=c.id, uploaded_by=lead.id, filename="Master_Supply_Agreement.pdf",
               declared_type="application/pdf", data=D.pdf_bytes(D.CONTRACT), is_demo=True)
        made += 1

    # A client request waiting for the demo lawyer (client portal → lawyer requests flow).
    req_org = _org(db, "Rahul Deshmukh (personal, demo)", "individual")
    req_client = _user(db, req_org, "client2@demo.formlaw.in", "Rahul Deshmukh (demo)", "client", "Pune")
    if not db.scalar(select(Intake.id).where(Intake.client_id == req_client.id)):
        from app.agents.intake.agent import structure  # type: ignore[import-not-found]
        data, engine, flags = structure(D.EMPLOYMENT_INTAKE, {})
        i = Intake(client_id=req_client.id, organization_id=req_org.id, title="Terminated without notice; salary unpaid",
                   description=D.EMPLOYMENT_INTAKE, structured=data | {"engine": engine}, matter_type=data["legal_domain"], city="Pune",
                   urgency=data["urgency"], security_flags=flags, status="matched")
        db.add(i)
        db.flush()
        lead_lawyer = db.scalar(select(Lawyer).where(Lawyer.user_id == lead.id))
        db.add(Connection(intake_id=i.id, client_id=req_client.id, lawyer_id=lead_lawyer.id, client_note="Please advise urgently. (demo)"))

    DEMO_DIR.mkdir(exist_ok=True)
    (DEMO_DIR / "Affidavit_Suresh_Pal_MALICIOUS_DEMO.pdf").write_bytes(D.pdf_bytes(D.AFFIDAVIT))
    (DEMO_DIR / "FIR_DEMO-118-2026.pdf").write_bytes(D.pdf_bytes(D.FIR))
    (DEMO_DIR / "Remand_Report.pdf").write_bytes(D.pdf_bytes(D.REMAND))
    (DEMO_DIR / "Master_Supply_Agreement.pdf").write_bytes(D.pdf_bytes(D.CONTRACT))
    return {"cases": made}


def seed_sources(db: Session) -> int:
    """Legal source registry (terms audit) — see legal-data/source-config/sources.json."""
    from app.ingestion import registry  # type: ignore[import-not-found]
    return len(registry.sync(db))


def main() -> None:
    from app.core.config import get_settings  # type: ignore[import-not-found]
    if not get_settings().demo_mode:
        raise SystemExit("DEMO_MODE is off; refusing to seed demo data.")
    with session_factory()() as db:
        out = seed_demo(db)
        sources = seed_sources(db)
        db.commit()
    print(f"Seeded SYNTHETIC demo data ({out['cases']} new matters); {sources} legal sources synced.")
    print(f"Demo sign-in password for every demo account: {DEMO_PASSWORD}")
    print(f"Demo upload files written to {DEMO_DIR}")


if __name__ == "__main__":
    main()
