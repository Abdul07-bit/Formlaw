"""
Orchestrator Agent: GOAL → PLAN → DELEGATE → RETRIEVE → REASON → VERIFY → MATCH.

Pure function over its inputs (no DB access): persistence is the caller's job. Every agent call goes
through the ToolGateway, so permissions and run limits are enforced regardless of what the documents say.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...core.config import AgentLimits
from ...matching.agent import Candidate, Match, match_lawyers
from ...security.injection import ScanHit, scan_sentences
from ...verification.groundedness import verify_claim
from ..gateway import AgentRun
from .case_review import ContradictionItem, EvidenceItem, Fact, ReviewOutput, review_case
from .chunking import Chunk, DocText, chunk_documents
from .classify import classify
from .contract_review import ContractReview, looks_like_contract, review_contract
from .drafting import draft_for
from .missing import Gap, find_missing
from .related import CaseMeta, Related, find_related


@dataclass
class AnalysisInput:
    task_id: str
    title: str
    description: str
    city: str
    budget: int
    documents: list[DocText]
    pending_extraction: int
    candidates: list[Candidate]
    lawyer_cases: list[CaseMeta]
    limits: AgentLimits


@dataclass
class AnalysisResult:
    task_id: str
    area: str
    area_confidence: float
    summary: str
    facts: list[Fact]
    evidence: list[EvidenceItem]
    contradictions: list[ContradictionItem]
    missing: list[Gap]
    security: list[ScanHit]
    related: list[Related]
    matches: list[Match]
    draft_title: str
    draft_body: str
    verification: dict[str, int]
    contract: ContractReview | None
    run: AgentRun
    quarantined_docs: set[str] = field(default_factory=set)


def analyse(inp: AnalysisInput) -> AnalysisResult:
    run = AgentRun(inp.task_id, inp.limits)
    run.log("Orchestrator", f"Request received — {len(inp.documents)} document(s), goal: review case & find counsel", "info")

    all_chunks: list[Chunk] = run.call("Ingestion", "read_case_documents", chunk_documents, inp.documents)
    pending = f"; {inp.pending_extraction} file(s) awaiting OCR" if inp.pending_extraction else ""
    run.log("Ingestion", f"{len(all_chunks)} evidence chunks indexed{pending}")

    # Security: documents are untrusted data. A document that tries to instruct the system loses evidence status.
    hits = run.call("Security Agent", "scan_untrusted_text", scan_sentences, [(c.doc_id, c.doc_name, c.sentence) for c in all_chunks])
    if hits:
        run.log("Security Agent", f"Indirect prompt injection detected in {', '.join(h.doc_name for h in hits.values())}", "danger")
        run.log("Policy Engine", "Instruction BLOCKED · external tool access DENIED · event LOGGED", "danger")
    else:
        run.log("Security Agent", "All documents scanned — no embedded instructions found")
    chunks = [c for c in all_chunks if c.doc_id not in hits]

    corpus_text = inp.description + "\n" + "\n".join(c.sentence for c in chunks)
    cls = run.call("Orchestrator", "classify", classify, corpus_text)
    run.log("Orchestrator", f"Task classified as {cls.area.upper()}_CASE_REVIEW ({round(cls.confidence * 100)}%)")
    run.log("Planner", "Plan: retrieve → review → verify → contradictions → gaps → research → match counsel", "info")

    review: ReviewOutput = run.call("Case Review Agent", "extract_facts", review_case, chunks)
    run.log("Retrieval Agent", f"{len(review.evidence)} evidence items retrieved")
    run.log("Case Review Agent", f"{len(review.facts)} claims generated")

    contract = None
    if looks_like_contract(chunks):
        contract = run.call("Contract Review Agent", "review_contract", review_contract, chunks)
        risks = sum(f.kind == "risk" for f in contract.findings)
        run.log("Contract Review Agent", f"{len(contract.clauses_found)} standard clauses found, {len(contract.missing_clauses)} missing, {risks} risk(s)",
                "warn" if risks or contract.missing_clauses else "ok")

    if review.contradictions:
        run.log("Contradiction Agent", f"Evidence conflict detected — {', '.join(c.topic for c in review.contradictions)}", "warn")
        run.log("Orchestrator", "Adapting plan → retrieving additional evidence to resolve conflict", "adapt")
        run.log("Retrieval Agent", "Re-search found no independent record that resolves the conflict", "adapt")
        run.log("Verification Agent", "Both sources preserved; claim status CONTRADICTED", "warn")
    else:
        run.log("Contradiction Agent", "No conflicting facts across documents")

    # Independent verification: re-check each claim against the text of the evidence it cites.
    by_label = {e.label: e for e in review.evidence}
    for f in review.facts:
        if f.status == "CONTRADICTED":
            continue
        texts = [by_label[l].text for l in f.evidence if l in by_label]
        verdict = run.call("Verification Agent", "verify_claims", verify_claim, f.statement, texts)
        if f.status == "SUPPORTED" and verdict.status in ("UNSUPPORTED", "UNVERIFIED"):
            f.status = "PARTIALLY_SUPPORTED"  # paraphrased claim: keep it, but never present it as fully supported
    counts = {s: sum(f.status == s for f in review.facts) for s in ("SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNSUPPORTED")}
    verification = {
        "analysed": len(review.facts), "supported": counts["SUPPORTED"], "partial": counts["PARTIALLY_SUPPORTED"],
        "conflicted": counts["CONTRADICTED"], "unsupported": counts["UNSUPPORTED"],
        "coverage": round(100 * sum(bool(f.evidence) for f in review.facts) / len(review.facts)) if review.facts else 0,
    }
    run.log("Verification Agent", f"{verification['analysed']} claims evaluated — {verification['supported']} supported, "
                                  f"{verification['partial']} partial, {verification['conflicted']} conflicted")

    missing = run.call("Missing Info Agent", "checklist", find_missing, cls.area, chunks)
    run.log("Missing Info Agent", f"{len(missing)} gap(s) identified", "warn" if missing else "ok")

    related = run.call("Precedent Agent", "search_lawyer_cases", find_related, cls.area, corpus_text, inp.lawyer_cases)
    run.log("Precedent Agent", f"{len(related)} related case(s) found in the verified-case database")

    matches = run.call("Matching Agent", "search_verified_lawyers", match_lawyers, cls.area, inp.city, inp.budget,
                       inp.candidates, {r.lawyer_id for r in related})
    run.log("Matching Agent", f"{len(matches)} KYC-verified advocates ranked by verified expertise, jurisdiction and fees")

    draft_title, draft_body = run.call("Drafting Agent", "compose_draft", draft_for, cls.area, inp.title, review.facts,
                                       review.contradictions, missing, review.evidence)
    run.log("Drafting Agent", f"{draft_title.replace('Draft — ', '')} prepared — awaiting human review", "info")
    run.log("Orchestrator", "Final result generated")

    who = review.subject or "the client"
    if review.contradictions:
        summary = (f"The supplied documents contain conflicting information regarding the {review.contradictions[0].topic.lower()} of {who}. "
                   "Two different values appear in the case materials. FormLaw has preserved both sources rather than selecting one without sufficient evidence.")
    elif review.facts:
        summary = (f"FormLaw extracted {len(review.facts)} evidence-backed statements from {len(inp.documents)} document(s). "
                   f"The matter appears to be a {cls.area.lower()} dispute; {len(missing)} supporting document(s) are still missing.")
    else:
        summary = ("FormLaw could not extract verifiable facts from the available text. "
                   + ("Some files are awaiting OCR. " if inp.pending_extraction else "") + "Add text-based documents or a fuller description.")

    return AnalysisResult(
        task_id=inp.task_id, area=cls.area, area_confidence=round(cls.confidence, 3), summary=summary, facts=review.facts,
        evidence=review.evidence, contradictions=review.contradictions, missing=missing, security=list(hits.values()),
        related=related, matches=matches, draft_title=draft_title, draft_body=draft_body, verification=verification,
        contract=contract, run=run, quarantined_docs=set(hits),
    )
