from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...agents import legal_bridge
from ...agents.engine.chunking import DocText
from ...core.config import ROOT_DIR, get_settings
from ...core.errors import Forbidden, NotFound, TooLarge, Unprocessable
from ...db.session import get_db
from ...models import Case, Document
from ...policy.risk import authorize
from ...schemas.cases import (AnalysisOut, CaseCreateIn, CaseOut, CaseSummaryOut, ChatIn, ChatOut, DocumentOut, DraftIn,
                              EvidenceOut, MatchOut)
from ...schemas.common import ApiModel, OutModel
from ...security import rate_limit
from ...security.deps import Principal, current_principal, require_client
from ...security.files import validate_upload
from ...ingestion.extract import extract
from ...services import audit, chat as chat_service, review as review_service
from ...services.access import get_case
from ...services.serializers import analysis_out, case_out, document_out, iso, latest_run
from ...services.storage import storage

router = APIRouter(prefix="/cases", tags=["cases"])
MAX_FILES_PER_REQUEST = 10


@router.get("", response_model=list[CaseSummaryOut])
def list_cases(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if p.role != "client":
        return []  # counsel reach cases through their connections
    cases = db.scalars(select(Case).where(Case.owner_id == p.id, Case.organization_id == p.user.organization_id,
                                          Case.deleted_at.is_(None)).order_by(Case.created_at.desc())).all()
    out = []
    for c in cases:
        run = latest_run(db, c.id)
        out.append({"id": c.id, "title": c.title, "city": c.city, "status": c.status, "area": run.area if run else None,
                    "documents": len(c.documents), "created_at": iso(c.created_at), "is_demo": c.is_demo})
    return out


@router.post("", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreateIn, p: Principal = Depends(require_client), db: Session = Depends(get_db)):
    authorize("case.create", p.role)
    rate_limit.hit("write", p.id)
    case = Case(organization_id=p.user.organization_id, owner_id=p.id, title=body.title.strip(), description=body.description.strip(),
                city=body.city.strip(), budget=body.budget, jurisdiction=body.city.strip() or None)
    db.add(case)
    db.flush()
    audit.record(db, action="case.create", result="success", actor=p.user, resource_type="case", resource_id=case.id, risk="MEDIUM")
    return case_out(db, case, "owner")


class DemoCaseIn(ApiModel):
    malicious: bool = False


@router.post("/demo", response_model=CaseOut, status_code=201, summary="Create the SYNTHETIC demo case (DEMO_MODE only)")
def create_demo_case(body: DemoCaseIn, p: Principal = Depends(require_client), db: Session = Depends(get_db)):
    if not get_settings().demo_mode:
        raise Forbidden("Demo data is disabled", code="demo_disabled")
    seed = json.loads((ROOT_DIR / "database" / "seeds" / "demo_data.json").read_text(encoding="utf-8"))["demoCase"]
    case = Case(organization_id=p.user.organization_id, owner_id=p.id, is_demo=True, city=seed["city"], budget=seed["budget"],
                title=seed["title"] + (" (security demo)" if body.malicious else ""), description=seed["description"])
    db.add(case)
    db.flush()
    docs = seed["documents"] + ([seed["maliciousDocument"]] if body.malicious else [])
    for d in docs:
        data = d["text"].encode()
        db.add(Document(case_id=case.id, owner_id=p.id, filename=d["name"], content_type=d["type"], size=len(data),
                        content_hash=hashlib.sha256(data).hexdigest(), processing_status="extracted", extracted_text=d["text"],
                        pages=d["text"].count("[[PAGE ") or 1))
    db.flush()
    db.refresh(case)
    audit.record(db, action="case.create_demo", result="success", actor=p.user, resource_type="case", resource_id=case.id, risk="MEDIUM")
    return case_out(db, case, "owner")


@router.get("/{case_id}", response_model=CaseOut)
def get_case_detail(case_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    case, access = get_case(db, p, case_id)  # admins and strangers get 404: no case enumeration
    return case_out(db, case, access)


@router.post("/{case_id}/documents", response_model=list[DocumentOut], status_code=201)
async def upload_documents(case_id: str, request: Request, files: list[UploadFile] = File(...),
                           p: Principal = Depends(require_client), db: Session = Depends(get_db)):
    authorize("document.upload", p.role)
    rate_limit.hit("upload", p.id, cost=max(1, len(files)))
    case, _ = get_case(db, p, case_id, write=True)
    if len(files) > MAX_FILES_PER_REQUEST:
        raise Unprocessable(f"Upload at most {MAX_FILES_PER_REQUEST} files at a time", code="too_many_files")
    limit = get_settings().max_upload_bytes
    created = []
    for f in files:
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise TooLarge(f"{f.filename} exceeds the {limit // (1024 * 1024)} MB limit")
        try:
            v = validate_upload(f.filename or "", f.content_type, data, limit)
        except Unprocessable as e:
            if e.code in ("active_content", "archive_bomb", "path_traversal"):
                audit.security_event(db, kind="malicious_file", doc_name=f.filename or "upload", snippet=e.message,
                                     actions=["Upload refused", "Security event logged"], case_id=case.id, actor_id=p.id)
            audit.record(db, action="document.upload", result="denied", actor=p.user, resource_type="case", resource_id=case.id,
                         risk="MEDIUM", detail=e.code)
            db.commit()
            raise
        ex = extract(v.kind, data)
        doc = Document(case_id=case.id, owner_id=p.id, filename=v.display_name, content_type=v.content_type, size=len(data),
                       storage_location=storage().put(data), content_hash=hashlib.sha256(data).hexdigest(),
                       processing_status=ex.status, extracted_text=ex.text, pages=ex.pages)
        db.add(doc)
        db.flush()
        created.append(doc)
        audit.record(db, action="document.upload", result="success", actor=p.user, resource_type="document", resource_id=doc.id,
                     risk="MEDIUM", detail=f"{v.ext} {ex.status}")
    case.status = "open"
    return [document_out(d, include_text=True) for d in created]


@router.post("/{case_id}/review", response_model=AnalysisOut, summary="Run the multi-agent case review")
def run_review(case_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db)):
    authorize("case.review", p.role)
    rate_limit.hit("agent", p.id)
    case, _ = get_case(db, p, case_id, write=True)
    run = review_service.run_review(db, case, p.user)
    db.flush()
    return analysis_out(db, run)


@router.post("/{case_id}/draft", response_model=AnalysisOut, summary="Statutory draft via Research → Drafting → Verification agents")
def create_draft(case_id: str, body: DraftIn, p: Principal = Depends(require_client), db: Session = Depends(get_db)):
    authorize("draft.create", p.role)
    rate_limit.hit("agent", p.id)
    case, _ = get_case(db, p, case_id, write=True)
    if body.doc_type not in legal_bridge.DRAFT_TYPES:
        raise Unprocessable(f"Unsupported draft type. Use one of: {', '.join(legal_bridge.DRAFT_TYPES)}", code="draft_type")
    run = latest_run(db, case.id)
    if not run:
        raise Unprocessable("Run the case review first", code="no_review")
    quarantined = {d.id for d in case.documents if d.processing_status == "quarantined"}
    docs = [DocText(d.id, d.filename, d.extracted_text) for d in case.documents if d.processing_status == "extracted" and d.id not in quarantined]
    run.legal_pipeline = legal_bridge.run_pipeline(docs, body.doc_type)
    audit.record(db, action="draft.create", result="success", actor=p.user, resource_type="case", resource_id=case.id, risk="MEDIUM",
                 task_id=run.task_id, agent="Legal Agents", verification_status=str(run.legal_pipeline.get("release_status", ""))[:20])
    return analysis_out(db, run)


@router.post("/{case_id}/chat", response_model=ChatOut, summary="Grounded Q&A over the case documents")
def ask(case_id: str, body: ChatIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    authorize("chat.ask", p.role)
    rate_limit.hit("agent", p.id)
    case, access = get_case(db, p, case_id)
    if access != "owner":
        raise NotFound("Case not found")  # counsel get the brief, not a chat over the client's raw documents
    return chat_service.answer(db, case, body.question.strip(), body.history, p.user)


@router.get("/{case_id}/evidence", response_model=list[EvidenceOut])
def evidence(case_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    case, access = get_case(db, p, case_id)
    run = latest_run(db, case.id)
    return (analysis_out(db, run) or {}).get("evidence", []) if run else []


class LawyerMatchesOut(OutModel):
    matches: list[MatchOut]
    disclaimer: str | None


@router.get("/{case_id}/lawyer-matches", response_model=LawyerMatchesOut,
            summary="Matched, KYC-verified advocates with the reasons for each match")
def lawyer_matches(case_id: str, p: Principal = Depends(require_client), db: Session = Depends(get_db)):
    case, _ = get_case(db, p, case_id, write=True)
    run = latest_run(db, case.id)
    a = analysis_out(db, run) if run else None
    return {"matches": a["matches"] if a else [], "disclaimer": a["fee_disclaimer"] if a else None}
