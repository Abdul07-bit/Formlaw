"""
Legal Research Agent — searches only FormLaw's approved, provenance-tracked legal corpus. Distinguishes judgments,
statute sections, constitutional articles, regulations and rules by the corpus `kind`. It never generates an
authority: if nothing relevant is indexed it says so. Each authority keeps source, URL, licence and content hash.
"""
from __future__ import annotations

import re

from ..base import AgentSpec, StepResult
from ..runtime.state import AuthorityItem

SPEC = AgentSpec(
    name="Legal Research Agent",
    purpose="Find authorities in the verified legal corpus relevant to the legal issue",
    actions=("research.search",),
    tools=frozenset({"corpus_search", "corpus_lookup_citation"}),
    inputs="legal issue / topic",
    outputs="authorities with court, date, citation, page, verbatim passage, source, licence, hash",
    failure_modes="nothing relevant indexed → one reformulated search → 'not in verified corpus'",
    verification="authority = an existing corpus row; passage text is the stored chunk; Verification Agent confirms the hash",
)
_W = re.compile(r"[a-z]{3,}")
_STOP = set("the and was for that with this from what when were who into does how can under which about find authorities "
            "authority case law laws legal relevant supporting support argument judgment judgments court courts held hold "
            "supreme high india indian section sections provision provisions principle principles research show give".split())
_CITE = re.compile(r"\d{4}\s*INSC\s*\d+|\(\d{4}\)\s*\d+\s*SCC\s*\d+|AIR\s*\d{4}\s*SC\s*\d+", re.I)


def stems(text: str) -> set[str]:
    return {w[:5] for w in _W.findall(text.lower()) if w not in _STOP}


def tidy(text: str, limit: int = 700) -> str:
    """A contiguous slice of the passage starting and ending at sentence boundaries (still verbatim)."""
    t = text.strip()
    m = re.search(r"(?<=[.?!])\s+(?=[A-Z])", t[:200]) if t and (t[0].islower() or not t[0].isalnum()) else None
    if m:
        t = t[m.end():]
    if len(t) > limit:
        cut = t.rfind(". ", 0, limit)
        t = t[: cut + 1] if cut > limit // 3 else t[:limit]
    return t


class ResearchAgent:
    spec = SPEC

    def run(self, ctx, step) -> StepResult:
        issue = step.params.get("issue") or ctx.state.topic or ctx.state.goal
        for cite in _CITE.findall(issue):
            if not ctx.tool("corpus_lookup_citation", citation=cite):
                return StepResult("insufficient", f"“{cite}” is not in FormLaw's verified corpus — it will not be described",
                                  {"unknown_citation": cite})
        hits = ctx.tool("corpus_search", query=issue, k=8)
        q = stems(issue)
        gate = 0.5 if step.params.get("attempt", 1) == 1 else 0.34
        relevant = [h for h in hits if q and len(q & stems(h.chunk.text)) / len(q) >= gate]
        added = 0
        for h in relevant[:5]:
            if any(a.legal_chunk_id == h.chunk.id for a in ctx.board.authorities):
                continue
            d, s = h.doc, h.source
            ctx.board.authorities.append(AuthorityItem(
                ctx.board.next_id("a"), d.id, h.chunk.id, d.kind, d.title, d.neutral_citation or d.citation, d.court,
                d.decision_date.isoformat() if d.decision_date else None, h.chunk.page, tidy(h.chunk.text), s.name,
                d.source_url or d.document_url, d.license_ref, h.chunk.content_hash, issue[:300]))
            added += 1
        if not added:
            return StepResult("insufficient", "No passage in the verified corpus addresses this issue", {"authorities": 0})
        return StepResult("ok", f"{added} authority passage(s) found in the verified corpus", {"authorities": added})
