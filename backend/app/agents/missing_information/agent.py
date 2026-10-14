"""
Missing Information Agent.

1. Referenced but absent: a document in the case refers to another record (arrest memo, annexure, witness statements,
   FSL report…) that is not among the uploaded documents. Cited to the passage that refers to it. High importance.
2. Checklist: records a matter of this type normally has, absent from the case. Medium importance, no citation.
Never fabricates the missing content — it only says what is absent and why it matters.
"""
from __future__ import annotations

import re

from ...ingestion.profile import REFERENCEABLE
from ..base import AgentSpec, StepResult
from ..runtime.state import Cite, MissingItem

SPEC = AgentSpec(
    name="Missing Information Agent",
    purpose="Identify records and facts the case file refers to or needs but does not contain",
    actions=("missing_information.detect",),
    tools=frozenset({"list_documents", "case_search"}),
    inputs="document list with profiled references; matter type",
    outputs="missing-information items (title, why it matters, basis, citation when referenced)",
    failure_modes="doc-type heuristics can mislabel a document; items are suggestions for the lawyer to confirm",
    verification="'referenced' items cite the passage that mentions the record",
)
WHY = {
    "arrest_memo": "Primary record of the date, time and place of arrest and of compliance with arrest safeguards.",
    "seizure_memo": "Records what was seized, where and before which witnesses.",
    "medical_report": "Establishes injuries / medical condition at the relevant time.",
    "witness_statement": "Needed to test the prosecution narrative and prepare cross-examination.",
    "cctv_footage": "Independent evidence of the events referred to in the record.",
    "call_records": "Can corroborate or contradict presence and contact claims.",
    "charge_sheet": "Sets out the final case and evidence relied on by the prosecution.",
    "remand_report": "Shows the grounds given to the court for custody.",
    "fir": "The first recorded version of the allegations.",
    "forensic_report": "Scientific evidence relied on by the investigation.",
    "bail_order": "Records the court's findings and conditions on bail.",
    "annexure": "Annexures referenced in a document form part of it; without them the document is incomplete.",
    "notice": "Notices referenced in the record determine deadlines and rights.",
    "invoice": "Proves the amounts claimed.",
    "power_of_attorney": "Establishes authority to act for a party.",
}
CHECKLISTS = {
    "criminal": ["fir", "arrest_memo", "remand_report", "witness_statement", "seizure_memo", "medical_report", "charge_sheet"],
    "contract": ["annexure", "notice", "invoice"],
    "employment": ["notice"],
    "property": ["power_of_attorney"],
}
# Doc types that satisfy a referenced record.
SATISFIES = {"witness_statement": {"witness_statement"}, "annexure": {"annexure"}, "notice": {"legal_notice", "notice"}}


class MissingInformationAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        board = ctx.board
        docs = ctx.tool("list_documents")
        present_types = {d["docType"] for d in docs}
        names = " ".join(d["name"].lower() for d in docs)
        have = {m.key for m in board.missing}

        def present(key: str) -> bool:
            return bool(SATISFIES.get(key, {key}) & present_types) or key.replace("_", " ") in names.replace("_", " ")

        referenced = {r for d in docs for r in d.get("references", [])}
        added = 0
        for key in sorted(referenced):
            if key in have or present(key):
                continue
            label, pats = REFERENCEABLE[key]
            res = ctx.tool("case_search", query=label, k=4)
            hit = next((h for h in res.hits if not h.flagged and any(re.search(p, h.text, re.I) for p in pats)), None)
            cite = None
            if hit:
                sent = next((s for s in re.split(r"(?<=[.!?])\s+", hit.text) if any(re.search(p, s, re.I) for p in pats)), hit.text[:240])
                cite = Cite(hit.chunk_id, sent)
                board.add_evidence([hit])
            board.missing.append(MissingItem(board.next_id("m"), label, WHY.get(key, "Referred to in the case documents."),
                                             "referenced_in_documents", "high", cite, key))
            have.add(key)
            added += 1
        for key in CHECKLISTS.get(ctx.state.matter_type, []):
            if key in have or present(key):
                continue
            board.missing.append(MissingItem(board.next_id("m"), REFERENCEABLE[key][0], WHY.get(key, ""), "checklist", "medium", None, key))
            have.add(key)
            added += 1
        ref_n = sum(m.basis == "referenced_in_documents" for m in board.missing)
        return StepResult("ok", f"{added} missing item(s): {ref_n} referenced in the documents but not provided",
                          {"missing": added})
