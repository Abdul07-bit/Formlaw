"""
Contradiction Agent.

detect   different dates for a once-only event across sources, conflicting clause values (notice periods, amounts),
         and validated model-proposed conflicts (both sides quoted verbatim, values differ, values appear in quotes)
resolve  provenance assessment of each side + targeted search for an independent record that corroborates either
         value. It reports; it never selects a winner. Unresolved conflicts are flagged for the lawyer.
"""
from __future__ import annotations

import re
from collections import defaultdict

from ...llm.schemas import ContradictionsOut
from ..base import AgentSpec, StepResult
from ..grounding import EVENT_LABEL, SINGLE_OCCURRENCE, doc_label, events_in, verbatim
from ..runtime.state import Cite, ContradictionItem, MissingItem, Side

SPEC = AgentSpec(
    name="Contradiction Agent",
    purpose="Find conflicting dates, statements and clauses; assess the provenance of each side",
    actions=("contradiction.detect", "contradiction.resolve"),
    tools=frozenset({"llm_structured", "case_search", "list_documents"}),
    inputs="timeline and evidence on the blackboard; optional topic",
    outputs="contradictions (statement A/B, sources, nature, confidence, provenance)",
    failure_modes="none found → reports none; unresolved → lawyer review",
    verification="both sides quoted verbatim from different passages; conflicting values present in the quotes",
)
SOURCE_ROLE = {
    "arrest_memo": "the statutory arrest record, prepared at the time of arrest (primary record)",
    "remand_report": "an official report placed before the court by the investigating officer",
    "fir": "the information as first recorded by police, which may predate later events",
    "charge_sheet": "an investigation summary prepared after the events",
    "witness_statement": "a witness account recorded during investigation",
    "seizure_memo": "a contemporaneous seizure record",
    "medical_report": "a medical record prepared by a doctor",
    "affidavit": "a sworn statement by a party",
    "complaint": "the complainant's allegations",
    "contract": "the executed agreement between the parties",
    "correspondence": "correspondence between the parties",
}
NOTICE = re.compile(r"\b(\d{1,3})\s*(?:\(\w+\)\s*)?(days?|months?)'?\s*(?:prior\s+)?(?:written\s+)?notice\b|\bnotice\s+(?:period\s+)?of\s+(\d{1,3})\s*(days?|months?)\b", re.I)


def _norm_val(v: str) -> str:
    return re.sub(r"[^a-z0-9]", "", v.lower())


class ContradictionAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        if step.action == "contradiction.resolve":
            return self._resolve(ctx, step.params["contradiction_id"])
        return self._detect(ctx, step.params.get("topic") or "")

    # ------------------------------------------------------------------ detect
    def _detect(self, ctx, topic: str) -> StepResult:
        board = ctx.board
        before = len(board.contradictions)
        self._date_conflicts(ctx)
        self._clause_conflicts(ctx)
        engine = "deterministic"
        hits = board.ranked_evidence(limit=30)
        if len(hits) >= 2:
            out = ctx.llm("contradiction", "contradiction", ContradictionsOut, request=ctx.state.goal,
                          passages=(pm := ctx.passages(hits)), context={"topic": topic})
            if out is not None:
                engine = "llm"
                for c in out.contradictions:
                    ha, hb = pm.resolve(c.a.passage_id), pm.resolve(c.b.passage_id)
                    if not ha or not hb or ha.chunk_id == hb.chunk_id:
                        continue
                    if not (verbatim(c.a.quote, ha.text) and verbatim(c.b.quote, hb.text)):
                        continue
                    if _norm_val(c.a.value) == _norm_val(c.b.value) or c.a.value.lower() not in c.a.quote.lower() or c.b.value.lower() not in c.b.quote.lower():
                        continue
                    self._add(ctx, c.topic, c.nature, Side(Cite(ha.chunk_id, c.a.quote), c.a.value, c.a.quote),
                              Side(Cite(hb.chunk_id, c.b.quote), c.b.value, c.b.quote), c.explanation, "medium", None)
        found = board.contradictions[before:]
        if topic:
            t = topic.lower()
            found.sort(key=lambda c: t.split()[0] not in c.topic.lower())
        if not found:
            return StepResult("ok", "No conflicting statements found in the retrieved evidence", {"contradictions": []}, engine)
        return StepResult("ok", f"{len(found)} conflict(s): " + "; ".join(f"{c.topic} ({c.a.value} vs {c.b.value})" for c in found[:3]),
                          {"contradictions": [c.id for c in found]}, engine)

    def _date_conflicts(self, ctx) -> None:
        board = ctx.board
        by_type: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for h in board.ranked_evidence(limit=60):
            for ev in events_in(h.text):
                if ev.event_type in SINGLE_OCCURRENCE and ev.date_iso:
                    by_type[ev.event_type][ev.date_iso].append((h, ev))
        for t in board.timeline:  # model-extracted events
            hit = board.evidence.get(t.cite.chunk_id)
            if hit and t.event_type in SINGLE_OCCURRENCE and t.date_iso and not hit.flagged:
                if not any(x[0].chunk_id == hit.chunk_id for x in by_type[t.event_type][t.date_iso]):
                    by_type[t.event_type][t.date_iso].append((hit, None))
        for etype, values in by_type.items():
            if len(values) < 2:
                continue
            # The two best-attested values, preferring sources in different documents.
            ranked = sorted(values.items(), key=lambda kv: -len({h.document_id for h, _ in kv[1]}))
            (va, la), (vb, lb) = ranked[0], ranked[1]
            ha, ea = la[0]
            hb, eb = next(((h, e) for h, e in lb if h.document_id != ha.document_id), lb[0])
            qa = ea.sentence if ea else next(s.cite.quote for s in board.timeline if s.cite.chunk_id == ha.chunk_id)
            qb = eb.sentence if eb else next(s.cite.quote for s in board.timeline if s.cite.chunk_id == hb.chunk_id)
            da = ea.date_text if ea else va
            db_ = eb.date_text if eb else vb
            self._add(ctx, EVENT_LABEL.get(etype, etype.replace("_", " ").capitalize()), "date",
                      Side(Cite(ha.chunk_id, qa), da, f"{doc_label(ha).capitalize()} gives {da}"),
                      Side(Cite(hb.chunk_id, qb), db_, f"{doc_label(hb).capitalize()} gives {db_}"),
                      f"Two sources give different dates for the same {etype.replace('_', ' ')}.", "high", etype)
            for item in board.timeline:
                if item.event_type == etype and item.date_iso in (va, vb):
                    item.status = "conflicted"

    def _clause_conflicts(self, ctx) -> None:
        vals: dict[str, list] = defaultdict(list)
        for h in ctx.board.ranked_evidence(limit=60):
            for m in NOTICE.finditer(h.text):
                n, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
                vals[f"{n} {unit.rstrip('s')}"].append((h, m.group(0)))
        if len(vals) >= 2:
            (va, la), (vb, lb) = list(vals.items())[:2]
            (ha, qa), (hb, qb) = la[0], lb[0]
            sent_a = next((s for s in re.split(r"(?<=[.;])\s+", ha.text) if qa in s), qa)
            sent_b = next((s for s in re.split(r"(?<=[.;])\s+", hb.text) if qb in s), qb)
            self._add(ctx, "Notice period", "clause", Side(Cite(ha.chunk_id, sent_a), qa, sent_a), Side(Cite(hb.chunk_id, sent_b), qb, sent_b),
                      "Different notice periods appear in the documents.", "medium", None)

    def _add(self, ctx, topic, nature, a: Side, b: Side, explanation, confidence, etype) -> None:
        key = (topic.lower(), frozenset({_norm_val(a.value), _norm_val(b.value)}))
        for c in ctx.board.contradictions:
            if (c.topic.lower(), frozenset({_norm_val(c.a.value), _norm_val(c.b.value)})) == key:
                return
        ctx.board.contradictions.append(ContradictionItem(ctx.board.next_id("x"), topic, nature, a, b, explanation, confidence, etype))

    # ----------------------------------------------------------------- resolve
    def _resolve(self, ctx, cid: str) -> StepResult:
        board = ctx.board
        c = next((x for x in board.contradictions if x.id == cid), None)
        if c is None:
            return StepResult("skipped", "Contradiction no longer on the board")
        sides = {"a": c.a, "b": c.b}
        prov: dict = {"sides": {}, "corroboration": {"a": [], "b": []}}
        for k, s in sides.items():
            h = board.evidence[s.cite.chunk_id]
            prov["sides"][k] = {"document": h.document_name, "docType": h.doc_type, "page": h.page,
                                "role": SOURCE_ROLE.get(h.doc_type, "a case document")}
        exclude = {c.a.cite.chunk_id, c.b.cite.chunk_id}
        event_words = (c.event_type or c.topic).replace("_", " ")
        for k, s in sides.items():
            res = ctx.tool("case_search", query=f"{event_words} {s.value}", k=6, exclude_chunk_ids=exclude, broaden=True)
            for h in res.hits:
                if h.flagged:
                    continue
                if c.event_type:
                    match = any(ev.event_type == c.event_type and ev.date_text.lower() == s.value.lower() or
                                (ev.event_type == c.event_type and ev.date_iso and ev.date_iso == _iso_of(s.value)) for ev in events_in(h.text))
                else:
                    match = s.value.lower() in h.text.lower()
                if match:
                    board.add_evidence([h])
                    prov["corroboration"][k].append({"chunkId": h.chunk_id, "document": h.document_name, "page": h.page})
        ca, cb = prov["corroboration"]["a"], prov["corroboration"]["b"]
        if ca and not cb:
            assessment = f"{c.a.value} is also stated in {ca[0]['document']} (p.{ca[0]['page']}); {c.b.value} is not independently corroborated."
        elif cb and not ca:
            assessment = f"{c.b.value} is also stated in {cb[0]['document']} (p.{cb[0]['page']}); {c.a.value} is not independently corroborated."
        elif ca and cb:
            assessment = "Both values are repeated elsewhere in the record; the conflict persists across sources."
        else:
            assessment = "No independent record in the case corroborates either value."
        prov["assessment"] = assessment + " FormLaw does not choose between them — lawyer review required."
        c.provenance, c.resolved = prov, True

        if c.event_type == "arrest":
            docs = ctx.tool("list_documents")
            if not any(d["docType"] == "arrest_memo" for d in docs):
                if not any(m.key == "arrest_memo" for m in board.missing):
                    board.missing.append(MissingItem(board.next_id("m"), "Certified arrest memo",
                                                     "The arrest memo is the primary record of the date and time of arrest and would settle this conflict.",
                                                     "conflict_resolution", "high", None, "arrest_memo"))
        return StepResult("ok", f"{c.topic}: {assessment}", {"corroborated": bool(ca or cb)})


def _iso_of(value: str) -> str | None:
    from ...ingestion.profile import parse_dates
    p = parse_dates(value)
    return p[0][1] if p else None
