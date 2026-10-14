"""
Legal Drafting Agent — a lawyer-controlled starting point, never a finished filing.

Inputs are restricted to VERIFIED facts and VERIFIED corpus authorities. The draft keeps FACTS, LEGAL AUTHORITIES,
INFERENCES and RECOMMENDATIONS separate. Unknown details become [PLACEHOLDER: …]. Any statute/citation in the body
that is not backed by a verified fact or authority is removed and reported.
"""
from __future__ import annotations

import re

from ...domain.enums import ClaimStatus as S
from ...llm.schemas import DraftOut
from ..base import AgentSpec, StepResult
from ..grounding import doc_label
from ..runtime.state import DraftDoc

SPEC = AgentSpec(
    name="Drafting Agent",
    purpose="Prepare drafts from verified facts and verified authorities for the lawyer to edit",
    actions=("drafting.compose",),
    tools=frozenset({"llm_structured"}),
    inputs="verified claims, verified authorities, contradictions, missing information, draft kind",
    outputs="draft with separated facts / authorities / inferences / recommendations and editable body",
    failure_modes="no verified facts → draft limited to structure + placeholders",
    verification="facts and authorities referenced by id must be verified; unbacked citations stripped from the body",
)
KINDS = {"legal_notice": "Legal notice", "case_summary": "Case summary", "research_memo": "Research memo",
         "argument_outline": "Argument outline", "client_update": "Client update", "chronology": "Chronology",
         "response_draft": "Response draft", "contract_clause": "Contract clause", "briefing_note": "Briefing note for senior counsel",
         "cross_examination_questions": "Questions for cross-examination"}
_AUTH = re.compile(r"\b(?:section|sec\.|article)\s+\d+[A-Z]?(?:\(\d+\))?(?:\s+(?:of the\s+)?[A-Z][\w ,]{2,40}?(?:Act|Code|Sanhita|BNS|BNSS|IPC|CrPC))?|\b\d{4}\s*INSC\s*\d+|\(\d{4}\)\s*\d+\s*SCC\s*\d+|AIR\s*\d{4}\s*SC\s*\d+", re.I)


class DraftingAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        board = ctx.board
        kind = step.params.get("kind") or ctx.state.draft_kind or "case_summary"
        kind = kind if kind in KINDS else "case_summary"
        facts = [c for c in board.claims if c.status in (S.SUPPORTED, S.PARTIALLY_SUPPORTED) and c.kind not in ("answer", "summary")]
        auths = [a for a in board.authorities if a.status == S.SUPPORTED]
        allowed_text = " ".join([c.text for c in facts] + [f"{a.title} {a.citation or ''} {a.quote}" for a in auths]).lower()
        out = ctx.llm("draft", "draft", DraftOut, request=ctx.state.goal, context={
            "draft_kind": kind,
            "verified_facts": [{"id": c.id, "text": c.text} for c in facts[:40]],
            "verified_authorities": [{"id": a.id, "title": a.title, "citation": a.citation, "court": a.court, "passage": a.quote[:500]} for a in auths],
            "contradictions": [{"topic": x.topic, "a": x.a.statement, "b": x.b.statement} for x in board.contradictions],
            "missing": [m.title for m in board.missing],
        })
        fact_ids, auth_ids = {c.id for c in facts}, {a.id for a in auths}
        if out is not None:
            body, removed = self._strip_unbacked(out.body, allowed_text)
            draft = DraftDoc(kind, out.title, [i.model_dump() for i in out.facts if set(i.fact_ids) <= fact_ids and i.fact_ids],
                             [i.model_dump() for i in out.authorities if set(i.authority_ids) <= auth_ids and i.authority_ids],
                             [i.model_dump() for i in out.inferences if set(i.fact_ids) <= fact_ids],
                             list(out.recommendations) + ([f"Removed {removed} unverified legal reference(s) from the draft body."] if removed else []),
                             body)
            engine = "llm"
        else:
            draft = self._template(ctx, kind, facts, auths)
            engine = "deterministic"
        board.draft = draft
        return StepResult("ok", f"{KINDS[kind]} drafted from {len(facts)} verified fact(s) and {len(auths)} verified authorit{'y' if len(auths) == 1 else 'ies'} — awaiting lawyer review",
                          {"kind": kind}, engine)

    @staticmethod
    def _strip_unbacked(body: str, allowed: str) -> tuple[str, int]:
        removed = 0

        def repl(m: re.Match) -> str:
            nonlocal removed
            token = m.group(0)
            core = re.match(r"(section|sec\.|article)\s+\d+[A-Z]?(\(\d+\))?", token, re.I)
            probe = (core.group(0) if core else token).lower()
            if probe in allowed:
                return token
            removed += 1
            return "[UNVERIFIED REFERENCE REMOVED]"
        return _AUTH.sub(repl, body), removed

    def _template(self, ctx, kind, facts, auths) -> DraftDoc:
        board = ctx.board
        fact_lines = [{"text": c.text, "fact_ids": [c.id]} for c in facts[:25]]
        auth_lines = [{"text": f"{a.title} ({a.citation or a.decision_date or 'citation not recorded'}), {a.court or ''}: “{a.quote[:300]}”",
                       "authority_ids": [a.id]} for a in auths]
        recs = [f"Obtain: {m.title}." for m in board.missing[:6]]
        recs += [f"Address the conflict on {x.topic.lower()} ({x.a.value} vs {x.b.value}) before relying on either date." for x in board.contradictions]
        recs.append("Review every statement against its source before use; this draft was assembled from verified extracts only.")
        lines = [f"{KINDS[kind].upper()}", f"Matter: {ctx.state.case_title}", "", "1. FACTS (verified against the case documents)"]
        lines += [f"   • {f['text']}" for f in fact_lines] or ["   [PLACEHOLDER: no verified facts yet — upload or review documents]"]
        if board.timeline:
            lines += ["", "2. CHRONOLOGY"]
            for t in sorted(board.timeline, key=lambda t: t.date_iso or "9999")[:30]:
                ev = board.evidence.get(t.cite.chunk_id)
                lines.append(f"   • {t.date_text} — {t.description}" + (f" [{ev.document_name} p.{ev.page}]" if ev else "") +
                             (" (CONFLICTED)" if t.status == "conflicted" else ""))
        if board.contradictions:
            lines += ["", "3. CONTRADICTIONS IN THE RECORD"]
            lines += [f"   • {x.topic}: {x.a.statement}; {x.b.statement}." for x in board.contradictions]
        if kind == "cross_examination_questions":
            lines += ["", "4. QUESTIONS (derived from the record)"]
            for x in board.contradictions:
                ea, eb = board.evidence.get(x.a.cite.chunk_id), board.evidence.get(x.b.cite.chunk_id)
                lines.append(f"   • {doc_label(ea).capitalize() if ea else 'One record'} gives {x.a.value}; {doc_label(eb) if eb else 'another'} gives {x.b.value}. Which is correct, and who recorded each?")
            for m in board.missing[:5]:
                lines.append(f"   • Was a {m.title.lower()} prepared? If so, why has it not been produced?")
        lines += ["", "LEGAL AUTHORITIES (verified corpus only)"]
        lines += [f"   • {a['text']}" for a in auth_lines] or ["   [PLACEHOLDER: no verified authority retrieved — research before citing law]"]
        lines += ["", "RECOMMENDATIONS"] + [f"   • {r}" for r in recs]
        lines += ["", "[PLACEHOLDER: counsel name, enrolment number, date]"]
        return DraftDoc(kind, f"{KINDS[kind]} — {ctx.state.case_title}", fact_lines, auth_lines, [], recs, "\n".join(lines))
