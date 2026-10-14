"""
Memory layers:

  WORKING   the run blackboard (in-process, discarded after the run)
  CASE      verified, case-scoped knowledge pointers (open contradictions, flagged chunks)
  EPISODIC  outcomes of previous runs on the case (intent, status, counts, failures)
  SEMANTIC  validated legal knowledge: issue → verified corpus passage links (organization-scoped)
  SECURITY  security events relevant to future runs (flagged chunks)

Rules: written only by the system after the verification gate; always with provenance; scoped by organization (and
case); expiring; never stores document text or secrets; memory points at evidence and is never itself evidence.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.base import utcnow
from ..domain.enums import MemoryScope
from ..models import MemoryItem

TTL = {MemoryScope.CASE: timedelta(days=180), MemoryScope.EPISODIC: timedelta(days=90),
       MemoryScope.SEMANTIC: timedelta(days=365), MemoryScope.SECURITY: timedelta(days=365)}


def _key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:40]


def read(db: Session, organization_id: str, case_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    now = utcnow()
    rows = db.scalars(select(MemoryItem).where(
        MemoryItem.organization_id == organization_id,
        or_(MemoryItem.case_id == case_id, MemoryItem.case_id.is_(None)),
        MemoryItem.validated.is_(True),
        or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > now),
    ).order_by(MemoryItem.created_at.desc()).limit(limit)).all()
    return [{"scope": r.scope, "kind": r.kind, **r.content, "provenance": r.provenance} for r in rows]


def write(db: Session, *, organization_id: str, case_id: str | None, scope: MemoryScope, kind: str, key_parts: list[str],
          content: dict[str, Any], provenance: dict[str, Any], validated: bool = True) -> None:
    key = _key(scope, kind, *key_parts)
    row = db.scalar(select(MemoryItem).where(MemoryItem.organization_id == organization_id, MemoryItem.case_id == case_id,
                                             MemoryItem.key == key))
    expires = utcnow() + TTL[scope]
    if row:
        row.content, row.provenance, row.validated, row.expires_at = content, provenance, validated, expires
    else:
        db.add(MemoryItem(organization_id=organization_id, case_id=case_id, scope=scope, kind=kind, key=key, content=content,
                          provenance=provenance, validated=validated, expires_at=expires))


def remember_run(db: Session, *, organization_id: str, case_id: str, run_id: str, result: dict[str, Any]) -> None:
    prov = {"runId": run_id}
    write(db, organization_id=organization_id, case_id=case_id, scope=MemoryScope.EPISODIC, kind="run_outcome", key_parts=[run_id],
          content={"intent": result["intent"], "status": result["status"], "topic": result.get("topic", ""),
                   "contradictions": len(result["contradictions"]), "missing": len(result["missing"]),
                   "unverified": len(result["unverified"]), "failures": result["stats"]["failures"]}, provenance=prov)
    for x in result["contradictions"]:
        write(db, organization_id=organization_id, case_id=case_id, scope=MemoryScope.CASE, kind="open_contradiction",
              key_parts=[x["topic"].lower()], content={"topic": x["topic"], "a": x["a"]["value"], "b": x["b"]["value"]},
              provenance={**prov, "chunks": [x["a"]["citation"]["chunkId"] if x["a"]["citation"] else None,
                                             x["b"]["citation"]["chunkId"] if x["b"]["citation"] else None]})
    for s in result["security"]:
        if s.get("chunkId"):
            write(db, organization_id=organization_id, case_id=case_id, scope=MemoryScope.SECURITY, kind="flagged_chunk",
                  key_parts=[s["chunkId"]], content={"source": s["source"], "kind": s["kind"]}, provenance={**prov, "chunk": s["chunkId"]})
    for a in result["authorities"]:
        if a["status"] == "SUPPORTED" and a.get("issue"):
            write(db, organization_id=organization_id, case_id=None, scope=MemoryScope.SEMANTIC, kind="authority_link",
                  key_parts=[a["issue"][:80].lower(), a["contentHash"]], content={"issue": a["issue"][:200], "title": a["title"],
                                                                                    "citation": a["citation"]}, provenance={**prov, "hash": a["contentHash"]})
