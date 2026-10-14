"""
Answer composition (Orchestrator). The answer is a set of claims, each citing evidence, plus a summary that is
itself a claim — so the verification gate checks the summary too.

Model path: the model phrases sentences from passages + FormLaw's verified findings (trusted context); citations and
quotes are validated in code. Deterministic path, and strict mode after a failed verification: the answer is built
only from items that are already verified (attributed quotes, contradictions, missing records, authorities).
"""
from __future__ import annotations

from ...domain.enums import ClaimStatus as S
from ...domain.enums import Intent
from ...ingestion.profile import template_fields
from ...llm.schemas import ComposeOut
from ...security.injection import scan_output
from ..base import AgentSpec, StepResult
from ..grounding import best_sentence, doc_label, verbatim
from ..runtime.state import Answer, Cite, ClaimItem, MissingItem

SPEC = AgentSpec(
    name="Orchestrator",
    purpose="Understand the request, plan, delegate, observe, adapt, and compose the final evidence-backed answer",
    actions=("answer.compose",),
    tools=frozenset({"llm_structured", "case_search", "list_documents"}),
    inputs="blackboard (evidence, verified findings)",
    outputs="answer summary + answer claims with citations",
    failure_modes="unverifiable sentences → strict recomposition from verified items only",
    verification="answer and summary pass the same verification gate as every other claim",
)


INCOMPLETE = ("CASE ANALYSIS INCOMPLETE — The supplied document contains template fields or insufficient case-specific "
              "information. Actual parties, facts, and supporting evidence cannot be reliably established from this material alone.")
_KEY_FIELD = ("plaintiff", "complainant", "defendant", "respondent", "accused", "case number", "court", "filing date", "date",
              "background", "core dispute", "witness")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


class Composer:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        board = ctx.board
        strict = bool(step.params.get("strict"))
        if self._template_only(ctx):
            return StepResult("ok", "Case analysis incomplete — the case documents are unfilled templates", {"template": True})
        # Retire earlier answer claims: failed ones stay on the board (reported as unverified), never in the answer.
        hits = board.ranked_evidence(limit=14)
        if not strict and hits:
            out = ctx.llm("compose", "compose", ComposeOut, request=ctx.state.goal, passages=(pm := ctx.passages(hits)),
                          context=self._trusted_context(ctx))
            if out is not None and self._apply_model(ctx, out, pm):
                return StepResult("ok", f"Answer composed with {len(board.answer.claim_ids)} cited statement(s)", engine="llm")
        self._deterministic(ctx, strict)
        mode = "from verified findings only" if strict else "from document text"
        return StepResult("ok", f"Answer composed {mode} ({len(board.answer.claim_ids)} cited statement(s))",
                          {"strict": strict})

    # ------------------------------------------------------------ templates
    def _template_only(self, ctx) -> bool:
        """
        Blank forms are never evidence. When the case holds nothing else, report that the analysis is incomplete and
        exactly which fields are missing — never fill the gaps or quote placeholders as facts.
        """
        board = ctx.board
        if not board.templates or board.ranked_evidence(limit=1) or ctx.state.intent == Intent.LEGAL_RESEARCH:
            return False
        docs = ctx.tool("list_documents")
        if any(d["status"] == "indexed" and d["docType"] != "template" for d in docs):
            return False  # real documents exist; the question was simply not answered by them
        forms = [d for d in docs if d["docType"] == "template"]
        fields: dict[str, str] = {}
        for d in forms:
            for f in d.get("templateFields") or []:
                fields.setdefault(f, d["name"])
        if not fields:  # placeholders inside otherwise unclassified documents
            for h in board.templates.values():
                for f in template_fields(h.text):
                    fields.setdefault(f, h.document_name)
        names = sorted({h.document_name for h in board.templates.values()} | {d["name"] for d in forms})
        listed = list(fields)
        limitations = [
            f"{', '.join(f'“{n}”' for n in names)} {'is an unfilled template' if len(names) == 1 else 'are unfilled templates'}: "
            f"{len(listed)} field(s) are blank" + (f", including {'; '.join(listed[:10])}." if listed else "."),
            "Template placeholders and form instructions were not treated as case facts; no names, dates, arguments or "
            "evidence were inferred to fill them.",
            "Upload the completed case documents (for example the filled case form, FIR or complaint, contracts, "
            "statements, notices and court orders) to analyse the case.",
        ]
        for f, doc in list(fields.items())[:15]:
            board.missing.append(MissingItem(board.next_id("m"), f, f"Left blank in “{doc}”; needed to establish the case.",
                                             "template_field", "high" if any(k in f.lower() for k in _KEY_FIELD) else "medium",
                                             key=f"template:{f.lower()}"))
        summ = board.add_claim(ClaimItem(board.next_id("c"), INCOMPLETE, "summary", SPEC.name, []))
        summ.status, summ.confidence, summ.reason = S.SUPPORTED, "high", "Describes the reviewed material, not a fact about the case"
        board.answer = Answer(INCOMPLETE, [summ.id], limitations, assessment="not_assessed")
        return True

    # ---------------------------------------------------------------- model
    def _trusted_context(self, ctx) -> dict:
        b = ctx.board
        return {
            "intent": ctx.state.intent,
            "verified_contradictions": [{"topic": x.topic, "a": x.a.statement, "b": x.b.statement,
                                         "provenance": x.provenance.get("assessment", "")} for x in b.contradictions],
            "missing_records": [m.title for m in b.missing],
            "timeline": [{"date": t.date_text, "event": t.description, "status": t.status} for t in b.timeline[:30]],
            "authorities": [{"title": a.title, "citation": a.citation, "court": a.court} for a in b.authorities if a.status == S.SUPPORTED],
            "contract_findings": [c.meta.get("title", c.kind) for c in b.claims if c.kind.startswith("contract_")][:20],
        }

    def _apply_model(self, ctx, out: ComposeOut, pm) -> bool:
        board = ctx.board
        if not out.sentences:
            return self._apply_not_established(ctx, out)
        ids, cites_all = [], []
        for s in out.sentences:
            if scan_output(s.text):
                continue  # instructions, links or beacons in model output are never shown
            hits = [h for pid in s.passage_ids if (h := pm.resolve(pid))]
            cites = []
            if hits:
                q = s.quote if s.quote and verbatim(s.quote, hits[0].text) else best_sentence(hits[0].text, s.text)
                cites = [Cite(hits[0].chunk_id, q)] + [Cite(h.chunk_id, best_sentence(h.text, s.text)) for h in hits[1:3]]
            c = board.add_claim(ClaimItem(board.next_id("c"), s.text, "answer", SPEC.name, cites))
            ids.append(c.id)
            cites_all += cites
        if not ids or scan_output(out.summary):
            return False
        summ = board.add_claim(ClaimItem(board.next_id("c"), out.summary, "summary", SPEC.name, cites_all[:6]))
        board.answer = Answer(out.summary, [summ.id] + ids, list(out.limitations))
        return True

    def _apply_not_established(self, ctx, out: ComposeOut) -> bool:
        """
        The model read the passages and found no answer (the prompt asks for empty `sentences` then). That is a valid
        answer — better than quoting unrelated passages. The summary is FormLaw's fixed wording, not model text, so
        nothing unverifiable is asserted about the case; the model's limitations explain what is missing.
        """
        board = ctx.board
        if ctx.state.intent != Intent.EVIDENCE_QA or board.contradictions:
            return False  # reviews, timelines, conflicts etc. always have findings to report: use the deterministic path
        limitations = [x for x in out.limitations if x.strip() and not scan_output(x)]
        summary = "The case documents do not establish this."
        summ = board.add_claim(ClaimItem(board.next_id("c"), summary, "summary", SPEC.name, []))
        summ.status, summ.confidence, summ.reason = S.SUPPORTED, "high", "Describes FormLaw's search result, not a fact about the case"
        board.answer = Answer(summary, [summ.id], limitations or [f"No passage in the {len({e.document_id for e in board.evidence.values()})} "
                                                                   "case document(s) answers this question."])
        return True

    # -------------------------------------------------------- deterministic
    def _deterministic(self, ctx, strict: bool) -> None:
        board, intent, goal = ctx.board, ctx.state.intent, ctx.state.goal
        claims: list[ClaimItem] = []
        limitations: list[str] = []

        seen_quotes: set[tuple[str, str]] = set()

        def add(text: str, cites: list[Cite], kind: str = "answer") -> None:
            key = (cites[0].chunk_id, cites[0].quote) if cites else ("", text)
            # One statement per quoted passage — also when two findings quote overlapping parts of the same sentence.
            if key in seen_quotes or any(ch == key[0] and (key[1] in q or q in key[1]) for ch, q in seen_quotes if cites):
                return
            seen_quotes.add(key)
            claims.append(board.add_claim(ClaimItem(board.next_id("c"), text, kind, SPEC.name, cites)))

        verified_facts = [c for c in board.claims if c.status in (S.SUPPORTED, S.PARTIALLY_SUPPORTED) and c.kind not in ("answer", "summary")]
        lead_conflict = self._conflict_leads(ctx)

        def add_conflicts() -> None:
            for x in board.contradictions:
                ea, eb = board.evidence.get(x.a.cite.chunk_id), board.evidence.get(x.b.cite.chunk_id)
                if ea and eb:
                    add(f"{_cap(doc_label(ea))} ({ea.document_name}, p.{ea.page}) records “{x.a.cite.quote}”", [x.a.cite])
                    add(f"{_cap(doc_label(eb))} ({eb.document_name}, p.{eb.page}) records “{x.b.cite.quote}”", [x.b.cite])

        if lead_conflict:
            add_conflicts()
        if intent == Intent.CONTRACT_REVIEW:
            for c in [c for c in verified_facts if c.kind.startswith("contract_")][:8] or [c for c in board.claims if c.kind.startswith("contract_")][:8]:
                add(c.text, list(c.citations))
        elif intent in (Intent.TIMELINE,):
            for t in sorted(board.timeline, key=lambda t: t.date_iso or "9999")[:12]:
                ev = board.evidence.get(t.cite.chunk_id)
                if ev:
                    add(f"{t.date_text}: {_cap(doc_label(ev))} records “{t.cite.quote}”", [t.cite])
        elif intent in (Intent.LEGAL_RESEARCH,):
            pass  # authorities are presented as their own section
        elif intent == Intent.EVIDENCE_QA or not board.contradictions:
            pool = verified_facts if strict else []
            if not pool:
                for h in board.ranked_evidence(limit=3):
                    s = best_sentence(h.text, goal)
                    add(f"{_cap(doc_label(h))} ({h.document_name}, p.{h.page}) states “{s}”", [Cite(h.chunk_id, s)])
            else:
                for c in pool[:5]:
                    add(c.text, list(c.citations))
        if not lead_conflict:
            add_conflicts()

        summary = self._summary(ctx, claims)
        if not board.evidence:
            limitations.append("No case documents were available to answer from.")
        if intent == Intent.LEGAL_RESEARCH and not [a for a in board.authorities if a.status != S.UNSUPPORTED]:
            limitations.append("FormLaw's verified corpus currently holds Supreme Court judgments only; no relevant passage was found. No authority has been generated.")
        cites = [ci for c in claims for ci in c.citations][:6]
        summ = board.add_claim(ClaimItem(board.next_id("c"), summary, "summary", SPEC.name, cites,
                                         meta={"derived": [c.id for c in claims]} if claims else {}))
        if not claims:  # nothing to verify against: a statement about the search result, not a fact about the case
            summ.status, summ.confidence, summ.reason = S.SUPPORTED, "high", "Describes FormLaw's search result, not a fact about the case"
        board.answer = Answer(summary, [summ.id] + [c.id for c in claims], limitations, strict)

    @staticmethod
    def _conflict_leads(ctx) -> bool:
        """A conflict leads the answer unless the lawyer asked a specific question about something else."""
        b = ctx.board
        if not b.contradictions:
            return False
        if ctx.state.intent != Intent.EVIDENCE_QA:
            return True
        q = ctx.state.goal.lower()
        return any(w in q for x in b.contradictions for w in x.topic.lower().replace("date of ", "").split() if len(w) > 3) or             any(w in q for w in ("conflict", "contradict", "inconsisten", "differ"))

    def _summary(self, ctx, claims) -> str:
        board, intent = ctx.board, ctx.state.intent
        n_docs = len({e.document_id for e in board.evidence.values()})
        if not board.evidence:
            return "Insufficient evidence: there are no indexed documents in this case to answer from."
        parts = []
        if board.contradictions and not self._conflict_leads(ctx):
            first = next((c for c in claims if c.citations), None)
            if first:
                parts.append(f"Most directly, {first.text[0].lower()}{first.text[1:]}.")
            x = board.contradictions[0]
            parts.append(f"Separately, the documents conflict on {x.topic.lower()} ({x.a.value} vs {x.b.value}); see the conflict below.")
            return " ".join(parts)
        if board.contradictions:
            x = board.contradictions[0]
            parts.append(f"The documents conflict on {x.topic.lower()}: one source gives {x.a.value}, another gives {x.b.value}. "
                         "FormLaw has not chosen between them.")
            sides = x.provenance.get("sides", {})
            if sides:
                parts.append(" ".join(f"{s['document']} is {s['role']}." for s in sides.values()))
                parts.append(x.provenance.get("assessment", "").replace(" FormLaw does not choose between them — lawyer review required.", "")
                             + " Lawyer review is required.")
            if len(board.contradictions) > 1:
                parts.append(f"{len(board.contradictions) - 1} further conflict(s) were found.")
        if intent == Intent.TIMELINE:
            conflicted = sum(t.status == "conflicted" for t in board.timeline)
            parts.append(f"{len(board.timeline)} dated event(s) found across {n_docs} document(s)" + (f"; {conflicted} conflicted." if conflicted else "."))
        if intent in (Intent.MISSING_INFO, Intent.CASE_REVIEW, Intent.DRAFT) and board.missing:
            parts.append(f"{len(board.missing)} record(s) appear to be missing, including {board.missing[0].title.lower()}.")
        if intent == Intent.CONTRACT_REVIEW:
            high = sum(1 for c in board.claims if c.kind.startswith("contract_") and c.meta.get("risk") == "high")
            parts.append(f"{sum(c.kind.startswith('contract_') for c in board.claims)} clause finding(s), {high} high-risk; "
                         f"{len(board.contract_missing)} standard provision(s) not found.")
        if intent == Intent.LEGAL_RESEARCH:
            n = sum(a.status != S.UNSUPPORTED for a in board.authorities)
            parts.append(f"{n} passage(s) from verified Supreme Court judgments address this issue." if n else
                         "No passage in FormLaw's verified legal corpus addresses this issue.")
        if intent == Intent.DRAFT and board.draft:
            parts.append(f"A draft ({board.draft.title}) is ready for your review.")
        if intent in (Intent.CASE_REVIEW, Intent.SUMMARY):
            facts = sum(1 for c in board.claims if c.kind in ("fact", "allegation", "admission", "disputed", "procedural"))
            parts.insert(0, f"Reviewed {n_docs} document(s): {facts} statement(s) and {len(board.timeline)} dated event(s) extracted.")
        if not parts:
            parts.append(f"The most relevant passages are quoted below from {n_docs} document(s). Read them against the question; "
                         "FormLaw has not inferred anything beyond their text." if claims else "The case documents do not establish this.")
        return " ".join(parts)
