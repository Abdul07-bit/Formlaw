"""
Public legal assistant for the landing page — no account needed.

It sees only the verified public legal corpus (never a case, a document or a user), is rate limited per IP and in total,
and answers with verbatim passages unless PUBLIC_ASSISTANT_MODEL is enabled. Same grounding rules as /research/answer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...db.session import get_db
from ...ingestion.status import corpus_status
from ...retrieval.legal_corpus import CorpusFilters
from ...schemas.common import ApiModel
from ...security import rate_limit
from ...services import legal_answer
from .research import camel

router = APIRouter(prefix="/public", tags=["public"])


class PublicQuestionIn(ApiModel):
    question: str = Field(min_length=3, max_length=500)
    previous: str | None = Field(default=None, max_length=500)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/ask", summary="Ask the verified legal corpus (anonymous, corpus only, rate limited)")
def ask(body: PublicQuestionIn, request: Request, db: Session = Depends(get_db, scope="function")):
    ip = _ip(request)
    rate_limit.hit("public_all", "all")
    rate_limit.hit("public", ip)
    question = legal_answer.with_context(body.question, body.previous)
    out = legal_answer.answer(db, question, CorpusFilters(), None, use_model=get_settings().public_assistant_model, ip=ip)
    return camel(out)


@router.get("/corpus", summary="What the public assistant can cite")
def corpus(db: Session = Depends(get_db, scope="function")):
    t = corpus_status(db)["totals"]
    return {"judgments": t.get("judgments", 0), "coverage": t.get("coverage", ""), "courts": t.get("courts", 0)}
