"""
Contract Review Agent — obligations, rights, deadlines, termination, penalties, liability, unusual / ambiguous /
missing / conflicting provisions. Every finding quotes the clause it is based on; absent provisions are reported as
absences, never as facts. Conflicting clauses are left to the Contradiction Agent.
"""
from __future__ import annotations

import re

from ...llm.schemas import ContractOut
from ..base import AgentSpec, StepResult
from ..grounding import sentences, verbatim
from ..runtime.state import Cite, ClaimItem

SPEC = AgentSpec(
    name="Contract Review Agent",
    purpose="Review contracts for obligations, rights, deadlines, risks and missing or conflicting provisions",
    actions=("contract_review.review",),
    tools=frozenset({"llm_structured", "case_search", "list_documents"}),
    inputs="contract passages",
    outputs="contract findings (category, clause quote, risk level) and missing standard provisions",
    failure_modes="no contract in the case → not applicable",
    verification="each finding quotes its clause verbatim; Verification Agent re-checks",
)
CLAUSES: list[tuple[str, str, str, str]] = [
    # category, title, pattern, default risk
    ("unusual", "One-sided discretion", r"\b(sole (and absolute )?discretion|without (any )?(prior )?notice|unilateral\w*|at any time without)\b", "high"),
    ("unusual", "Automatic renewal", r"\b(automatically renew\w*|auto-?renew\w*)\b", "medium"),
    ("unusual", "Non-compete / restraint", r"\b(non-?compet\w+|shall not (engage|compete|solicit))\b", "high"),
    ("ambiguous", "Vague standard", r"\b(reasonable efforts|best efforts|as may be decided|from time to time|as deemed fit|substantially)\b", "medium"),
    ("liability", "Unlimited liability", r"\b(unlimited liability|without limit|all losses)\b", "high"),
    ("penalty", "Penalty / liquidated damages", r"\b(penalt\w+|liquidated damages|late fee|interest at)\b", "medium"),
    ("termination", "Termination", r"\bterminat\w*\b", "medium"),
    ("payment", "Payment terms", r"\b(pay|payment|fee|consideration|invoice)\w*\b.{0,80}\b(within|days|due|rs\.?|inr|₹|\d)", "low"),
    ("liability", "Limitation of liability", r"\b(limitation of liability|liabilit\w+ (shall|will) (not )?exceed|in no event shall)\b", "medium"),
    ("indemnity", "Indemnity", r"\bindemnif\w*\b", "medium"),
    ("confidentiality", "Confidentiality", r"\bconfidential\w*\b", "low"),
    ("dispute_resolution", "Dispute resolution", r"\b(arbitrat\w+|mediat\w+|dispute resolution)\b", "low"),
    ("governing_law", "Governing law / jurisdiction", r"\b(governing law|governed by the laws|exclusive jurisdiction|courts at)\b", "low"),
    ("deadline", "Deadline", r"\b(within \d+\s*(days?|weeks?|months?)|no later than|on or before)\b", "low"),
]
STANDARD = {
    "termination": "Termination rights and notice", "liability": "Limitation of liability", "dispute_resolution": "Dispute resolution",
    "governing_law": "Governing law", "confidentiality": "Confidentiality", "payment": "Payment terms",
}


class ContractReviewAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        docs = ctx.tool("list_documents")
        contract_ids = [d["id"] for d in docs if d["docType"] == "contract"]
        res = ctx.tool("case_search", query="agreement clause shall party terminate payment liability notice discretion damages", k=60,
                       doc_types=["contract"] if contract_ids else None, max_per_document=60, broaden=True)
        hits = [h for h in res.hits if h.document_id in contract_ids] if contract_ids else []
        if not hits:
            return StepResult("skipped", "No contract found among the case documents", {"not_applicable": True})
        ctx.board.add_evidence(hits)
        out = ctx.llm("contract", "contract", ContractOut, request=ctx.state.goal, passages=(pm := ctx.passages(hits)))
        found: set[str] = set()
        n = 0
        if out is not None:
            for f in out.findings:
                h = pm.resolve(f.passage_id)
                if not h or not verbatim(f.quote, h.text):
                    continue
                ctx.board.add_claim(ClaimItem(ctx.board.next_id("c"), f.text, f"contract_{f.category}", SPEC.name,
                                              [Cite(h.chunk_id, f.quote)], meta={"title": f.title, "risk": f.risk_level, "party": f.party}))
                found.add(f.category)
                n += 1
            for mp in out.missing_provisions:
                ctx.board.contract_missing.append({"title": mp.title, "why": mp.why})
        if not n:
            for h in hits:
                for s in sentences(h.text):
                    for cat, title, pat, risk in CLAUSES:
                        if re.search(pat, s, re.I):
                            ctx.board.add_claim(ClaimItem(ctx.board.next_id("c"), f"{title}: the contract provides “{s}”", f"contract_{cat}",
                                                          SPEC.name, [Cite(h.chunk_id, s)], meta={"title": title, "risk": risk}))
                            found.add(cat)
                            n += 1
                            break
            for cat, title in STANDARD.items():
                if cat not in found:
                    ctx.board.contract_missing.append({"title": title, "why": "No clause addressing this was found in the contract text."})
        high = sum(1 for c in ctx.board.claims if c.kind.startswith("contract_") and c.meta.get("risk") == "high")
        return StepResult("ok", f"{n} clause finding(s), {high} high-risk, {len(ctx.board.contract_missing)} standard provision(s) not found",
                          {"findings": n, "high_risk": high}, "llm" if out is not None else "deterministic")
