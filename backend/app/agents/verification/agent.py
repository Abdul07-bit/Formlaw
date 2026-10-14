"""
Verification Agent — the verification gate. Every claim on the blackboard leaves this agent with a status:

  SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED · CONTRADICTED · UNVERIFIED

Order of checks (cheapest, most objective first):
  1. citations exist and point into this case; quotes are verbatim in the cited passage
  2. deterministic groundedness: dates / numbers / sections in the claim must appear in the evidence; wording overlap
  3. conflict awareness: a claim asserting one side of a known contradiction as fact is CONTRADICTED
  4. optional model judge (different prompt, different role) — may only DOWNGRADE a status, never upgrade
Authorities are verified by re-reading the corpus row and comparing the content hash.
"""
from __future__ import annotations

import re

from ...domain.enums import ClaimStatus as S
from ...llm.schemas import JudgeOut
from ..base import AgentSpec, StepResult
from ...ingestion.text import norm_for_match
from ..grounding import verbatim

SPEC = AgentSpec(
    name="Verification Agent",
    purpose="Verify every important claim against the evidence it cites",
    actions=("verification.verify",),
    tools=frozenset({"verify_claim", "get_chunks", "corpus_get_chunk", "llm_structured"}),
    inputs="claims and authorities on the blackboard",
    outputs="status, confidence and reason for each claim",
    failure_modes="judge unavailable → deterministic verdicts only",
    verification="deterministic first; the model that wrote a claim never grades it; the judge can only downgrade",
)
ATTRIBUTED = re.compile(r"\b(states?|stated|records?|recorded|according to|gives?|says?|provides?|mentions?|alleges?|claims?|reports?)\b", re.I)
_RANK = {S.SUPPORTED: 4, S.PARTIALLY_SUPPORTED: 3, S.UNVERIFIED: 2, S.UNSUPPORTED: 1, S.CONTRADICTED: 0}


class VerificationAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        board = ctx.board
        # Authorities: the passage must still exist in the corpus with the same hash.
        for a in board.authorities:
            if a.status == S.UNVERIFIED:
                row = ctx.tool("corpus_get_chunk", chunk_id=a.legal_chunk_id)
                a.status = S.SUPPORTED if row and row[1] == a.content_hash and verbatim(a.quote, row[0]) else S.UNSUPPORTED
        pending = [c for c in board.claims if c.status == S.UNVERIFIED or step.params.get("recheck")]
        missing_ids = {ci.chunk_id for c in pending for ci in c.citations if ci.chunk_id not in board.evidence}
        if missing_ids:
            board.add_evidence(ctx.tool("get_chunks", chunk_ids=sorted(missing_ids)))
        conflicts = [(x, {x.a.value.lower(), x.b.value.lower()}) for x in board.contradictions]
        for c in pending:
            self._check(ctx, c, conflicts)
        judged = self._judge(ctx, [c for c in pending if c.verified and c.agent != "Case Analysis Agent" or c.kind == "answer"])
        counts = {s.value: sum(c.status == s for c in board.claims) for s in S}
        bad = counts["UNSUPPORTED"] + counts["CONTRADICTED"] + counts["UNVERIFIED"]
        current = set(board.answer.claim_ids) if board.answer else set()
        answer_bad = [c.id for c in board.claims if c.id in current and not c.verified]
        return StepResult("ok", f"{len(pending)} claim(s) checked — {counts['SUPPORTED']} supported, {counts['PARTIALLY_SUPPORTED']} partial, "
                                f"{bad} not supported" + (f"; judge reviewed {judged}" if judged else ""),
                          {"counts": counts, "answer_unsupported": answer_bad}, "llm" if judged else "deterministic")

    def _check(self, ctx, c, conflicts) -> None:
        board = ctx.board
        derived = c.meta.get("derived")
        if derived:  # a summary FormLaw composed from other claims inherits their verification
            parts = [x for x in (board.claim(i) for i in derived) if x]
            ok = [x for x in parts if x.verified]
            c.status = S.SUPPORTED if parts and len(ok) == len(parts) else S.PARTIALLY_SUPPORTED if ok else S.UNSUPPORTED
            c.confidence = "high" if c.status == S.SUPPORTED else "medium" if ok else "low"
            c.reason = "Composed from findings that each passed verification" if c.status == S.SUPPORTED else \
                "Some findings it summarises did not pass verification"
            return
        if c.authority_ids and not c.citations:
            auths = [a for a in board.authorities if a.id in c.authority_ids]
            ok = auths and all(a.status == S.SUPPORTED for a in auths)
            c.status, c.confidence = (S.SUPPORTED, "high") if ok else (S.UNVERIFIED, "low")
            c.reason = "Cites verified corpus passages" if ok else "Cited authority is not verified in the corpus"
            return
        if not c.citations:
            c.status, c.confidence, c.reason = S.UNVERIFIED, "low", "No evidence was cited for this statement"
            return
        texts, quotes_ok = [], True
        for ci in c.citations:
            hit = board.evidence.get(ci.chunk_id)
            if hit is None:
                c.status, c.confidence, c.reason = S.UNSUPPORTED, "low", "Cites a passage that is not in this case"
                return
            texts.append(hit.text)
            quotes_ok &= verbatim(ci.quote, hit.text)
        if not quotes_ok:
            c.status, c.confidence, c.reason = S.UNSUPPORTED, "low", "The quoted text does not appear in the cited passage"
            return
        # A statement that draws on several passages is checked against them together.
        v = ctx.tool("verify_claim", claim=c.text, evidence=[" ".join(texts)] if len(texts) > 1 else texts)
        status, reason = v.status, v.reason
        if status != S.CONTRADICTED and any(len(ci.quote) >= 12 and norm_for_match(ci.quote) in norm_for_match(c.text) for ci in c.citations):
            status, reason = S.SUPPORTED, "Statement quotes the evidence verbatim"
        low = c.text.lower()
        for x, values in conflicts:
            if any(v_ in low for v_ in values) and not ATTRIBUTED.search(c.text):
                status, reason = S.CONTRADICTED, f"Another source gives a different value ({x.a.value} vs {x.b.value})"
                break
        c.status, c.reason = status, reason
        c.confidence = "high" if status == S.SUPPORTED and v.confidence >= 0.8 else "medium" if status in (S.SUPPORTED, S.PARTIALLY_SUPPORTED) else "low"
        if status == S.SUPPORTED and reason.startswith("Statement quotes"):
            c.confidence = "high"

    def _judge(self, ctx, claims) -> int:
        if not claims or not ctx.llm_available:
            return 0
        claims = claims[:30]
        # Every cited passage (up to three) goes to the judge: a statement comparing two documents is judged against both.
        hits = [ctx.board.evidence[ci.chunk_id] for c in claims for ci in c.citations[:3] if ci.chunk_id in ctx.board.evidence]
        pm = ctx.passages(list({h.chunk_id: h for h in hits}.values()))
        pid_of = {h.chunk_id: pid for pid, h in pm.by_pid.items()}
        payload = [{"claim_id": c.id, "claim": c.text,
                    "evidence_passages": [p for ci in c.citations[:3] if (p := pid_of.get(ci.chunk_id))]} for c in claims]
        out = ctx.llm("judge", "judge", JudgeOut, request="Verify each claim against its evidence passages, read together.",
                      passages=pm, context={"claims": payload})
        if out is None:
            return 0
        by_id = {c.id: c for c in claims}
        for v in out.verdicts:
            c = by_id.get(v.claim_id)
            if c and _RANK[S(v.verdict)] < _RANK[S(c.status)]:  # downgrade only
                c.status, c.reason = v.verdict, f"Independent check: {v.reason}"[:400]
                c.confidence = "medium" if v.verdict == S.PARTIALLY_SUPPORTED else "low"
        return len(out.verdicts)
