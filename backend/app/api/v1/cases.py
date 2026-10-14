"""Cases, team members and documents (lawyer workbench)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import Conflict, Forbidden, NotFound, TooLarge, Unprocessable
from ...db.session import get_db
from ...ingestion.case_documents import ingest
from ...models import Case, CaseMember, Document, DocumentChunk, Membership, User
from ...policies.engine import authorize
from ...repositories.access import get_case
from ...retrieval import case_index
from ...schemas.workspace import CaseIn, CasePatch, MemberIn
from ...security import rate_limit
from ...security.deps import Principal, require_lawyer
from ...services import audit
from ...services.serializers import case_out, document_out, member_out

router = APIRouter(tags=["cases"])


def next_reference(db: Session, org_id: str) -> str:
    from datetime import date
    n = (db.scalar(select(func.count(Case.id)).where(Case.organization_id == org_id)) or 0) + 1
    return f"FL-{date.today().year}-{n:04d}"


@router.get("/cases")
def list_cases(p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    authorize("case.list", p.role)
    rows = db.execute(select(Case, CaseMember.role).join(CaseMember, CaseMember.case_id == Case.id)
                      .where(CaseMember.user_id == p.id, CaseMember.role != "client", Case.deleted_at.is_(None),
                             Case.organization_id.in_(p.org_ids)).order_by(Case.updated_at.desc())).all()
    return [case_out(db, c, role) for c, role in rows]


@router.get("/firm/matters")
def firm_register(p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    """
    Matter register for firm owners/admins: which matters exist, their status and who leads them. Deliberately no
    title, client name, description, documents or findings — those need case membership granted by the matter lead.
    """
    authorize("firm.register.read", p.role)
    org_role = db.scalar(select(Membership.role).where(Membership.organization_id == p.org_id, Membership.user_id == p.id))
    if org_role not in ("owner", "admin"):
        raise Forbidden("Only firm owners and administrators can view the matter register", code="not_firm_admin")
    out = []
    for c in db.scalars(select(Case).where(Case.organization_id == p.org_id, Case.deleted_at.is_(None)).order_by(Case.created_at.desc())):
        team = db.execute(select(CaseMember.role, User.name).join(User, User.id == CaseMember.user_id)
                          .where(CaseMember.case_id == c.id, CaseMember.role != "client")).all()
        out.append({"id": c.id, "reference": c.reference, "matterType": c.matter_type, "status": c.status,
                    "createdAt": c.created_at.isoformat() if c.created_at else None,
                    "leads": [n for r, n in team if r == "lead"], "teamSize": len(team),
                    "iAmMember": db.scalar(select(CaseMember.id).where(CaseMember.case_id == c.id, CaseMember.user_id == p.id)) is not None})
    audit.record(db, action="firm.register.read", result="success", actor=p, resource_type="organization", resource_id=p.org_id,
                 organization_id=p.org_id)
    return out


@router.post("/cases", status_code=201)
def create_case(body: CaseIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    authorize("case.create", p.role)
    rate_limit.hit("write", p.id)
    c = Case(organization_id=p.org_id, created_by=p.id, reference=body.reference or next_reference(db, p.org_id), title=body.title,
             description=body.description, matter_type=body.matter_type, jurisdiction=body.jurisdiction, court=body.court,
             client_name=body.client_name)
    db.add(c)
    db.flush()
    db.add(CaseMember(case_id=c.id, user_id=p.id, role="lead", added_by=p.id))
    audit.record(db, action="case.create", result="success", actor=p, resource_type="case", resource_id=c.id, risk="MEDIUM",
                 organization_id=c.organization_id, case_id=c.id)
    db.flush()
    return case_out(db, c, "lead")


@router.get("/cases/{case_id}")
def get_one(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return case_out(db, a.case, a.role)


@router.patch("/cases/{case_id}")
def update_case(case_id: str, body: CasePatch, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "case.update")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a.case, k, v)
    audit.record(db, action="case.update", result="success", actor=p, resource_type="case", resource_id=case_id, risk="MEDIUM",
                 organization_id=a.case.organization_id, case_id=case_id)
    db.flush()
    return case_out(db, a.case, a.role)


@router.get("/cases/{case_id}/members")
def members(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    get_case(db, p, case_id)
    return [member_out(db, m) for m in db.scalars(select(CaseMember).where(CaseMember.case_id == case_id))]


@router.post("/cases/{case_id}/members", status_code=201)
def add_member(case_id: str, body: MemberIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "case.member.add")
    u = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    # Only lawyers of the same organization can join the legal team (no cross-tenant sharing).
    if not u or u.role != "lawyer" or not db.scalar(select(Membership.id).where(Membership.user_id == u.id,
                                                                               Membership.organization_id == a.case.organization_id)):
        raise Unprocessable("Only lawyers in your organization can be added to the case team", code="not_in_organization")
    if db.scalar(select(CaseMember.id).where(CaseMember.case_id == case_id, CaseMember.user_id == u.id)):
        raise Conflict("Already a member")
    m = CaseMember(case_id=case_id, user_id=u.id, role=body.role, added_by=p.id)
    db.add(m)
    audit.record(db, action="case.member.add", result="success", actor=p, resource_type="case", resource_id=case_id, risk="MEDIUM",
                 organization_id=a.case.organization_id, case_id=case_id)
    db.flush()
    return member_out(db, m)


# ---------------------------------------------------------------- documents
@router.post("/cases/{case_id}/documents", status_code=201)
async def upload(case_id: str, files: list[UploadFile] = File(...), p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id, "document.upload")
    rate_limit.hit("upload", p.id, cost=len(files))
    if len(files) > 10:
        raise Unprocessable("Upload at most 10 files at a time")
    limit = get_settings().max_upload_bytes
    out = []
    for f in files:
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise TooLarge(f"{f.filename} is larger than {limit // (1024 * 1024)} MB")
        d = ingest(db, organization_id=a.case.organization_id, case_id=case_id, uploaded_by=p.id, filename=f.filename or "document",
                   declared_type=f.content_type, data=data, source="lawyer_upload", is_demo=a.case.is_demo)
        out.append(document_out(d))
    case_index.invalidate(case_id)
    return out


@router.get("/cases/{case_id}/documents")
def list_documents(case_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    a = get_case(db, p, case_id)
    return [document_out(d) for d in db.scalars(select(Document).where(Document.case_id == case_id,
                                                                         Document.organization_id == a.case.organization_id).order_by(Document.created_at))]


def _doc(db: Session, p: Principal, document_id: str) -> Document:
    d = db.get(Document, document_id)
    if not d:
        raise NotFound("Document not found")
    get_case(db, p, d.case_id)  # 404 unless the caller can read the case
    return d


@router.get("/documents/{document_id}")
def document_detail(document_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    return document_out(_doc(db, p, document_id))


@router.get("/documents/{document_id}/pages")
def document_pages(document_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    """Text of each page as chunks, for the evidence viewer. Highlight targets are chunk ids."""
    d = _doc(db, p, document_id)
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == d.id, DocumentChunk.case_id == d.case_id)
                        .order_by(DocumentChunk.ordinal)).all()
    pages: dict[int, list] = {}
    for c in chunks:
        pages.setdefault(c.page, []).append({"chunkId": c.id, "paragraph": c.paragraph, "section": c.section, "text": c.text,
                                             "securityFlags": c.security_flags or []})
    return {"document": document_out(d), "pages": [{"page": k, "chunks": v} for k, v in sorted(pages.items())]}


@router.get("/documents/{document_id}/file")
def document_file(document_id: str, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    from ...services.storage import storage
    d = _doc(db, p, document_id)
    if not d.storage_key:
        raise NotFound("File not available")
    audit.record(db, action="document.download", result="success", actor=p, resource_type="document", resource_id=d.id,
                 organization_id=d.organization_id, case_id=d.case_id)
    # Served as an attachment with a fixed safe type list, never rendered inline from user-controlled content.
    safe = d.mime_type if d.mime_type in ("application/pdf", "image/png", "image/jpeg") else "application/octet-stream"
    return Response(storage().get(d.storage_key), media_type=safe,
                    headers={"content-disposition": f'attachment; filename="{d.filename}"', "x-content-type-options": "nosniff"})
