"""
Grounded chat over a case. Answers come only from the case's (non-quarantined) documents. With an LLM
configured, the model may phrase the answer, but every sentence is re-verified against the passages it
cites and unsupported sentences are dropped. Without an LLM the answer is extractive (verbatim evidence).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.engine.chunking import DocText, chunk_documents
from ..agents.gateway import AgentRun
from ..agents.llm.prompts import GROUNDED_ANSWER_SYSTEM, GroundedAnswer, grounded_user_prompt
from ..agents.llm.provider import LLMError, LLMOutputError, get_provider
from ..core.config import get_settings
from ..models import Case, Contradiction, Document, Evidence, MissingInformation
from ..retrieval.hybrid import Passage, content_hash, search
from ..security.injection import kinds_in
from ..verification.groundedness import verify_claim
from . import audit
from .review import new_task_id
from .serializers import latest_run

log = logging.getLogger("formlaw.chat")
STEPS = ["Orchestrator understood request", "Retrieval Agent searching evidence", "Verification Agent checking claims"]


def _ev(p: Passage, label: str) -> dict[str, Any]:
    return {"id": label, "doc_id": p.document_id, "doc_name": p.document_name, "page": p.page or 1, "excerpt": p.text,
            "highlight": p.text[:60], "content_hash": content_hash(p.text)}


def answer(db: Session, case: Case, question: str, history: list[str], actor) -> dict[str, Any]:
    run = AgentRun(new_task_id(), get_settings().limits)
    steps = list(STEPS)
    last = latest_run(db, case.id)
    lq = question.lower()

    if kinds_in(question):
        audit.record(db, action="chat.injection_attempt", result="blocked", actor=actor, resource_type="case", resource_id=case.id,
                     risk="MEDIUM", task_id=run.task_id, agent="Chat Agent")
        return _out("insufficient", "FormLaw answers questions about your case documents. Requests to change its rules or reveal its instructions are ignored.",
                    [], [], steps, engine="extractive", note="This request was logged.")

    # Known conflicts win: never pick one side of a contradiction.
    if last:
        q_words = set(re.findall(r"[a-z]{4,}", lq))
        for c in db.scalars(select(Contradiction).where(Contradiction.run_id == last.id)):
            topic_words = set(re.findall(r"[a-z]{4,}", c.topic.lower())) - {"date", "time", "name"}
            # Prefix match so "arrested" / "arrest" refer to the same topic.
            on_topic = any(q.startswith(t) or t.startswith(q) for q in q_words for t in topic_words)
            if on_topic or re.search(r"contradict|conflict|inconsisten", lq):
                ea, eb = db.get(Evidence, c.evidence_a), db.get(Evidence, c.evidence_b)
                steps += ["Contradiction Agent comparing evidence", "Conflict detected → replanning, searching for additional evidence"]
                return _out("conflicted",
                            f"The supplied case documents contain conflicting {c.topic.lower()}s. One document states {c.claim_a}; another states {c.claim_b}.",
                            [ea.label, eb.label], [], steps, engine="extractive",
                            note="FormLaw cannot reliably select one value without additional evidence.")
        if re.search(r"\b(missing|gap|lack)", lq):
            items = db.scalars(select(MissingInformation).where(MissingInformation.run_id == last.id).order_by(MissingInformation.ordinal)).all()
            steps.append("Missing Information Agent analysing gaps")
            text = f"The record is missing: {'; '.join(m.title for m in items)}." if items else "No critical gaps were found against the checklist."
            return _out("supported", text, [], [], steps, engine="extractive")

    docs = db.scalars(select(Document).where(Document.case_id == case.id, Document.processing_status == "extracted")).all()
    chunks = run.call("Chat Agent", "search_case_evidence", chunk_documents,
                      [DocText(d.id, d.filename, d.extracted_text) for d in docs])
    passages = [Passage(f"Q{i}", c.sentence, c.doc_id, c.doc_name, page=c.page) for i, c in enumerate(chunks)]
    query = " ".join([*history[-3:], question])
    hits = run.call("Chat Agent", "search_case_evidence", search, passages, query, k=4)
    hits = [h for h in hits if h[1] > 0][:4]
    if not hits:
        return _out("insufficient", "We couldn’t verify an answer. The available evidence is insufficient.", [], [], steps,
                    engine="extractive", note="Recommended: upload the document that addresses this question.")

    labels = {p.id: f"Q{n + 1}" for n, (p, _) in enumerate(hits)}
    evidence = [_ev(p, labels[p.id]) for p, _ in hits]
    provider = get_provider()
    verification: list[dict[str, Any]] = []
    if provider:
        try:
            parsed, tokens = run.call("Chat Agent", "llm_generate", provider.generate_structured, retryable=(LLMError,),
                                      system_prompt=GROUNDED_ANSWER_SYSTEM,
                                      user_prompt=grounded_user_prompt(question, [(labels[p.id], f"{p.document_name} p.{p.page}", p.text) for p, _ in hits]),
                                      schema=GroundedAnswer)
            run.spend_tokens(tokens)
            by_label = {labels[p.id]: p.text for p, _ in hits}
            kept, cited = [], []
            for s in parsed.sentences:
                ids = [i for i in s.evidence_ids if i in by_label]
                v = verify_claim(s.text, [by_label[i] for i in ids])
                verification.append({"sentence": s.text, "status": v.status, "evidence_ids": ids})
                if v.status in ("SUPPORTED", "PARTIALLY_SUPPORTED") and not kinds_in(s.text):
                    kept.append(s.text)
                    cited += ids
            dropped = len(parsed.sentences) - len(kept)
            if kept:
                audit.record(db, action="chat.answer", result="success", actor=actor, resource_type="case", resource_id=case.id,
                             task_id=run.task_id, agent="Chat Agent", tool="llm_generate", verification_status=f"{len(kept)} verified")
                return _out("supported", " ".join(kept), sorted(set(cited)), [e for e in evidence if e["id"] in cited], steps, engine="llm",
                            note=f"{dropped} unsupported sentence(s) removed by the Verification Agent." if dropped else None,
                            verification=verification)
        except (LLMError, LLMOutputError) as e:
            log.warning("LLM answer failed (%s); using extractive answer", type(e).__name__)

    audit.record(db, action="chat.answer", result="success", actor=actor, resource_type="case", resource_id=case.id,
                 task_id=run.task_id, agent="Chat Agent", verification_status="extractive")
    return _out("supported", " ".join(p.text for p, _ in hits), [e["id"] for e in evidence], evidence, steps, engine="extractive",
                note="Answer composed only of retrieved document text.",
                verification=[{"sentence": p.text, "status": "SUPPORTED", "evidence_ids": [labels[p.id]]} for p, _ in hits])


def _out(status: str, text: str, ids: list[str], evidence: list[dict], steps: list[str], *, engine: str,
         note: str | None = None, verification: list[dict] | None = None) -> dict[str, Any]:
    return {"status": status, "text": text, "evidence_ids": ids, "evidence": evidence, "sources": sorted({f"{e['doc_name']} p.{e['page']}" for e in evidence}),
            "note": note, "steps": steps, "engine": engine, "verification": verification or []}
