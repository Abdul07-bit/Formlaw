"""
Conflict-of-interest checks for client requests.

    request created → automated name search in the ADVOCATE'S OWN FIRM → advocate sees names only → CLEARED / CONFLICT
                                                                                │                      └► request declined
                                                                                └► full intake summary disclosed

The automated search is an aid, not a decision: it matches normalised names against the firm's matter client names and
titles. A hit is reported by matter reference only (no title or client name), and the advocate must still confirm.
Names that could identify another firm's clients are never searched or shown.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import Conflict as ConflictError
from ..db.base import utcnow
from ..models import Case, ConflictCheck, Connection, Intake, Lawyer, Notification, User
from ..security.deps import Principal
from . import audit

_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "adv", "advocate", "shri", "sri", "smt", "kumari", "km", "m/s", "ms.", "the",
               "late", "prof", "justice", "hon", "sh", "demo"}
_ORG_SUFFIXES = {"pvt", "private", "ltd", "limited", "llp", "inc", "co", "corp", "corporation", "company"}


def normalise(name: str) -> tuple[str, ...]:
    s = unicodedata.normalize("NFKC", name).lower()
    s = re.sub(r"\(.*?\)", " ", s)  # "(demo)", "(mother of the accused)"
    toks = [t for t in re.findall(r"[a-z0-9]+", s) if t not in _HONORIFICS and t not in _ORG_SUFFIXES]
    return tuple(toks)


def _matches(needle: tuple[str, ...], hay: tuple[str, ...]) -> bool:
    """Whole-name match, or every token of a (2+ token) name appearing in order inside the other text."""
    if not needle or not hay:
        return False
    if needle == hay:
        return True
    if len(needle) < 2:
        return False
    n = len(needle)
    return any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


def names_for(db: Session, intake: Intake, client: User | None) -> list[dict]:
    out = [{"name": client.name, "role": "client"}] if client else []
    seen = {normalise(client.name)} if client else set()
    for p in intake.declared_parties or []:
        key = normalise(p)
        if key and key not in seen:
            seen.add(key)
            out.append({"name": p, "role": "other_party"})
    return out


def search(db: Session, organization_id: str, names: list[dict]) -> list[dict]:
    hits = []
    for c in db.scalars(select(Case).where(Case.organization_id == organization_id, Case.deleted_at.is_(None))):
        fields = {"client": normalise(c.client_name or ""), "title": normalise(c.title or "")}
        for n in names:
            key = normalise(n["name"])
            for field, hay in fields.items():
                if _matches(key, hay):
                    hits.append({"caseId": c.id, "reference": c.reference, "name": n["name"], "role": n["role"], "field": field})
                    break
    return hits


def ensure(db: Session, conn: Connection) -> ConflictCheck:
    """Create (once) and run the automated part of the check for a request."""
    chk = db.scalar(select(ConflictCheck).where(ConflictCheck.connection_id == conn.id))
    if chk:
        return chk
    lawyer = db.get(Lawyer, conn.lawyer_id)
    org_id = db.get(User, lawyer.user_id).organization_id
    names = names_for(db, db.get(Intake, conn.intake_id), db.get(User, conn.client_id))
    chk = ConflictCheck(connection_id=conn.id, organization_id=org_id, names_checked=names, automated_hits=search(db, org_id, names))
    db.add(chk)
    db.flush()
    audit.record(db, action="conflict_check.run", result="success", resource_type="connection", resource_id=conn.id,
                 organization_id=org_id, risk="MEDIUM", detail=f"{len(names)} names, {len(chk.automated_hits)} automated hits")
    return chk


def decide(db: Session, p: Principal, conn: Connection, clear: bool, note: str) -> ConflictCheck:
    chk = ensure(db, conn)
    if chk.status != "PENDING_REVIEW":
        raise ConflictError("The conflict check has already been decided", code="conflict_check_decided")
    chk.status, chk.decided_by, chk.decided_at, chk.note = ("CLEARED" if clear else "CONFLICT"), p.id, utcnow(), note[:1000]
    if not clear:
        # Decline without saying why: the reason could reveal another client's matter.
        conn.status, conn.responded_at, conn.lawyer_note = "declined", utcnow(), ""
        intake = db.get(Intake, conn.intake_id)
        db.add(Notification(user_id=conn.client_id, kind="connection", link="/portal",
                            title=f"Declined: {intake.title}",
                            body="This advocate is unable to take on your matter. You may contact another advocate."))
    audit.record(db, action="conflict_check.decide", result="success", actor=p, resource_type="connection", resource_id=conn.id,
                 organization_id=chk.organization_id, risk="HIGH", detail=chk.status)
    db.flush()
    return chk


def out(chk: ConflictCheck) -> dict:
    return {"status": chk.status, "names": chk.names_checked,
            "automatedHits": [{"reference": h["reference"], "name": h["name"], "role": h["role"], "field": h["field"]} for h in chk.automated_hits],
            "decidedAt": chk.decided_at.isoformat() if chk.decided_at else None}
