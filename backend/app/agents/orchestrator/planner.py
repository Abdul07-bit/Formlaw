"""
Planner. Plans are composed only from the action catalogue below — a model cannot add agents, tools or actions.
With a model configured, the planner asks it for better search queries and focus topics (validated, bounded);
the step structure always comes from the intent template, which keeps execution predictable and auditable.
"""
from __future__ import annotations

import itertools
import re
from typing import Any

from ...domain.enums import Intent
from ...llm.schemas import PlanOut
from ..runtime.state import PlanStep

# action → agent. The only things a plan may contain.
CATALOGUE: dict[str, str] = {
    "security.scan_request": "Security Agent",
    "security.screen": "Security Agent",
    "retrieval.search": "Retrieval Agent",
    "case_analysis.extract": "Case Analysis Agent",
    "contract_review.review": "Contract Review Agent",
    "contradiction.detect": "Contradiction Agent",
    "contradiction.resolve": "Contradiction Agent",
    "missing_information.detect": "Missing Information Agent",
    "research.search": "Legal Research Agent",
    "drafting.compose": "Drafting Agent",
    "verification.verify": "Verification Agent",
    "answer.compose": "Orchestrator",
}
SEED_QUERIES: dict[str, list[str]] = {
    "criminal": ["accused complainant police officer", "arrested arrest date custody", "offence section alleged",
                 "witness statement saw", "seized recovered", "remand magistrate"],
    "contract": ["agreement between parties", "payment consideration invoice", "termination notice", "liability indemnity",
                 "dispute arbitration governing law"],
    "default": ["parties", "date", "alleged", "agreed", "notice"],
}


class StepFactory:
    def __init__(self) -> None:
        self._n = itertools.count(1)

    def __call__(self, action: str, label: str, origin: str = "plan", reason: str = "", **params: Any) -> PlanStep:
        if action not in CATALOGUE:
            raise ValueError(f"Unknown plan action {action}")
        return PlanStep(f"s{next(self._n)}", CATALOGUE[action], action, label, params, origin=origin, reason=reason)  # type: ignore[arg-type]


def _topic_label(topic: str) -> str:
    return f"{topic}-related" if topic else "relevant"


def build_plan(state, make: StepFactory) -> list[PlanStep]:
    i, topic, board = state.intent, state.topic, state.board
    seeds = SEED_QUERIES.get(state.matter_type, SEED_QUERIES["default"])
    q_main = list(dict.fromkeys([state.goal] + board.queries + ([topic] if topic else [])))
    broad = list(dict.fromkeys(q_main + seeds))[:7]
    R = lambda queries, label=None: make("retrieval.search", label or f"Retrieve {_topic_label(topic)} evidence", queries=queries)  # noqa: E731
    A = lambda **kw: make("case_analysis.extract", "Extract facts, parties and dated events", focus=board.focus or ([topic] if topic else []), **kw)  # noqa: E731
    C = make("contradiction.detect", "Check sources for conflicting statements", topic=topic) if i != Intent.EVIDENCE_QA else None
    M = lambda: make("missing_information.detect", "Identify missing records")  # noqa: E731
    RES = lambda: make("research.search", "Search the verified legal corpus for authorities", issue=topic or state.goal, attempt=1)  # noqa: E731
    COMPOSE = lambda: make("answer.compose", "Compose the answer from verified evidence")  # noqa: E731
    VERIFY = lambda label="Verify every claim against its source": make("verification.verify", label)  # noqa: E731

    if i == Intent.EVIDENCE_QA:
        steps = [R(q_main), COMPOSE(), VERIFY()]
    elif i == Intent.CONTRADICTIONS:
        steps = [R(list(dict.fromkeys(q_main + ([f"{topic} date"] if topic else []) + seeds[:3]))), A(), C, COMPOSE(), VERIFY()]
    elif i == Intent.TIMELINE:
        steps = [R(broad + ["dated on"], "Retrieve dated events"), A(scope="all"), C, COMPOSE(), VERIFY()]
    elif i == Intent.MISSING_INFO:
        steps = [R(broad), A(), M(), COMPOSE(), VERIFY()]
    elif i == Intent.CONTRACT_REVIEW:
        steps = [make("contract_review.review", "Extract and classify contract clauses"), C, COMPOSE(), VERIFY()]
    elif i == Intent.LEGAL_RESEARCH:
        steps = [R(q_main, "Retrieve case context for the issue"), RES(), COMPOSE(), VERIFY("Verify authorities against the corpus")]
    elif i == Intent.DRAFT:
        steps = [R(broad), A(scope="all"), C, M(), *( [RES()] if state.wants_research else []),
                 VERIFY("Verify facts before drafting"), make("drafting.compose", "Prepare the draft from verified facts", kind=state.draft_kind),
                 COMPOSE(), VERIFY()]
    elif i == Intent.COMPARE_DOCUMENTS:
        steps = [R(broad, "Retrieve passages from each document"), A(scope="all"), C, COMPOSE(), VERIFY()]
    elif i == Intent.SUMMARY:
        steps = [R(broad), A(scope="all"), COMPOSE(), VERIFY()]
    else:  # CASE_REVIEW
        steps = [R(broad, "Retrieve the material evidence"), A(scope="all"), C, M(), *([RES()] if state.wants_research else []), COMPOSE(), VERIFY()]
    return [s for s in steps if s is not None]


def refine_with_model(state, llm) -> str | None:
    """Ask the model for focused queries / topics. Output is length-bounded and sanitised; structure is not negotiable."""
    out = llm("plan", "plan", PlanOut, request=state.goal, context={
        "intent": state.intent, "matter_type": state.matter_type,
        "documents": [{"name": d["name"], "type": d["docType"]} for d in state.documents][:40]})
    if out is None:
        return None
    clean = lambda s: re.sub(r"[^\w\s'.-]", " ", s)[:100].strip()  # noqa: E731
    state.board.queries = [q for q in (clean(q) for q in out.queries) if q][:5]
    state.board.focus = [f for f in (clean(f) for f in out.focus_topics) if f][:3]
    return out.rationale[:300] or None
