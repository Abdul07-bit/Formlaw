"""
Legal research outside a case — verified corpus only. Search returns verbatim passages with provenance; the grounded
answer endpoint phrases only verified sentences and refuses unknown citations. Nothing is generated in place of law.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...ingestion.status import corpus_status
from ...policies.engine import authorize
from ...retrieval.legal_corpus import CorpusFilters
from ...schemas.common import ApiModel
from ...security import rate_limit
from ...security.deps import Principal, require_lawyer
from ...services import audit, legal_answer
from ...services import research as research_service

router = APIRouter(tags=["research"])


class CorpusFilterIn(ApiModel):
    kinds: list[Literal["constitution_article", "statute_section", "rule", "regulation", "judgment"]] = Field(default_factory=list)
    jurisdiction: str | None = Field(default=None, max_length=120)
    court: str | None = Field(default=None, max_length=200)
    year_from: int | None = Field(default=None, ge=1950, le=2100)
    year_to: int | None = Field(default=None, ge=1950, le=2100)
    case_type: str | None = Field(default=None, max_length=80)
    topic: str | None = Field(default=None, max_length=120)
    citation: str | None = Field(default=None, max_length=60)
    article: str | None = Field(default=None, pattern=r"^\d{1,3}[A-Za-z]{0,2}$")
    statute: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=60)


class ResearchIn(CorpusFilterIn):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=8, ge=1, le=25)


class LegalQuestionIn(CorpusFilterIn):
    question: str = Field(min_length=3, max_length=500)
    previous: str | None = Field(default=None, max_length=500)


def _filters(b: CorpusFilterIn) -> CorpusFilters:
    return CorpusFilters(court=b.court, jurisdiction=b.jurisdiction, year_from=b.year_from, year_to=b.year_to, case_type=b.case_type,
                         topic=b.topic, citation=b.citation, article=b.article, statute=b.statute, source=b.source, kinds=list(b.kinds))


def camel(o: Any) -> Any:
    if isinstance(o, dict):
        return {(k.split("_")[0] + "".join(w.title() for w in k.split("_")[1:]) if isinstance(k, str) else k): camel(v) for k, v in o.items()}
    if isinstance(o, list):
        return [camel(v) for v in o]
    return o


@router.post("/research", summary="Search judgments, constitutional Articles, sections, rules and regulations")
def research(body: ResearchIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    authorize("research.search", p.role)
    rate_limit.hit("agent", p.id)
    out = research_service.research(db, body.query, filters=_filters(body), limit=body.limit)
    audit.record(db, action="research.search", result="success", actor=p, agent="Legal Research Agent", tool="corpus_search",
                 detail=f"{len(out['results'])} results")
    return camel(out)


@router.post("/research/answer", summary="Grounded answer from the verified corpus (claims → evidence → document → source)")
def research_answer(body: LegalQuestionIn, p: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    authorize("research.search", p.role)
    rate_limit.hit("agent", p.id)
    return camel(legal_answer.answer(db, legal_answer.with_context(body.question, body.previous), _filters(body), p))


@router.get("/research/corpus", summary="What the legal corpus actually contains (no inflated claims)")
def corpus(_: Principal = Depends(require_lawyer), db: Session = Depends(get_db, scope="function")):
    st = corpus_status(db)
    return {"totals": st["totals"], "sources": [
        {k: r[k] for k in ("source", "name", "status", "documents", "coverage", "quarantined")} for r in st["sources"]]}
