"""
Client document review: organises a client's OWN uploaded files before they choose an advocate.

    for each file: VALIDATE → EXTRACT → NORMALISE → PROFILE (type, dates, references) → SCAN (instruction-like text)
    then: timeline (dated sentences, with source + page) · date conflicts (same one-off event, different dates, both
    sides kept) · missing documents (mentioned in the client's own files, or usually needed for this kind of matter)

Deterministic: no AI model, no network. It organises what the files say; it never says who is right, what the law is or
what will happen. Shown only to the client who owns the intake.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.missing_information.agent import CHECKLISTS, SATISFIES, WHY
from ..core.errors import Unprocessable
from ..db.base import utcnow
from ..ingestion.extract import extract
from ..ingestion.profile import REFERENCEABLE, parse_dates, profile
from ..ingestion.text import normalize, split_pages
from ..models import Intake, IntakeDocument
from ..security.files import validate_upload
from ..security.injection import scan
from .storage import storage

DISCLAIMER = ("Organised automatically from the files and description you provided. It is not legal advice, it does not "
              "judge who is right, and it may miss things — an advocate should review your documents.")
DOC_LABELS = {"fir": "FIR", "remand_report": "Remand report", "arrest_memo": "Arrest memo", "charge_sheet": "Charge sheet",
              "witness_statement": "Witness statement", "seizure_memo": "Seizure / recovery memo", "medical_report": "Medical report",
              "bail_order": "Bail order", "judgment": "Court judgment or order", "contract": "Agreement / contract",
              "legal_notice": "Legal notice", "affidavit": "Affidavit", "complaint": "Complaint", "invoice": "Invoice",
              "correspondence": "Letter or e-mail", "template": "Blank form", "document": "Document"}
# One-off events: two different dates for the same one is worth pointing out. (Notices, payments, hearings recur.)
EVENTS = {
    "Arrest": re.compile(r"\barrest(ed)?\b|\bapprehended\b|\btaken into custody\b", re.I),
    "FIR registered": re.compile(r"\b(fir|first information report)\b.{0,60}\b(registered|lodged|filed)\b|\b(registered|lodged)\b.{0,30}\bfir\b", re.I),
    "Termination": re.compile(r"\bterminat(ed|ion)\b|\bdismissed from\b", re.I),
    "Agreement signed": re.compile(r"\bagreement\b.{0,40}\b(signed|executed)\b|\b(signed|executed)\b.{0,40}\bagreement\b", re.I),
}
_SENT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_WRAP = re.compile(r"(?<!\n)\n(?!\n)")  # a single line break inside a paragraph (PDF line wrapping)
MAX_TIMELINE = 60


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(_WRAP.sub(" ", text)) if len(s.strip()) > 8]


def _dated(source: str, page: int | None, text: str) -> list[dict[str, Any]]:
    out = []
    for sent in _sentences(text):
        for raw, iso in parse_dates(sent):
            out.append({"date": iso, "dateText": raw, "event": sent[:280], "source": source, "page": page,
                        "kind": next((k for k, rx in EVENTS.items() if rx.search(sent)), None)})
    return out


def _read(d: IntakeDocument, limit: int) -> tuple[dict[str, Any], str]:
    """(document summary, normalised text with page markers or '')."""
    row: dict[str, Any] = {"id": d.id, "name": d.filename, "type": "document", "typeLabel": "Document", "pages": None,
                           "status": "read", "note": None, "datesFound": 0, "flagged": False}
    try:
        data = storage().get(d.storage_key)
        v = validate_upload(d.filename, d.mime_type, data, limit)
    except (Unprocessable, OSError, KeyError) as e:
        return row | {"status": "unreadable", "note": getattr(e, "message", "The file could not be opened.")}, ""
    ex = extract(v.kind, data)
    if ex.status != "extracted":
        status = "scanned" if ex.status == "needs_ocr" else "unreadable"
        note = ("This looks like a scan or photo. Its text can't be read automatically yet, but an advocate can still read it."
                if status == "scanned" else (ex.note or "No readable text."))
        return row | {"status": status, "note": note, "pages": ex.pages}, ""
    text = ex.text if "[[PAGE" in ex.text else normalize(ex.text)
    prof = profile(d.filename, text)
    flagged = scan(text[:200_000]).flagged
    row |= {"type": prof.doc_type, "typeLabel": DOC_LABELS.get(prof.doc_type, "Document"), "pages": ex.pages,
            "datesFound": len(prof.dates), "flagged": flagged, "references": prof.references}
    if prof.doc_type == "template":
        row["note"] = "This looks like a blank form. Fill it in (or upload the completed copy) so it can be used."
    elif flagged:
        row["note"] = "Some text looks like instructions to a computer system. It was treated as ordinary text."
    return row, text


def review(db: Session, intake: Intake, *, max_bytes: int) -> dict[str, Any]:
    docs = db.scalars(select(IntakeDocument).where(IntakeDocument.intake_id == intake.id).order_by(IntakeDocument.created_at)).all()
    documents, timeline = [], _dated("Your description", None, intake.description)
    referenced: dict[str, set[str]] = {}
    for k, (_label, pats) in REFERENCEABLE.items():
        if any(re.search(p, intake.description, re.I) for p in pats):
            referenced.setdefault(k, set()).add("your description")
    for d in docs:
        row, text = _read(d, max_bytes)
        documents.append({k: v for k, v in row.items() if k != "references"})
        if not text or row["type"] == "template":
            continue
        for page, page_text in split_pages(text):
            timeline += _dated(d.filename, page, normalize(page_text))
        for k in row.get("references", []):
            referenced.setdefault(k, set()).add(d.filename)

    # Date conflicts: the same one-off event dated differently by different sources. Both sides are kept.
    conflicts = []
    for kind in EVENTS:
        by_date: dict[str, list[dict]] = {}
        for t in timeline:
            if t["kind"] == kind and t["date"]:
                by_date.setdefault(t["date"], []).append(t)
        sources = {t["source"] for items in by_date.values() for t in items}
        if len(by_date) > 1 and len(sources) > 1:
            conflicts.append({"event": kind, "sides": [{"date": iso, "dateText": items[0]["dateText"], "source": items[0]["source"],
                                                         "page": items[0]["page"], "quote": items[0]["event"]}
                                                        for iso, items in sorted(by_date.items())][:4],
                              "note": "Your documents give different dates for this. Both are shown; an advocate can work out which is right."})

    present_types = {d["type"] for d in documents}
    names = " ".join(d["name"].lower().replace("_", " ") for d in documents)

    def present(key: str) -> bool:
        return bool(SATISFIES.get(key, {key}) & present_types) or key.replace("_", " ") in names

    missing = [{"key": k, "title": REFERENCEABLE[k][0], "why": WHY.get(k, "Mentioned in your documents."), "basis": "mentioned",
                "mentionedIn": sorted(src)} for k, src in sorted(referenced.items()) if not present(k)]
    have = {m["key"] for m in missing}
    missing += [{"key": k, "title": REFERENCEABLE[k][0], "why": WHY.get(k, ""), "basis": "usually_needed", "mentionedIn": []}
                for k in CHECKLISTS.get(intake.matter_type or "", []) if k not in have and not present(k)]
    timeline.sort(key=lambda t: (t["date"] or "9999", t["source"]))
    readable = sum(d["status"] == "read" for d in documents)
    result = {
        "generatedAt": utcnow().isoformat(timespec="seconds"), "engine": "rules (no AI model)", "disclaimer": DISCLAIMER,
        "documents": documents, "timeline": [{k: v for k, v in t.items() if k != "kind"} for t in timeline[:MAX_TIMELINE]],
        "conflicts": conflicts, "missing": missing,
        "summary": {"documents": len(documents), "readable": readable, "datedEvents": len(timeline), "conflicts": len(conflicts),
                    "missing": len(missing)},
    }
    intake.review, intake.reviewed_at = result, utcnow()
    return result
