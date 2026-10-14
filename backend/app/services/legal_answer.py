"""
Grounded legal Q&A over the verified corpus.

    Answer → Claim → Evidence (chunk, page) → Document → Original Source

The model is never the source of truth: it may only phrase sentences from retrieved passages, each sentence
is re-verified against the passages it cites, and anything unsupported is dropped. If nothing survives:
"I could not find sufficient verified source material to support this answer."
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm import prompts
from ..llm.schemas import GroundedAnswer
from ..llm.providers import LLMError, LLMOutputError, get_embedder, get_router
from ..models import ConstitutionProvision
from ..retrieval.legal_corpus import CorpusFilters, find_by_citation, find_by_parties, search_corpus
from ..security.injection import kinds_in
from ..agents.verification.groundedness import verify_claim
from . import audit
from .runs import new_task_id

log = logging.getLogger("formlaw.legal_answer")
INSUFFICIENT = "I could not find sufficient verified source material to support this answer."
CITATION = re.compile(r"\d{4}\s*INSC\s*\d+|\[\d{4}\]\s*\d+\s*S\.?\s?C\.?\s?R\.?\s*\d+|\(\d{4}\)\s*\d+\s*SCC\s*\d+|AIR\s*\d{4}\s*SC\s*\d+", re.I)
# Party names = the run of Capitalised words directly around "v." / "versus" (question words are lower-case or excluded).
PARTIES = re.compile(r"((?:[A-Z][\w.&'@]*\s+){0,5}[A-Z][\w.&'@]*)\s+(?:v\.|vs\.?|versus)\s+((?:[A-Z][\w.&'@]*\s*){1,6})")
_QWORDS = {"What", "When", "Where", "Which", "Who", "How", "Why", "Did", "Does", "Is", "Was", "In", "The", "Summarise", "Summarize", "Explain", "Tell"}
ARTICLE = re.compile(r"\barticle\s+(\d{1,3}[A-Z]{0,2})\b", re.I)
_W = re.compile(r"[a-z]{3,}")
_STOP = set("the and was for that with this from what when were who into does how can under which about".split())
# Generic legal vocabulary says nothing about whether a passage is on-topic.
_GENERIC = set("law laws legal rule rules court courts case cases held hold holds decide decided decision judgment judgments supreme high "
               "india indian act acts section sections provision provisions principle principles say says said give given".split())


def _stems(text: str) -> set[str]:
    return {w[:5] for w in _W.findall(text.lower()) if w not in _STOP and w not in _GENERIC}


def _tidy(passage: str, limit: int = 600) -> str:
    """Show whole sentences: drop a leading fragment and cut at a sentence end."""
    p = passage.strip()
    if p and (p[0].islower() or not p[0].isalnum()):
        m = re.search(r"[.?!:]\s+(?=[A-Z0-9\"“(])", p)
        if m and m.end() < len(p) // 2:
            p = p[m.end():]
    if len(p) > limit:
        cut = max(p.rfind(". ", 0, limit), p.rfind(".\n", 0, limit))
        p = p[: cut + 1] if cut > limit // 3 else p[:limit] + "…"
    return p


def _result(status: str, answer: str, *, claims=None, evidence=None, note=None, engine="extractive") -> dict[str, Any]:
    return {"status": status, "answer": answer, "claims": claims or [], "evidence": evidence or [], "note": note, "engine": engine}


def with_context(question: str, previous: str | None) -> str:
    """A short follow-up ("and if the trial is delayed?") is read together with the previous question."""
    q = question.strip()
    if previous and len(_W.findall(q.lower())) < 6 and not kinds_in(previous):
        return f"{previous.strip()} {q}"
    return q


def answer(db: Session, question: str, filters: CorpusFilters, actor, *, use_model: bool = True, ip: str | None = None) -> dict[str, Any]:
    task_id = new_task_id()
    q = question.strip()
    if kinds_in(q):
        return _result("INSUFFICIENT_EVIDENCE", INSUFFICIENT, note="Instruction-like requests are ignored; ask a legal question.")

    # 1. Named authority that must exist verbatim in the corpus (never invented).
    for cite in CITATION.findall(q):
        if not find_by_citation(db, cite):
            audit.record(db, action="legal.answer", result="success", actor=actor, task_id=task_id, agent="Research Agent",
                         verification_status="NOT_FOUND")
            return _result("NOT_FOUND", INSUFFICIENT, note=f"The cited authority “{cite.strip()}” is not in FormLaw's verified corpus. "
                                                           "FormLaw will not describe a judgment it cannot show you.")
    m = PARTIES.search(q)
    if m and not CITATION.search(q):
        a_words = m.group(1).split()
        while a_words and a_words[0] in _QWORDS:
            a_words.pop(0)
        a, b = " ".join(a_words), m.group(2).strip()
        if a and not find_by_parties(db, a, b):
            return _result("NOT_FOUND", INSUFFICIENT, note=f"No judgment titled “{a} v. {b}” is in the verified corpus.")

    # 2. Constitutional Articles come only from the imported constitutional layer.
    am = ARTICLE.search(q)
    if am:
        prov = db.scalar(select(ConstitutionProvision).where(ConstitutionProvision.kind == "article", ConstitutionProvision.number == am.group(1).upper()))
        if not prov or not prov.text:
            return _result("INSUFFICIENT_EVIDENCE", INSUFFICIENT,
                           note=f"Article {am.group(1)} is not available: the Constitution of India has not been imported yet "
                                "(the official source requires permission — see the source registry).")
        ev = {"evidence_id": "E1", "document_id": prov.id, "document_name": f"Constitution of India — Article {prov.number}" + (f": {prov.title}" if prov.title else ""),
              "kind": "constitution_article", "court": None, "date": prov.as_on_date.isoformat() if prov.as_on_date else None,
              "citation": f"Article {prov.number}", "page": None, "text": prov.text, "source": prov.source_name, "source_url": prov.source_url,
              "document_url": prov.source_url, "content_hash": prov.content_hash, "data_class": "VERIFIED_SOURCE"}
        return _result("SUPPORTED", prov.text, claims=[{"text": prov.text, "evidence_ids": ["E1"], "status": "SUPPORTED"}], evidence=[ev],
                       note=f"Article {prov.number}, Constitution of India (as on {ev['date'] or 'unknown date'}).")

    # 3. Retrieval over judgments / statutes.
    embedder = get_embedder()
    hits = search_corpus(db, q, filters, k=6, embedder=embedder)
    # Relevance gate: most of the question's specific terms must appear in a passage (generic legal words don't count).
    q_terms = _stems(q)
    hits = [h for h in hits if q_terms and len(q_terms & _stems(h.chunk.text)) / len(q_terms) >= 0.5]
    if not hits:
        return _result("INSUFFICIENT_EVIDENCE", INSUFFICIENT, note="No passage in the verified corpus addresses this question.")
    evidence = [h.evidence(f"E{i + 1}") for i, h in enumerate(hits)]
    by_id = {e["evidence_id"]: e for e in evidence}

    router = get_router() if use_model else None
    if router:
        try:
            system, _refs = prompts.system_prompt("grounded_answer")
            parsed, _tokens, _model = router.generate("compose", system_prompt=system, schema=GroundedAnswer, user_prompt=prompts.user_message(
                request=q, passages=[prompts.PromptPassage(e["evidence_id"], f"{e['document_name']} ({e['neutral_citation'] or e['citation'] or ''}) p.{e['page']}", e["text"]) for e in evidence]))
            claims, kept = [], []
            for s in parsed.sentences:
                ids = [i for i in s.evidence_ids if i in by_id]
                v = verify_claim(s.text, [by_id[i]["text"] for i in ids], citations=CITATION.findall(s.text),
                                 citation_exists=lambda c: bool(find_by_citation(db, c)))
                claims.append({"text": s.text, "evidence_ids": ids, "status": v.status})
                if v.status in ("SUPPORTED", "PARTIALLY_SUPPORTED") and not kinds_in(s.text):
                    kept.append(s.text)
            dropped = sum(c["status"] not in ("SUPPORTED", "PARTIALLY_SUPPORTED") for c in claims)
            if kept:
                used = sorted({i for c in claims if c["status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED") for i in c["evidence_ids"]})
                audit.record(db, action="legal.answer", result="success", actor=actor, task_id=task_id, agent="Research Agent",
                             tool="llm_generate", verification_status=f"{len(kept)} verified")
                return _result("SUPPORTED", " ".join(kept), claims=claims, evidence=[by_id[i] for i in used] or evidence, engine="llm",
                               note=f"{dropped} unsupported sentence(s) removed by the Verification Agent." if dropped else None)
            if parsed.sentences:
                return _result("INSUFFICIENT_EVIDENCE", INSUFFICIENT, claims=claims, evidence=evidence,
                               note="The model's sentences could not be verified against the retrieved passages, so none are shown.")
        except (LLMError, LLMOutputError) as e:
            log.warning("legal answer: model unavailable (%s); extractive answer", type(e).__name__)

    top = evidence[:2]
    audit.record(db, action="legal.answer", result="success", actor=actor, task_id=task_id, agent="Research Agent", verification_status="extractive",
                 ip=ip)
    return _result("SUPPORTED", "\n\n".join(_tidy(e["text"]) for e in top),
                   claims=[{"text": _tidy(e["text"]), "evidence_ids": [e["evidence_id"]], "status": "SUPPORTED"} for e in top],
                   evidence=evidence, note="Verbatim passages from the verified corpus (no model phrasing).")
