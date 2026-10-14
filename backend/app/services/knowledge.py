"""
Persist a run's verified output into the case workspace (after the verification gate). Upserts by a stable key so
repeated runs refine, not duplicate, the case knowledge. Lawyer review decisions are never overwritten by agents.
"""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Citation, Claim, Contradiction, Draft, Evidence, LegalAuthority, MissingInformation, TimelineEvent)

ANALYSIS_KINDS_EXCLUDED = {"answer", "summary"}


def _k(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def _upsert(db: Session, model, case_id: str, key: str, **values):
    row = db.scalar(select(model).where(model.case_id == case_id, model.key == key))
    if row is None:
        row = model(case_id=case_id, key=key, **values)
        db.add(row)
        db.flush()
        return row, True
    return row, False


class Writer:
    def __init__(self, db: Session, organization_id: str, case_id: str, run_id: str, result: dict[str, Any]):
        self.db, self.org, self.case, self.run, self.r = db, organization_id, case_id, run_id, result
        self.ev_by_chunk = {e["chunkId"]: e for e in result["evidence"]}
        self._evidence_ids: dict[tuple[str, str], str] = {}

    def evidence(self, cite: dict[str, Any] | None) -> str | None:
        if not cite:
            return None
        k = (cite["chunkId"], cite["quote"])
        if k in self._evidence_ids:
            return self._evidence_ids[k]
        hit = self.ev_by_chunk.get(cite["chunkId"], {})
        row, _ = _upsert(self.db, Evidence, self.case, _k(*k), organization_id=self.org, document_id=cite["documentId"],
                         chunk_id=cite["chunkId"], page=cite["page"], paragraph=cite["paragraph"], section=cite.get("section"),
                         quote=cite["quote"][:4000], content_hash=hit.get("contentHash", ""), first_run_id=self.run)
        self._evidence_ids[k] = row.id
        return row.id

    def write_all(self) -> dict[str, int]:
        n = {"claims": 0, "contradictions": 0, "missing": 0, "timeline": 0, "authorities": 0}
        auth_ids: dict[str, str] = {}
        for a in self.r["authorities"]:
            row, new = _upsert(self.db, LegalAuthority, self.case, _k(a["contentHash"]), organization_id=self.org, run_id=self.run,
                               legal_document_id=a["legalDocumentId"], legal_chunk_id=a["legalChunkId"], authority_type=a["type"],
                               title=a["title"][:400], citation=a["citation"], court=a["court"], page=a["page"],
                               decision_date=date.fromisoformat(a["date"]) if a["date"] else None, quote=a["quote"],
                               issue=(a.get("issue") or "")[:300], source_name=a["source"], source_url=a["sourceUrl"],
                               license=a["license"], content_hash=a["contentHash"])
            auth_ids[a["id"]] = row.id
            n["authorities"] += new
        for c in self.r["claims"]:
            if c["kind"] in ANALYSIS_KINDS_EXCLUDED:
                continue
            row, new = _upsert(self.db, Claim, self.case, _k(c["kind"], " ".join(c["text"].lower().split())), organization_id=self.org,
                               run_id=self.run, agent=c["agent"], kind=c["kind"], text=c["text"], status=c["status"],
                               confidence=c["confidence"], reason=c["reason"][:400])
            if not new:  # refresh verification, keep the lawyer's review decision
                row.status, row.confidence, row.reason, row.run_id = c["status"], c["confidence"], c["reason"][:400], self.run
            have = {(x.evidence_id, x.authority_id) for x in self.db.scalars(select(Citation).where(Citation.claim_id == row.id))}
            for cite in c["citations"]:
                eid = self.evidence(cite)
                if (eid, None) not in have:
                    self.db.add(Citation(claim_id=row.id, evidence_id=eid))
            for aid in c["authorityIds"]:
                if aid in auth_ids and (None, auth_ids[aid]) not in have:
                    self.db.add(Citation(claim_id=row.id, authority_id=auth_ids[aid]))
            n["claims"] += new
        for x in self.r["contradictions"]:
            ea, eb = self.evidence(x["a"]["citation"]), self.evidence(x["b"]["citation"])
            if not ea or not eb:
                continue
            row, new = _upsert(self.db, Contradiction, self.case, _k(x["topic"].lower(), *sorted([x["a"]["value"].lower(), x["b"]["value"].lower()])),
                               organization_id=self.org, run_id=self.run, topic=x["topic"], statement_a=x["a"]["statement"],
                               statement_b=x["b"]["statement"], evidence_a_id=ea, evidence_b_id=eb, nature=x["nature"],
                               confidence=x["confidence"], provenance=x["provenance"])
            if not new and x["provenance"]:
                row.provenance = x["provenance"]
            n["contradictions"] += new
        for m in self.r["missing"]:
            row, new = _upsert(self.db, MissingInformation, self.case, _k(m.get("title", "").lower()), organization_id=self.org,
                               run_id=self.run, title=m["title"], why_needed=m["why"], basis=m["basis"],
                               evidence_id=self.evidence(m["citation"]), importance=m["importance"])
            n["missing"] += new
        for t in self.r["timeline"]:
            eid = self.evidence(t["citation"])
            if not eid:
                continue
            row, new = _upsert(self.db, TimelineEvent, self.case, _k(t["eventType"], t["date"] or t["dateText"], t["citation"]["chunkId"]),
                               organization_id=self.org, run_id=self.run, event_date=date.fromisoformat(t["date"]) if t["date"] else None,
                               date_text=t["dateText"][:60], description=t["description"], event_type=t["eventType"][:40],
                               evidence_id=eid, status=t["status"])
            if not new:
                row.status = t["status"]
            n["timeline"] += new
        return n

    def draft(self, created_by: str) -> str | None:
        d = self.r.get("draft")
        if not d:
            return None
        row = Draft(case_id=self.case, organization_id=self.org, run_id=self.run, kind=d["kind"], title=d["title"][:200],
                    sections={k: d[k] for k in ("facts", "authorities", "inferences", "recommendations")}, body=d["body"],
                    created_by=created_by)
        self.db.add(row)
        self.db.flush()
        return row.id
