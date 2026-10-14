"""
Tools available to agents, bound to one run's scope (organization_id + case_id) and database session.
All are read-only or compute-only. Persisting results happens after the verification gate, outside agent control.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.enums import Risk
from ...llm import prompts
from ...llm.providers import LLMError, LLMOutputError, LLMRouter, get_embedder
from ...models import Document
from ...retrieval import case_index
from ...retrieval.legal_corpus import CorpusFilters, find_by_citation, search_corpus
from ...security.injection import scan
from ..verification.groundedness import verify_claim
from .gateway import Tool, TransientToolError


class LLMUnavailable(Exception):
    """No model configured: callers use their deterministic path."""


def build_tools(db: Session, *, organization_id: str, case_id: str, router: LLMRouter | None, prompt_refs: set[str]) -> dict[str, Tool]:
    scope = {"organization_id": organization_id, "case_id": case_id}

    def case_search(query: str, k: int = 8, document_ids: list[str] | None = None, doc_types: list[str] | None = None,
                    exclude_chunk_ids: set[str] | None = None, broaden: bool = False, max_per_document: int = 4) -> case_index.SearchResult:
        return case_index.search(db, **scope, query=query, k=k, document_ids=document_ids, doc_types=doc_types,
                                 exclude_chunk_ids=exclude_chunk_ids, broaden=broaden, max_per_document=max_per_document)

    def get_chunks(chunk_ids: list[str]) -> list[case_index.EvidenceHit]:
        return case_index.get_chunks(db, **scope, chunk_ids=chunk_ids)

    def all_chunks(limit: int = 400) -> list[case_index.EvidenceHit]:
        return case_index.all_chunks(db, **scope, limit=limit)

    def list_documents() -> list[dict[str, Any]]:
        docs = db.scalars(select(Document).where(Document.organization_id == organization_id, Document.case_id == case_id)).all()
        return [{"id": d.id, "name": d.filename, "docType": d.doc_type, "status": d.status, "pages": d.pages,
                 "references": (d.meta or {}).get("references", []), "securityFlags": d.security_flags or [],
                 "templateFields": (d.meta or {}).get("templateFields", [])} for d in docs]

    def llm_structured(task: str, prompt_id: str, schema: type[BaseModel], request: str,
                       passages: list[prompts.PromptPassage] = (), context: dict[str, Any] | None = None) -> dict[str, Any]:
        if router is None:
            raise LLMUnavailable()
        system, refs = prompts.system_prompt(prompt_id)
        prompt_refs.update(refs)
        try:
            obj, tokens, model = router.generate(task, system_prompt=system, schema=schema,
                                                 user_prompt=prompts.user_message(request=request, passages=list(passages), context=context))
        except LLMError as e:
            raise TransientToolError(str(e)) from e
        return {"obj": obj, "_tokens": tokens, "_model": model}

    def verify(claim: str, evidence: list[str]):
        return verify_claim(claim, evidence)

    def corpus_search(query: str, k: int = 6, kinds: list[str] | None = None) -> list[Any]:
        return search_corpus(db, query, CorpusFilters(kinds=kinds or []), k=k, embedder=get_embedder())

    def corpus_lookup_citation(citation: str) -> list[Any]:
        return find_by_citation(db, citation)

    def corpus_get_chunk(chunk_id: str) -> tuple[str, str] | None:
        from ...models import LegalChunk
        c = db.get(LegalChunk, chunk_id)
        return (c.text, c.content_hash) if c else None

    def scan_text(text: str):
        return scan(text)

    defs = [
        Tool("case_search", case_search, Risk.LOW, "Hybrid search over this case's documents"),
        Tool("get_chunks", get_chunks, Risk.LOW, "Fetch specific chunks of this case"),
        Tool("all_chunks", all_chunks, Risk.LOW, "Read every chunk of this case (bounded)"),
        Tool("list_documents", list_documents, Risk.LOW, "List this case's documents (metadata only)"),
        Tool("llm_structured", llm_structured, Risk.LOW, "Structured model call with trust-separated prompt"),
        Tool("verify_claim", verify, Risk.LOW, "Deterministic claim-vs-evidence verification"),
        Tool("corpus_search", corpus_search, Risk.LOW, "Search the approved legal corpus"),
        Tool("corpus_lookup_citation", corpus_lookup_citation, Risk.LOW, "Exact citation lookup in the approved corpus"),
        Tool("corpus_get_chunk", corpus_get_chunk, Risk.LOW, "Re-read a corpus passage by id (provenance check)"),
        Tool("scan_text", scan_text, Risk.LOW, "Injection / exfiltration scanner"),
    ]
    return {t.name: t for t in defs}


__all__ = ["build_tools", "LLMUnavailable", "LLMOutputError"]
