"""
Orchestrator runtime — an explicit state machine:

  START → SECURE_INPUT → CLASSIFY → PLAN → [EXECUTE → OBSERVE → ADAPT/REPLAN]* → VERIFY GATE → QUALITY CHECK → FINALIZE

The orchestrator does not do the work itself: it plans, delegates each step to the agent registered for the action,
observes the result, adapts the plan, and enforces budgets. No unverified claim can reach the final answer as a finding.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from ...core.config import AgentLimits
from ...domain.enums import ClaimStatus as S
from ...domain.enums import Intent, RunStatus
from ...llm.schemas import IntentOut
from ..base import StepResult
from ..orchestrator import intent as intent_mod
from ..orchestrator.composer import SPEC as ORCH_SPEC
from ..orchestrator.composer import Composer
from ..orchestrator.planner import StepFactory, build_plan, refine_with_model
from ..registry import BY_ACTION
from .budget import Budget, BudgetExceeded
from .context import AgentContext
from .events import EventType
from .gateway import Gateway, Tool
from .observers import observe
from .state import Blackboard, Cite, PlanStep

log = logging.getLogger("formlaw.orchestrator")
Emit = Callable[..., None]


@dataclass
class RunState:
    run_id: str
    task_id: str
    organization_id: str
    case_id: str
    user_id: str
    case_title: str
    matter_type: str
    goal: str
    limits: AgentLimits
    llm_enabled: bool
    forced_intent: Intent | None = None
    forced_params: dict[str, Any] = field(default_factory=dict)
    intent: Intent = Intent.EVIDENCE_QA
    topic: str = ""
    draft_kind: str = ""
    wants_research: bool = False
    plan: list[PlanStep] = field(default_factory=list)
    board: Blackboard = field(default_factory=Blackboard)
    documents: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    engines: set[str] = field(default_factory=set)
    prompt_refs: set[str] = field(default_factory=set)
    rationale: str = ""
    status: RunStatus = RunStatus.RUNNING
    stop_reason: str | None = None
    make_step: StepFactory = field(default_factory=StepFactory)
    budget: Budget = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.budget = Budget(self.limits)

    def note_failure(self, agent: str, kind: str) -> None:
        self.failures.append({"agent": agent, "kind": kind})

    def board_topic(self, cid: str) -> str:
        c = next((x for x in self.board.contradictions if x.id == cid), None)
        return c.topic.lower() if c else "conflict"


class Orchestrator:
    def __init__(self, tools: dict[str, Tool], emit: Emit):
        self.tools, self.emit = tools, emit

    # ------------------------------------------------------------------ run
    def run(self, st: RunState) -> dict[str, Any]:
        self.gateway = Gateway(self.tools, st.budget, st.limits.max_retries,
                               on_retry=lambda a, t, n: self.emit(EventType.ADAPT, agent="Orchestrator",
                                                                  summary=f"{t} failed transiently → retrying ({n}/{st.limits.max_retries})"))
        self.emit(EventType.RUN_STARTED, agent="Orchestrator", summary="Request received", data={"goal": st.goal[:300]})
        try:
            if not self._secure_input(st):
                st.status = RunStatus.REFUSED
                return self._finalize(st)
            self._classify(st)
            self._plan(st)
            self._execute(st)
            self._verification_gate(st)
            self._quality_check(st)
            st.status = RunStatus.PARTIAL if any(s.status == "failed" for s in st.plan) else RunStatus.COMPLETED
        except BudgetExceeded as e:
            st.status, st.stop_reason = RunStatus.PARTIAL, f"Stopped safely: {e.which} reached"
            self.emit(EventType.ADAPT, agent="Orchestrator", summary=f"{e.which} reached → stopping safely with verified partial results")
            for s in st.plan:
                if s.status == "pending":
                    s.status = "skipped"
            self._salvage(st)
        return self._finalize(st)

    def _salvage(self, st: RunState) -> None:
        """
        A limit was reached. Rather than return nothing, finish from the evidence already gathered without the model:
        verify claims against their sources (verbatim check) and compose the answer from verified items only.
        """
        if st.board.answer is not None and not any(c.status == S.UNVERIFIED and c.citations for c in st.board.claims):
            return
        st.llm_enabled = False
        st.budget.grace()
        try:
            self._verification_gate(st)
            self._quality_check(st)
        except BudgetExceeded:
            log.warning("run %s: wrap-up after %s also exceeded its allowance", st.run_id, st.stop_reason)

    # ------------------------------------------------------------ phases
    def _secure_input(self, st: RunState) -> bool:
        step = st.make_step("security.scan_request", "Check the request for embedded instructions")
        st.plan.append(step)
        res = self._dispatch(st, step)
        if res.status == "failed":
            self.emit(EventType.SECURITY, agent="Security Agent", summary=res.summary, data=res.signals)
            return False
        return True

    def _classify(self, st: RunState) -> None:
        if st.forced_intent:
            r = intent_mod.classify_rules(st.goal)
            r.intent = st.forced_intent
            r.draft_kind = st.forced_params.get("draft_kind") or r.draft_kind or ("case_summary" if st.forced_intent == Intent.DRAFT else "")
            r.engine = "workflow"
        else:
            r = intent_mod.classify_rules(st.goal)
            ctx = AgentContext(st, ORCH_SPEC, self.gateway)
            out = ctx.llm("classify", "intent", IntentOut, request=st.goal)
            if out is not None and out.intent != "OUT_OF_SCOPE":
                r = intent_mod.IntentResult(Intent(out.intent), [Intent(i) for i in out.secondary], out.topic or r.topic,
                                            out.draft_kind or r.draft_kind, out.wants_research or r.wants_research, "llm")
                st.engines.update(ctx.engines)
        st.intent, st.topic, st.draft_kind, st.wants_research = r.intent, r.topic, r.draft_kind, r.wants_research
        if st.intent == Intent.DRAFT and not st.draft_kind:
            st.draft_kind = "case_summary"
        self.emit(EventType.INTENT, agent="Orchestrator", summary=f"Understood as {st.intent.value.replace('_', ' ').lower()}"
                  + (f" — topic: {st.topic}" if st.topic else ""),
                  data={"intent": st.intent.value, "secondary": [i.value for i in r.secondary], "topic": st.topic, "engine": r.engine})

    def _plan(self, st: RunState) -> None:
        st.documents = self.gateway.call(agent="Orchestrator", allowed=frozenset({"list_documents"}), step_id=None, tool="list_documents")
        ctx = AgentContext(st, ORCH_SPEC, self.gateway)
        st.rationale = refine_with_model(st, ctx.llm) or ""
        st.engines.update(ctx.engines)
        steps = build_plan(st, st.make_step)
        # Case memory: a conflict found in an earlier run on this topic is re-checked, not forgotten.
        if st.intent == Intent.EVIDENCE_QA and st.topic:
            words = {w for w in st.topic.lower().split() if len(w) > 3}
            prior = [m for m in st.board.memory if m.get("kind") == "open_contradiction"
                     and words & set(m.get("topic", "").lower().split())]
            if prior:
                steps.insert(1, st.make_step("contradiction.detect", "Re-check the conflict recorded in case memory", "adapt",
                                             "Case memory holds an open conflict on this topic", topic=st.topic))
                self.emit(EventType.ADAPT, agent="Orchestrator",
                          summary=f"Case memory: an earlier run found a conflict on {prior[0]['topic'].lower()} → adding a contradiction check")
        st.plan.extend(steps)
        if not st.rationale:
            st.rationale = f"{len(steps)} steps: " + " → ".join(s.label.split(' ')[0].lower() for s in steps)
        self.emit(EventType.PLAN, agent="Orchestrator", summary=st.rationale,
                  data={"steps": [s.public() for s in st.plan]})

    def _execute(self, st: RunState) -> None:
        while True:
            step = next((s for s in st.plan if s.status == "pending"), None)
            if step is None:
                return
            result = self._dispatch(st, step)
            for a in observe(st, step, result):
                at = st.plan.index(step) + 1
                st.plan[at:at] = a.steps
                self.emit(EventType.REPLAN if a.kind == "replan" else EventType.ADAPT, agent="Orchestrator", summary=a.message,
                          data={"inserted": [s.public() for s in a.steps]})

    def _dispatch(self, st: RunState, step: PlanStep) -> StepResult:
        st.budget.step()
        agent = BY_ACTION[step.action]
        step.status, step.attempts = "running", step.attempts + 1
        self.emit(EventType.STEP_STARTED, agent=agent.spec.name, step_id=step.id, summary=step.label, data={"action": step.action, "origin": step.origin})
        ctx = AgentContext(st, agent.spec, self.gateway, step.id)
        try:
            result = agent.run(ctx, step)
        except BudgetExceeded:
            step.status = "failed"
            raise
        except Exception as e:  # an agent failure never crashes the run; it is recorded and the plan continues
            log.exception("agent %s failed on %s", agent.spec.name, step.action)
            st.note_failure(agent.spec.name, type(e).__name__)
            result = StepResult("failed", f"{agent.spec.name} failed ({type(e).__name__}); continuing without it")
        if ctx.engines:
            result.engine = ctx.engines[-1]
            st.engines.update(ctx.engines)
        step.status = "failed" if result.status == "failed" and step.action != "security.scan_request" else "done" if result.status != "skipped" else "skipped"
        step.summary = result.summary
        safe = {k: v for k, v in result.signals.items() if isinstance(v, (int, float, str, bool, list))}
        self.emit(EventType.STEP_FAILED if result.status == "failed" else EventType.STEP_COMPLETED, agent=agent.spec.name, step_id=step.id,
                  summary=result.summary, data={"status": result.status, "engine": result.engine, "signals": safe})
        if result.signals.get("security_findings"):
            self.emit(EventType.SECURITY, agent="Security Agent", summary=result.summary, data=safe)
        if step.action == "verification.verify":
            self.emit(EventType.VERIFICATION, agent="Verification Agent", summary=result.summary, data=safe)
        return result

    def _verification_gate(self, st: RunState) -> None:
        """No claim leaves the run unverified when it has evidence to be checked against."""
        if any(c.status == S.UNVERIFIED and (c.citations or c.authority_ids or c.meta.get("derived")) for c in st.board.claims) or \
                any(a.status == S.UNVERIFIED for a in st.board.authorities):
            step = st.make_step("verification.verify", "Verification gate: check remaining claims", "gate")
            st.plan.append(step)
            self._dispatch(st, step)

    def _quality_check(self, st: RunState) -> None:
        b = st.board
        if b.answer is None:
            step = st.make_step("answer.compose", "Compose the answer", "gate")
            st.plan.append(step)
            self._dispatch(st, step)
            self._verification_gate(st)
        if b.answer is None:  # composition failed twice: say so rather than guess
            from .state import Answer
            b.answer = Answer("FormLaw could not compose an answer for this request. The evidence and findings below are still verified.")
        # Final guard: answer statements that failed verification are moved out of the answer, never shown as findings.
        keep = [cid for cid in b.answer.claim_ids if (c := b.claim(cid)) and (c.verified or c.kind == "summary")]
        b.answer.claim_ids = keep
        summ = b.claim(keep[0]) if keep else None
        if summ is not None and summ.kind == "summary" and not summ.verified:
            b.answer.limitations.insert(0, "The model's summary could not be verified against the evidence and was withheld.")
            b.answer.summary = "Findings below are each verified against the cited documents; no overall summary could be verified."

    # ---------------------------------------------------------- finalize
    def _finalize(self, st: RunState) -> dict[str, Any]:
        result = build_result(st)
        self.emit(EventType.RUN_COMPLETED if st.status != RunStatus.FAILED else EventType.RUN_FAILED, agent="Orchestrator",
                  summary={"completed": "Completed", "partial": st.stop_reason or "Completed with some steps failed",
                           "refused": "Request refused by security policy"}.get(st.status.value, st.status.value),
                  data={"status": st.status.value})
        return result


def _cite_out(st: RunState, cite) -> dict[str, Any] | None:
    h = st.board.evidence.get(cite.chunk_id)
    if not h:
        return None
    return {"chunkId": h.chunk_id, "documentId": h.document_id, "documentName": h.document_name, "page": h.page,
            "paragraph": h.paragraph, "section": h.section, "quote": cite.quote}


def _claim_out(st: RunState, c) -> dict[str, Any]:
    return {"id": c.id, "text": c.text, "kind": c.kind, "agent": c.agent, "status": c.status, "confidence": c.confidence,
            "reason": c.reason, "citations": [x for x in (_cite_out(st, ci) for ci in c.citations) if x],
            "authorityIds": c.authority_ids, "meta": c.meta}


ASSESSMENT_LABEL = {
    "strong": "Strong documentary support", "partial": "Partial support", "conflicting": "Conflicting evidence",
    "insufficient": "Insufficient evidence", "not_assessed": "Not assessed",
}
_SCOPE_NOTE = " This describes the support in the reviewed documents only — not whether their contents are true."


def _assessment(st: RunState, stmt: list, level: str) -> dict[str, str]:
    """
    Documentary-support assessment for the answer as a whole, with its basis. Quote accuracy is not truth: a verified
    quote shows that a document says something, not that it is so, nor how strong a legal position is.
    """
    b, ans = st.board, st.board.answer
    if st.status == RunStatus.REFUSED:
        key, why = "not_assessed", "The request was refused before any document was reviewed."
    elif ans and ans.assessment == "not_assessed":
        key, why = "not_assessed", "The case material is an unfilled template, so there is no case-specific content to assess."
    elif not b.evidence and not b.templates and st.intent != Intent.LEGAL_RESEARCH:
        key, why = "not_assessed", "No readable case document was available to review."
    elif st.intent == Intent.LEGAL_RESEARCH and not stmt:
        n = sum(a.status == S.SUPPORTED for a in b.authorities)
        key, why = ("partial", f"{n} passage(s) were re-read from FormLaw's verified Supreme Court corpus. Whether they apply to "
                    "this case, and whether they remain good law, has not been independently verified.") if n else \
                   ("insufficient", "No passage in FormLaw's verified legal corpus addresses this issue; no authority was generated.")
    elif b.contradictions and Composer._conflict_leads(SimpleNamespace(board=b, state=st)):  # the conflict bears on the question
        key, why = "conflicting", (f"The documents disagree on {b.contradictions[0].topic.lower()}"
                                   + (f" and {len(b.contradictions) - 1} other point(s)" if len(b.contradictions) > 1 else "")
                                   + "; both sides are cited and FormLaw does not choose between them.")
    elif level == "low":
        key, why = "insufficient", "The reviewed documents do not establish an answer to this question."
    elif level == "high":
        key, why = "strong", (f"Each of the {len(stmt)} statement(s) is traceable to a passage that was checked against its source, "
                              "and no conflicting passage was found in the reviewed documents.")
    else:
        key, why = "partial", "Some statements are supported only in part by their sources, or need more context."
    if b.contradictions and key in ("strong", "partial"):
        why += f" Separately, the documents conflict on {b.contradictions[0].topic.lower()}."
    return {"level": key, "label": ASSESSMENT_LABEL[key], "reason": why + (_SCOPE_NOTE if key in ("strong", "partial") else "")}


NOT_FOUND = "Not found in the provided documents."


def _lead_lower(s: str) -> str:
    """Lower-case a leading capital for mid-sentence use, but keep acronyms ("FIR", "CCTV footage")."""
    return s[:1].lower() + s[1:] if s[:2] and not s[:2].isupper() else s
DETAIL_FIELDS = [("case_number", "Case number"), ("court", "Court"), ("jurisdiction", "Jurisdiction"), ("case_type", "Case type"),
                 ("police_station", "Police station"), ("procedural_status", "Procedural status")]


def _report(st: RunState, unverified: list) -> dict[str, Any]:
    """
    Structured case report (case review / summary): every overview field carries its source or says it was not found;
    next steps follow from what the evidence lacks. Nothing here is generated beyond the verified board.
    """
    b = st.board
    cite = lambda chunk_id, quote: _cite_out(st, Cite(chunk_id, quote))  # noqa: E731
    fields = []
    for key, label_ in DETAIL_FIELDS:
        hit = next((d for d in b.case_details if d["field"] == key), None)
        fields.append({"key": key, "label": label_, "value": hit["value"] if hit else None,
                       "citation": cite(hit["chunkId"], hit["quote"]) if hit else None})
    provisions = [{"value": d["value"], "citation": cite(d["chunkId"], d["quote"])} for d in b.case_details if d["field"] == "provision"]
    parties = [{"name": p["name"], "role": p["role"], "citation": cite(p["chunkId"], p["name"])} for p in b.parties[:20]]

    steps: list[str] = []
    template_only = bool(b.answer and b.answer.assessment == "not_assessed" and b.templates)
    if template_only:
        steps.append("Upload the completed case documents — the filled case form, FIR or complaint, contracts, statements, "
                     "notices and orders — so the actual parties, facts and evidence can be analysed.")
    for x in b.contradictions[:3]:
        ea, eb = b.evidence.get(x.a.cite.chunk_id), b.evidence.get(x.b.cite.chunk_id)
        steps.append(f"Resolve the conflict on {x.topic.lower()}: {x.a.value}" + (f" ({ea.document_name})" if ea else "") +
                     f" vs {x.b.value}" + (f" ({eb.document_name})" if eb else "") + " — obtain an independent record.")
    for m in sorted((m for m in b.missing if m.basis != "template_field"), key=lambda m: m.importance != "high")[:4]:
        steps.append(f"Obtain the {_lead_lower(m.title)}: {m.why}")
    for d in st.documents:
        if d.get("status") in ("needs_ocr", "failed"):
            steps.append(f"Provide a readable (text or OCR) copy of {d['name']}; it has not been reviewed.")
    if any(c.kind == "allegation" for c in b.claims if c.verified):
        steps.append("Test the allegations recorded in the documents against independent evidence before relying on them.")
    if unverified:
        steps.append(f"Check the {len(unverified)} statement(s) that failed verification against the source documents.")
    if provisions:
        steps.append(f"Verify the provisions cited in the documents ({', '.join(p['value'] for p in provisions[:4])}) against "
                     "the current official text; FormLaw has not independently verified them.")
    steps.append("Have a qualified lawyer review these findings before relying on them.")

    docs = st.documents
    return {
        "overview": {"title": st.case_title, "matterType": st.matter_type, "fields": fields, "provisions": provisions, "parties": parties},
        "nextSteps": steps[:9],
        "documents": {
            "reviewed": sorted({e.document_name for e in b.evidence.values()}),
            "templates": sorted({h.document_name for h in b.templates.values()} | {d["name"] for d in docs if d.get("docType") == "template"}),
            "unreadable": [d["name"] for d in docs if d.get("status") in ("needs_ocr", "failed")],
            "total": len(docs),
        },
        "notFound": NOT_FOUND,
    }


def build_result(st: RunState) -> dict[str, Any]:
    b = st.board
    ans = b.answer
    answer_claims = [b.claim(i) for i in (ans.claim_ids if ans else [])]
    answer_claims = [c for c in answer_claims if c]
    shown = {c.id for c in answer_claims}
    stmt = [c for c in answer_claims if c.kind != "summary"]
    unverified = [c for c in b.claims if not c.verified and c.id not in shown and (c.citations or c.kind in ("answer", "summary"))]

    if st.status == RunStatus.REFUSED:
        level, why = "low", "The request was refused before any evidence was used."
    elif not stmt and not b.contradictions and not [a for a in b.authorities if a.status == S.SUPPORTED]:
        level, why = "low", "Insufficient evidence in the case documents."
    elif all(c.status == S.SUPPORTED for c in stmt):
        level, why = "high", "Every statement is quoted from, and verified against, its source document."
        if b.contradictions:
            why += " The sources conflict; FormLaw reports both sides and does not choose."
    else:
        level, why = "medium", "Some statements are only partially supported by their sources."

    assessment = _assessment(st, stmt, level)
    limitations = list(ans.limitations) if ans else []
    if b.templates and not (ans and ans.assessment == "not_assessed"):
        forms = sorted({h.document_name for h in b.templates.values()})
        limitations.append(f"{len(b.templates)} passage(s) of unfilled template text ({', '.join(forms[:3])}) were excluded; "
                           "placeholders are not case facts.")
    unreadable = [d for d in st.documents if d.get("status") in ("needs_ocr", "failed")]
    if unreadable:
        limitations.append(f"{', '.join(d['name'] for d in unreadable)} could not be read (scanned or unreadable); "
                           "its contents were not reviewed.")
    if any(c.kind in ("allegation", "disputed") for c in stmt):
        limitations.append("Some statements are allegations recorded in the documents; that a document records them does "
                           "not establish that they are true.")

    reasons = []
    if b.contradictions:
        reasons.append(f"{len(b.contradictions)} unresolved conflict(s) in the evidence")
    if unverified:
        reasons.append(f"{len(unverified)} statement(s) could not be verified")
    if b.security:
        reasons.append("A document contains instructions aimed at the AI")
    if any(m.importance == "high" for m in b.missing):
        reasons.append("Key records are missing")
    if b.draft:
        reasons.append("Draft requires lawyer review before use")

    actions = []
    if b.evidence:
        actions.append({"kind": "view_evidence", "label": "View evidence"})
    if st.intent != Intent.LEGAL_RESEARCH:
        actions.append({"kind": "research", "label": "Research authority", "prompt": f"Find authorities on {st.topic or 'the main legal issue'}"})
    if b.timeline and st.intent != Intent.TIMELINE:
        actions.append({"kind": "timeline", "label": "Build timeline", "prompt": "Build a timeline of events"})
    if b.contradictions and st.intent != Intent.DRAFT:
        actions.append({"kind": "draft", "label": "Cross-examination questions", "prompt": "Prepare questions for cross examination on the contradictions"})
    if st.intent != Intent.DRAFT:
        actions.append({"kind": "draft", "label": "Generate report", "prompt": "Summarize the case for senior counsel"})

    cited_ids = {ci.chunk_id for c in b.claims for ci in c.citations} | {x.a.cite.chunk_id for x in b.contradictions} | \
                {x.b.cite.chunk_id for x in b.contradictions} | {t.cite.chunk_id for t in b.timeline} | \
                {m.cite.chunk_id for m in b.missing if m.cite}
    evidence = [e.as_dict() for e in b.evidence.values() if e.chunk_id in cited_ids or e.flagged]
    return {
        "runId": st.run_id, "taskId": st.task_id, "intent": st.intent.value, "topic": st.topic, "status": st.status.value,
        "stopReason": st.stop_reason, "rationale": st.rationale,
        "plan": [s.public() for s in st.plan],
        "answer": {
            "summary": ans.summary if ans else ("Request refused." if st.status == RunStatus.REFUSED else "No answer could be composed."),
            "claimIds": [c.id for c in stmt], "limitations": limitations,
            "confidence": {"level": level, "reason": why},  # legacy field; clients show `assessment`
            "assessment": assessment,
            "requiresLawyerReview": bool(reasons), "reviewReasons": reasons,
        },
        "report": _report(st, unverified) if st.intent in (Intent.CASE_REVIEW, Intent.SUMMARY) else None,
        "claims": [_claim_out(st, c) for c in b.claims if c.kind != "summary"],
        "unverified": [_claim_out(st, c) for c in unverified],
        "contradictions": [{"id": x.id, "topic": x.topic, "nature": x.nature, "confidence": x.confidence, "explanation": x.explanation,
                            "a": {"value": x.a.value, "statement": x.a.statement, "citation": _cite_out(st, x.a.cite)},
                            "b": {"value": x.b.value, "statement": x.b.statement, "citation": _cite_out(st, x.b.cite)},
                            "provenance": x.provenance} for x in b.contradictions],
        "missing": [{"id": m.id, "title": m.title, "why": m.why, "basis": m.basis, "importance": m.importance,
                     "citation": _cite_out(st, m.cite) if m.cite else None} for m in b.missing],
        "contractGaps": b.contract_missing,
        "timeline": [{"id": t.id, "dateText": t.date_text, "date": t.date_iso, "description": t.description, "eventType": t.event_type,
                      "status": t.status, "citation": _cite_out(st, t.cite)} for t in sorted(b.timeline, key=lambda t: (t.date_iso or "9999", t.id))],
        "parties": b.parties[:30],
        "authorities": [{"id": a.id, "legalDocumentId": a.legal_document_id, "legalChunkId": a.legal_chunk_id, "type": a.authority_type, "title": a.title, "citation": a.citation, "court": a.court,
                         "date": a.decision_date, "page": a.page, "quote": a.quote, "source": a.source_name, "sourceUrl": a.source_url,
                         "license": a.license, "contentHash": a.content_hash, "status": a.status, "issue": a.issue} for a in b.authorities],
        "draft": None if not b.draft else {"kind": b.draft.kind, "title": b.draft.title, "facts": b.draft.facts,
                                           "authorities": b.draft.authorities, "inferences": b.draft.inferences,
                                           "recommendations": b.draft.recommendations, "body": b.draft.body},
        "evidence": evidence,
        "security": [{"kind": s.kind, "source": s.source, "snippet": s.snippet, "chunkId": s.chunk_id, "action": s.action} for s in b.security],
        "actions": actions,
        "stats": {"steps": st.budget.steps, "toolCalls": st.budget.tool_calls, "replans": st.budget.replans, "tokens": st.budget.tokens,
                  "latencyMs": st.budget.elapsed_ms, "engines": sorted(st.engines) or ["deterministic"], "prompts": sorted(st.prompt_refs),
                  "evidenceConsidered": len(b.evidence), "failures": st.failures},
    }
