from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...agents import legal_bridge
from ...core.errors import NotFound
from ...db.session import get_db
from ...models import Evidence
from ...policy.risk import authorize
from ...retrieval.legal_corpus import CorpusFilters
from ...schemas.cases import CorpusFilterIn, LegalAnswerOut, LegalQuestionIn, ResearchIn, ResearchOut
from ...schemas.common import ApiModel
from ...security import rate_limit
from ...security.deps import Principal, current_principal
from ...ingestion.status import corpus_status
from ...services import audit, legal_answer, research as research_service
from ...services.access import get_case
from ...services.serializers import latest_run
from ...verification.groundedness import verify_claim
from pydantic import Field

router = APIRouter(tags=["research", "verification"])


@router.post("/research", response_model=ResearchOut, summary="Search Articles, sections, rules, regulations and judgments")
def research(body: ResearchIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    authorize("research.search", p.role)
    rate_limit.hit("agent", p.id)
    out = research_service.research(db, body.query, filters=_filters(body), limit=body.limit)
    audit.record(db, action="research.search", result="success", actor=p.user, agent="Research Agent", tool="search_legal_corpus",
                 detail=f"{len(out['results'])} results")
    return out


def _filters(b: CorpusFilterIn) -> CorpusFilters:
    return CorpusFilters(court=b.court, jurisdiction=b.jurisdiction, year_from=b.year_from, year_to=b.year_to, case_type=b.case_type,
                         topic=b.topic, citation=b.citation, article=b.article, statute=b.statute, source=b.source, kinds=list(b.kinds))


@router.post("/research/answer", response_model=LegalAnswerOut,
             summary="Grounded answer from the verified legal corpus (claims → evidence → document → source)")
def research_answer(body: LegalQuestionIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    authorize("research.search", p.role)
    rate_limit.hit("agent", p.id)
    return legal_answer.answer(db, body.question, _filters(body), p.user)


@router.get("/research/corpus", summary="What the legal corpus actually contains (no inflated claims)")
def corpus(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    st = corpus_status(db)
    return {"totals": st["totals"], "sources": [
        {k: r[k] for k in ("source", "name", "status", "documents", "coverage", "quarantined")} for r in st["sources"]]}


class ClaimIn(ApiModel):
    text: str = Field(min_length=3, max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)
    citations: list[str] = Field(default_factory=list, max_length=10)


class VerifyIn(ApiModel):
    case_id: str
    claims: list[ClaimIn] = Field(min_length=1, max_length=50)


@router.post("/verification/claims", summary="Verify claims against a case's evidence and the trusted corpus")
def verify_claims(body: VerifyIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rate_limit.hit("agent", p.id)
    case, _ = get_case(db, p, body.case_id)
    run = latest_run(db, case.id)
    if not run:
        raise NotFound("No review found for this case")
    evidence = {e.label: e.text for e in db.query(Evidence).filter(Evidence.run_id == run.id)}
    results = []
    for c in body.claims:
        v = verify_claim(c.text, [evidence[i] for i in c.evidence_ids if i in evidence], citations=c.citations,
                         citation_exists=legal_bridge.corpus_citation_exists)
        results.append({"text": c.text, "status": v.status, "confidence": v.confidence, "reason": v.reason})
    audit.record(db, action="verification.claims", result="success", actor=p.user, resource_type="case", resource_id=case.id,
                 agent="Verification Agent", tool="verify_claims", detail=f"{len(results)} claims")
    return {"results": results}
