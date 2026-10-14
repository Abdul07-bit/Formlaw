"""
Legal source registry. legal-data/source-config/sources.json is the single source of truth (with the terms audit for every
source); sync() mirrors it into legal_sources. Only APPROVED sources whose terms review is current can be ingested.

Statuses
    DISCOVERED      known URL, terms not reviewed yet
    UNDER_REVIEW    terms review in progress
    APPROVED        terms reviewed; automated or manual import permitted as recorded
    RESTRICTED      access controls (CAPTCHA, login, 403) or terms prevent automated access; never bypassed
    REJECTED        not to be used
    EXPIRED_REVIEW  computed: APPROVED but the terms review is older than REVIEW_VALID_DAYS — re-review before ingesting
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import ROOT_DIR
from ..models import LegalSource

REGISTRY_PATH = ROOT_DIR / "legal-data" / "source-config" / "sources.json"
STATUSES = ("DISCOVERED", "UNDER_REVIEW", "APPROVED", "RESTRICTED", "REJECTED")
REVIEW_VALID_DAYS = 365
_APPROVED_REQUIRES = ("license", "terms_url", "last_checked", "decision_reason", "approved_by", "access_method", "attribution")


class IngestionRefused(Exception):
    """Raised when a source is not cleared for ingestion."""


def load() -> dict[str, Any]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    for s in data["sources"]:
        if s["status"] not in STATUSES:
            raise ValueError(f"{s['key']}: invalid status {s['status']}")
        if s["status"] == "APPROVED" and not s.get("license"):
            raise ValueError(f"{s['key']}: an APPROVED source must record its licence/terms")
    return data


def effective_status(entry: dict[str, Any], today: date | None = None) -> str:
    if entry["status"] != "APPROVED":
        return entry["status"]
    checked = date.fromisoformat(entry["last_checked"]) if entry.get("last_checked") else None
    if not checked or (today or date.today()) - checked > timedelta(days=REVIEW_VALID_DAYS):
        return "EXPIRED_REVIEW"
    return "APPROVED"


def validate(data: dict[str, Any] | None = None, today: date | None = None) -> list[str]:
    """Problems with the registry itself (missing audit fields, bad URLs, duplicate keys, stale reviews)."""
    data = data or load()
    problems, keys = [], set()
    for s in data["sources"]:
        k = s.get("key", "?")
        if k in keys:
            problems.append(f"{k}: duplicate key")
        keys.add(k)
        for f in ("name", "base_url", "jurisdiction", "source_type", "status"):
            if not s.get(f):
                problems.append(f"{k}: missing {f}")
        url = urlparse(s.get("base_url", ""))
        if url.scheme not in ("https", "file") or (url.scheme == "https" and not url.netloc):
            problems.append(f"{k}: base_url must be https:// (or file:// for manual import)")
        if s.get("status") == "APPROVED":
            # Operator-supplied channels have no source-level terms: each manifest row must carry its own licence
            # (enforced by adapters/local_manifest.py), so terms_url / commercial-use apply per document instead.
            per_row = s.get("source_type") == "operator_supplied"
            required = [f for f in _APPROVED_REQUIRES if not (per_row and f == "terms_url")]
            problems += [f"{k}: APPROVED source missing {f}" for f in required if not s.get(f)]
            if effective_status(s, today) == "EXPIRED_REVIEW":
                problems.append(f"{k}: terms review older than {REVIEW_VALID_DAYS} days — re-review before ingesting")
            if not per_row and s.get("commercial_use_allowed") is not True:
                problems.append(f"{k}: APPROVED but commercial use is not confirmed")
    window = data.get("target_window") or {}
    try:
        if date.fromisoformat(window["start"]) > date.fromisoformat(window["end"]):
            problems.append("target_window: start is after end")
    except (KeyError, ValueError):
        problems.append("target_window: start/end (YYYY-MM-DD) required")
    return problems


def target_window(data: dict[str, Any] | None = None) -> tuple[date, date]:
    w = (data or load())["target_window"]
    return date.fromisoformat(w["start"]), date.fromisoformat(w["end"])


def sync(db: Session) -> list[LegalSource]:
    out = []
    data = load()
    for s in data["sources"]:
        row = db.scalar(select(LegalSource).where(LegalSource.key == s["key"])) or LegalSource(key=s["key"])
        status = effective_status(s)
        row.name, row.base_url, row.license = s["name"], s["base_url"], s.get("license") or "not reviewed"
        row.source_type, row.jurisdiction, row.terms_url = s.get("source_type"), s.get("jurisdiction"), s.get("terms_url")
        row.coverage_start, row.coverage_end = s.get("coverage_start"), s.get("coverage_end")
        row.access_method, row.allowed_usage, row.restrictions = s.get("access_method"), s.get("allowed_usage"), s.get("restrictions")
        row.attribution, row.authoritative = s.get("attribution"), bool(s.get("authoritative"))
        row.commercial_use_allowed, row.redistribution_allowed = s.get("commercial_use_allowed"), s.get("redistribution_allowed")
        row.api_available, row.verification_status = s.get("api_available"), status
        row.decision_reason = s.get("decision_reason")
        row.last_checked = date.fromisoformat(s["last_checked"]) if s.get("last_checked") else None
        row.enabled = status == "APPROVED"
        db.add(row)
        out.append(row)
    keys = {s["key"] for s in data["sources"]}
    for stale in db.scalars(select(LegalSource).where(LegalSource.key.not_in(keys))):
        # Removed from the registry: never ingestible again; existing documents stay traceable to it.
        stale.verification_status, stale.enabled = "REJECTED", False
        stale.decision_reason = "Removed from the source registry"
    db.flush()
    return out


def require_approved(db: Session, key: str) -> tuple[LegalSource, dict[str, Any]]:
    """LICENSE / TERMS CHECK stage: refuse anything not APPROVED with a current review, in both the file and the database."""
    entry = next((s for s in load()["sources"] if s["key"] == key), None)
    if entry is None:
        raise IngestionRefused(f"Unknown source '{key}'. Add it to {REGISTRY_PATH.name} with a terms audit first.")
    sync(db)
    row = db.scalar(select(LegalSource).where(LegalSource.key == key))
    status = effective_status(entry)
    if status != "APPROVED" or not row or not row.enabled:
        raise IngestionRefused(f"{key}\nSTATUS: NOT INGESTED\nREASON: {status} — {entry.get('decision_reason') or 'usage rights not reviewed'}")
    return row, entry
