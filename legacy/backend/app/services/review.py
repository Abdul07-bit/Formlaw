"""Runs the review pipeline for a case and persists every result into normalised tables."""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import legal_bridge
from ..agents.engine.chunking import DocText
from ..agents.engine.orchestrator import AnalysisInput, AnalysisResult, analyse
from ..agents.engine.related import CaseMeta
from ..core.config import get_settings
from ..core.errors import AgentLimitExceeded, Unprocessable
from ..db.base import utcnow
from ..matching.agent import Candidate
from ..models import (AnalysisRun, Case, Citation, Claim, Contradiction, Document, Evidence, Lawyer, LawyerCase,
                      LawyerExpertise, LawyerMatch, MissingInformation, RelatedCase)
from ..retrieval.hybrid import content_hash
from . import audit

log = logging.getLogger("formlaw.review")


def new_task_id() -> str:
    return f"TASK-{secrets.randbelow(90000) + 10000}"


def verified_candidates(db: Session) -> list[Candidate]:
    lawyers = db.scalars(select(Lawyer).where(Lawyer.verification_status == "verified", Lawyer.profile_status == "published")).all()
    areas: dict[str, set[str]] = {}
    for e in db.scalars(select(LawyerExpertise).where(LawyerExpertise.verified.is_(True))):
        areas.setdefault(e.lawyer_id, set()).add(e.practice_area)
    return [Candidate(l.id, l.city, l.state, frozenset(areas.get(l.id, set())), l.consultation_fee, l.hearing_fee,
                      l.response_hours, l.experience_years) for l in lawyers]


def verified_case_meta(db: Session) -> list[CaseMeta]:
    rows = db.scalars(select(LawyerCase).where(LawyerCase.verification_status == "verified")).all()
    return [CaseMeta(r.id, r.lawyer_id, r.legal_category, tuple(r.keywords or ())) for r in rows]


def run_review(db: Session, case: Case, actor) -> AnalysisRun:
    docs = list(db.scalars(select(Document).where(Document.case_id == case.id)))
    if not docs:
        raise Unprocessable("Upload at least one document before running a review", code="no_documents")
    readable = [d for d in docs if d.extracted_text and d.processing_status in ("extracted", "quarantined")]
    s = get_settings()
    task_id = new_task_id()
    run = AnalysisRun(case_id=case.id, task_id=task_id, status="running")
    db.add(run)
    case.status = "processing"
    db.flush()

    try:
        result = analyse(AnalysisInput(
            task_id=task_id, title=case.title, description=case.description, city=case.city, budget=case.budget,
            documents=[DocText(d.id, d.filename, d.extracted_text) for d in readable],
            pending_extraction=sum(d.processing_status == "needs_ocr" for d in docs),
            candidates=verified_candidates(db), lawyer_cases=verified_case_meta(db), limits=s.limits,
        ))
    except AgentLimitExceeded as e:
        run.status, run.error, run.completed_at = "failed", e.message, utcnow()
        case.status = "open"
        audit.record(db, action="case.review", result="error", actor=actor, resource_type="case", resource_id=case.id,
                     task_id=task_id, agent="Orchestrator", detail=e.message)
        raise

    _persist(db, case, run, result, {d.id: d for d in docs}, actor)

    # Original six-agent system: research, statutory draft and line-by-line verification over clean documents.
    clean = [DocText(d.id, d.filename, d.extracted_text) for d in readable if d.id not in result.quarantined_docs]
    doc_type = legal_bridge.default_draft_type(result.area)
    try:
        t0 = utcnow()
        run.legal_pipeline = legal_bridge.run_pipeline(clean, doc_type) if clean else None
        result.run.log("Legal Agents", f"Research → Drafting ({doc_type}) → Verification: {(run.legal_pipeline or {}).get('release_status', 'skipped')}")
        audit.record(db, action="legal_pipeline.run", result="success", actor=actor, resource_type="case", resource_id=case.id,
                     task_id=task_id, agent="Legal Agents", tool="run_legal_pipeline",
                     latency_ms=int((utcnow() - t0).total_seconds() * 1000),
                     verification_status=(run.legal_pipeline or {}).get("release_status", "")[:20])
    except (ValueError, OSError) as e:
        log.warning("legal pipeline failed task=%s error=%s", task_id, type(e).__name__)
        result.run.log("Legal Agents", "Statutory drafting pipeline unavailable — review results unaffected", "warn")

    run.trace = [vars(t) for t in result.run.trace]
    run.status, run.completed_at = "completed", utcnow()
    case.status, case.case_type = "reviewed", result.area
    for call in result.run.calls:
        audit.record(db, action="agent.tool_call", result=call["result"], actor=actor, resource_type="case", resource_id=case.id,
                     task_id=task_id, agent=call["agent"], tool=call["tool"], latency_ms=call["latency_ms"])
    audit.record(db, action="case.review", result="success", actor=actor, resource_type="case", resource_id=case.id, task_id=task_id,
                 agent="Orchestrator", verification_status=f"{result.verification['supported']}/{result.verification['analysed']} supported")
    return run


def _persist(db: Session, case: Case, run: AnalysisRun, r: AnalysisResult, docs: dict[str, Document], actor) -> None:
    run.area, run.area_confidence, run.summary = r.area, r.area_confidence, r.summary
    run.draft_title, run.draft_body, run.verification = r.draft_title, r.draft_body, r.verification

    ev_ids: dict[str, str] = {}
    for e in r.evidence:
        row = Evidence(run_id=run.id, case_id=case.id, document_id=e.doc_id, label=e.label, page=e.page, text=e.text,
                       highlight=e.highlight[:300], content_hash=content_hash(e.text))
        db.add(row)
        db.flush()
        ev_ids[e.label] = row.id

    for i, f in enumerate(r.facts):
        claim = Claim(run_id=run.id, case_id=case.id, key=f.key, label=f.label, text=f.statement, verification_status=f.status,
                      confidence={"SUPPORTED": 0.95, "PARTIALLY_SUPPORTED": 0.6, "CONTRADICTED": 0.5}.get(f.status, 0.2), ordinal=i)
        db.add(claim)
        db.flush()
        for label in f.evidence:
            db.add(Citation(claim_id=claim.id, evidence_id=ev_ids[label], source_type="case_document"))

    for c in r.contradictions:
        db.add(Contradiction(run_id=run.id, case_id=case.id, topic=c.topic, claim_a=c.a_value, claim_b=c.b_value,
                             evidence_a=ev_ids[c.a_evidence], evidence_b=ev_ids[c.b_evidence], confidence=c.confidence))
    for i, g in enumerate(r.missing):
        db.add(MissingInformation(run_id=run.id, case_id=case.id, title=g.title, description=g.why, action=g.action, ordinal=i))
    for rank, m in enumerate(r.matches):
        db.add(LawyerMatch(run_id=run.id, case_id=case.id, lawyer_id=m.lawyer_id, rank=rank, score=m.score, reasons=m.reasons,
                           estimate_min=m.estimate[0], estimate_max=m.estimate[1]))
    for rel in r.related:
        db.add(RelatedCase(run_id=run.id, lawyer_case_id=rel.case_id, similarity=rel.similarity, shared_terms=list(rel.shared_terms)))

    for hit in r.security:
        ev = audit.security_event(db, kind=hit.kind, doc_name=hit.doc_name, snippet=hit.snippet, actions=hit.actions,
                                  case_id=case.id, document_id=hit.doc_key, actor_id=getattr(actor, "id", None))
        if hit.doc_key in docs:
            docs[hit.doc_key].processing_status = "quarantined"
        audit.record(db, action="security.prompt_injection_blocked", result="blocked", actor=actor, resource_type="document",
                     resource_id=hit.doc_key, risk="HIGH", task_id=run.task_id, agent="Security Agent", security_event_id=ev.id)
