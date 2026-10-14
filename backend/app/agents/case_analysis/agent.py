"""
Case Analysis Agent — parties, facts, allegations, admissions, disputed facts, dated events, issues.

Model path: structured extraction; every item must cite a passage and quote it verbatim, and any statute/section it
mentions must appear in the cited text — otherwise the item is dropped (never "fixed"). Deterministic path: dated
events and attributed statements extracted directly from sentences. Never invents facts.
"""
from __future__ import annotations

import re

from ...ingestion.profile import placeholders
from ...llm.schemas import ExtractOut
from ...retrieval.case_index import EvidenceHit
from ..base import AgentSpec, StepResult
from ..grounding import doc_label, events_in, sentences, verbatim
from ..runtime.state import Cite, ClaimItem, TimelineItem

SPEC = AgentSpec(
    name="Case Analysis Agent",
    purpose="Extract parties, facts, allegations, admissions, disputed facts, dates and issues from the evidence",
    actions=("case_analysis.extract",),
    tools=frozenset({"llm_structured", "all_chunks"}),
    inputs="evidence on the blackboard; focus topics",
    outputs="claims (with citations), timeline events, parties, issues",
    failure_modes="model unavailable → deterministic extraction; ungrounded model items dropped",
    verification="verbatim quote check + statute-in-source check here; Verification Agent re-checks every claim",
)
_AUTH = re.compile(r"\b(?:section|sec\.|s\.|article|art\.)\s*\d+[a-z]?(?:\(\d+\))?|\b(?:AIR|SCC|SCR|INSC)\b\s*\S*\d", re.I)
_PARTY = [
    (re.compile(r"\baccused(?: person)?(?: namely| named|,)?\s+((?:[A-Z][a-z]+\s){0,3}[A-Z][a-z]+)"), "accused"),
    (re.compile(r"\bcomplainant(?: namely| named|,)?\s+((?:[A-Z][a-z]+\s){0,3}[A-Z][a-z]+)"), "complainant"),
    (re.compile(r"\b((?:[A-Z][a-z]+\s){0,3}[A-Z][a-z]+),?\s+\((?:the )?(accused|complainant|petitioner|respondent|witness)\)"), None),
    (re.compile(r"\b(?:SI|ASI|Inspector|Sub-Inspector|Constable)\s+((?:[A-Z][a-z]+\s){0,2}[A-Z][a-z]+)"), "police officer"),
    (re.compile(r"\bbetween\s+((?:[A-Z][\w.&]*\s){0,5}[A-Z][\w.&]*)\s*(?:\(.*?\))?,?\s+and\s+((?:[A-Z][\w.&]*\s){0,5}[A-Z][\w.&]*)"), "contracting party"),
]
# Identifying details, read exactly as written (deterministic path). Provisions only as the document itself cites them.
_DETAIL = [
    ("case_number", re.compile(r"\b((?:FIR|F\.I\.R\.|Case|Crime|Suit|Petition|Appeal|Complaint|C\.C\.|W\.P\.|Bail Application)\s*"
                               r"(?:No\.?|Number)\s*[:.\-]?\s*[A-Z0-9][\w/.\-]*\d[\w/.\-]*)", re.I)),
    ("court", re.compile(r"\b((?:Court of (?:the )?[A-Z][\w.' ]{2,60}?)(?=[,.;\n]|$)|(?:[A-Z][\w.']+ ){0,5}(?:High|District|Sessions|"
                         r"Magistrate'?s?|Family|Civil|Supreme|Metropolitan|Consumer) Court(?:,? (?:at )?[A-Z][a-z]+)?)")),
    ("police_station", re.compile(r"\bPolice Station\s*[:\-]?\s*([A-Z][\w ]{2,30}?)(?=[,.;\n]|\s+(?:on|in|at|and|under|District)\b)|"
                                  r"\bP\.?S\.?\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)")),
    ("provision", re.compile(r"\b((?:Sections?|u/s\.?|Articles?)\s*\d+[A-Z]?(?:\(\d+\))?(?:\s*(?:,|and|/|&)\s*\d+[A-Z]?(?:\(\d+\))?)*"
                             r"(?:\s*(?:of the|of)?\s*(?:BNSS|BNS|BSA|IPC|CrPC|Cr\.P\.C\.?|NDPS Act|Constitution(?: of India)?|"
                             r"Bharatiya Nyaya Sanhita|Bharatiya Nagarik Suraksha Sanhita|Indian Penal Code|"
                             r"(?:[A-Z]\w+ ){1,5}Act(?:,? \d{4})?))\b)")),
]
_FACT_HINT = re.compile(r"\b(arrest|seiz|recover|stat|admit|confess|alleg|deni|saw|found|signed|agreed|paid|terminat|deliver|injur|stolen|weapon|shall|breach)", re.I)


def _header_like(s: str) -> bool:
    """Document titles and captions ("STATEMENT OF WITNESS — recorded under …") are not statements of fact."""
    letters = [c for c in s[:50] if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.6


def _norm_auth(s: str) -> str:
    s = re.sub(r"\bsec\.|\bs\.", "section", s.lower())
    return re.sub(r"\bart\.", "article", s).replace(" ", "")


def _authorities_ok(text: str, source: str) -> bool:
    """Any statute/section/citation named in an item must appear in the passage it cites (no authority from memory)."""
    src = _norm_auth(source)
    return all(_norm_auth(m.group(0)) in src for m in _AUTH.finditer(text))


class CaseAnalysisAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        board = ctx.board
        if step.params.get("scope") == "all" or len(board.evidence) < 4:
            board.add_evidence(ctx.tool("all_chunks", limit=120))
        hits = board.ranked_evidence(limit=40)
        if not hits:
            return StepResult("insufficient", "No evidence to analyse", {"no_evidence": True})
        focus = step.params.get("focus") or board.focus
        out = ctx.llm("extract", "extract", ExtractOut, request=ctx.state.goal, passages=(pm := ctx.passages(hits[:30])),
                      context={"focus_topics": focus, "intent": ctx.state.intent})
        self._details(ctx, hits)
        if out is not None:
            kept, dropped = self._apply_model(ctx, out, pm)
            if kept:
                return StepResult("ok", f"Extracted {kept} grounded items ({dropped} ungrounded discarded)",
                                  {"dropped": dropped, "events": len(board.timeline)}, engine="llm")
        n = self._deterministic(ctx, hits, focus)
        return StepResult("ok" if n else "insufficient", f"Extracted {n} items directly from document sentences",
                          {"events": len(board.timeline)})

    def _apply_model(self, ctx, out: ExtractOut, pm) -> tuple[int, int]:
        board, kept, dropped = ctx.board, 0, 0

        def ok(item) -> EvidenceHit | None:
            hit = pm.resolve(item.passage_id)
            return hit if hit and verbatim(item.quote, hit.text) else None

        for f in out.facts:
            hit = ok(f)
            if not hit or not _authorities_ok(f.text, hit.text):
                dropped += 1
                continue
            board.add_claim(ClaimItem(board.next_id("c"), f.text, f.kind, SPEC.name, [Cite(hit.chunk_id, f.quote)]))
            kept += 1
        for e in out.events:
            hit = ok(e)
            if not hit or e.date_text.lower() not in hit.text.lower():
                dropped += 1
                continue
            iso = e.date_iso if re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.date_iso or "") else None
            board.timeline.append(TimelineItem(board.next_id("t"), e.date_text, iso, e.description, e.event_type, Cite(hit.chunk_id, e.quote)))
            kept += 1
        for pt in out.parties:
            hit = ok(pt)
            if hit and pt.name.lower() in hit.text.lower():
                board.parties.append({"name": pt.name, "role": pt.role, "chunkId": hit.chunk_id})
                kept += 1
            else:
                dropped += 1
        for d in out.case_details:
            hit = ok(d)
            # A case title ("State v. Arjun Kumar") is not a case type; titles are shown from the case record.
            title_like = d.field == "case_type" and re.search(r"\s(v|vs)\.?\s", d.value, re.I)
            if hit and d.value.strip() and d.value.lower() in d.quote.lower() and not placeholders(d.value) and not title_like:
                self._add_detail(board, d.field, d.value.strip(), hit.chunk_id, d.quote)
                kept += 1
            else:
                dropped += 1
        for i in out.issues:
            hit = ok(i)
            if not hit or not _authorities_ok(i.text, hit.text):
                dropped += 1
                continue
            board.add_claim(ClaimItem(board.next_id("c"), i.text, "issue", SPEC.name, [Cite(hit.chunk_id, i.quote)]))
            kept += 1
        return kept, dropped

    @staticmethod
    def _add_detail(board, field: str, value: str, chunk_id: str, quote: str) -> None:
        if not any(x["field"] == field and x["value"].lower() == value.lower() for x in board.case_details):
            board.case_details.append({"field": field, "value": value, "chunkId": chunk_id, "quote": quote})

    def _details(self, ctx, hits: list[EvidenceHit]) -> None:
        """Case number, court, police station and cited provisions, each read verbatim from a cited sentence."""
        for h in hits:
            t = h.text
            for name, rx in _DETAIL:  # over the whole passage: "FIR No. DEMO-118/2026" must not be split at "No."
                for m in rx.finditer(t):
                    value = next((g for g in m.groups() if g), "").strip(" ,.;")
                    if len(value) < 3 or placeholders(value):
                        continue
                    start = t.rfind(". ", 0, m.start()) + 2 if t.rfind(". ", 0, m.start()) >= 0 else 0
                    end = t.find(".", m.end())
                    self._add_detail(ctx.board, name, value, h.chunk_id, t[start:end + 1 if end >= 0 else len(t)].strip())

    def _deterministic(self, ctx, hits: list[EvidenceHit], focus: list[str]) -> int:
        board, n = ctx.board, 0
        seen_events = {(t.event_type, t.date_iso, t.cite.chunk_id) for t in board.timeline}
        for h in hits:
            for ev in events_in(h.text):
                key = (ev.event_type, ev.date_iso, h.chunk_id)
                if key in seen_events:
                    continue
                seen_events.add(key)
                desc = f"{ev.event_type.replace('_', ' ').capitalize()} — according to {doc_label(h)}"
                board.timeline.append(TimelineItem(board.next_id("t"), ev.date_text, ev.date_iso, desc, ev.event_type, Cite(h.chunk_id, ev.sentence)))
                n += 1
            for rx, role in _PARTY:
                for m in rx.finditer(h.text):
                    names = [g for g in m.groups() if g and g[0].isupper()]
                    r = role or (m.group(2) if m.lastindex and m.lastindex >= 2 else "party")
                    for name in names[:2]:
                        if not any(p["name"] == name.strip() for p in board.parties):
                            board.parties.append({"name": name.strip(), "role": r, "chunkId": h.chunk_id})
            for s in sentences(h.text)[:6]:
                if len(s) < 25 or not _FACT_HINT.search(s) or _header_like(s):
                    continue
                if focus and not any(f.lower().split()[0] in s.lower() for f in focus if f):
                    continue
                kind = "allegation" if re.search(r"\balleg|\bclaim|\baccus", s, re.I) else "admission" if re.search(r"\badmit|\bconfess", s, re.I) else "fact"
                text = f"{doc_label(h)[0].upper()}{doc_label(h)[1:]} states: “{s}”"
                board.add_claim(ClaimItem(board.next_id("c"), text, kind, SPEC.name, [Cite(h.chunk_id, s)]))
                n += 1
        return n
