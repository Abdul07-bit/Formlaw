"""
Evidence Retrieval Agent — hybrid search over the case index; returns structured evidence onto the blackboard.

Signals for the orchestrator:
  weak            the best hit covers too little of the query (→ broaden once)
  conflict_probe  retrieved passages give different dates for a once-only event (→ contradiction agent)
  flagged         retrieved passages contain instruction-like text (→ security agent)
"""
from __future__ import annotations

from collections import defaultdict

from ...retrieval.case_index import tokens
from ..base import AgentSpec, StepResult
from ..grounding import SINGLE_OCCURRENCE, events_in

SPEC = AgentSpec(
    name="Retrieval Agent",
    purpose="Find the passages of the case documents that bear on the request",
    actions=("retrieval.search",),
    tools=frozenset({"case_search", "list_documents"}),
    inputs="queries, optional document/doc-type filters, broaden flag",
    outputs="evidence items (document, page, paragraph, section, text, hash, relevance, security flags)",
    failure_modes="no documents; weak recall → broadened search; still weak → insufficient evidence",
    verification="every item is a stored chunk of this case, loaded with organization_id + case_id",
)


def conflict_probe(hits) -> dict[str, set[str]]:
    by_type: dict[str, set[str]] = defaultdict(set)
    for h in hits:
        if h.flagged:
            continue
        for ev in events_in(h.text):
            if ev.event_type in SINGLE_OCCURRENCE and ev.date_iso:
                by_type[ev.event_type].add(ev.date_iso)
    return {k: v for k, v in by_type.items() if len(v) > 1}


class RetrievalAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        p = step.params
        queries = p.get("queries") or [p.get("query") or ctx.state.goal]
        docs = ctx.tool("list_documents")
        if not any(d["status"] == "indexed" for d in docs):
            return StepResult("insufficient", "No indexed documents in this case yet", {"no_documents": True})
        broaden = bool(p.get("broaden"))
        found, flagged, new, coverage = [], 0, 0, 0.0
        for q in queries[:6]:
            res = ctx.tool("case_search", query=q, k=int(p.get("k", 8)), doc_types=p.get("doc_types"),
                           exclude_chunk_ids=set(p.get("exclude", [])) or None, broaden=broaden)
            new += ctx.board.add_evidence(res.hits)
            found += res.hits
            if res.hits:
                qt = set(tokens(q))
                coverage = max(coverage, max(len(qt & set(tokens(h.text))) / max(len(qt), 1) for h in res.hits))
            if not broaden and q not in ctx.board.queries:
                ctx.board.queries.append(q)
        flagged = sum(h.flagged for h in found)
        docs_hit = len({h.document_id for h in found})
        unique = len({h.chunk_id for h in found})
        weak = not found or (coverage < 0.34 and unique < 3)
        conflicts = conflict_probe(found)
        mode = "broadened " if broaden else ""
        summary = (f"Retrieved {len({h.chunk_id for h in found})} {mode}passages from {docs_hit} document(s)"
                   + (f"; {flagged} contain instruction-like text" if flagged else ""))
        return StepResult("insufficient" if not found else "ok", summary,
                          {"weak": weak, "hits": len(found), "new": new, "flagged": flagged, "coverage": round(coverage, 2),
                           "conflict_probe": sorted(conflicts)})
