"""
OBSERVE → ADAPT. After every step the orchestrator passes the step's signals through these rules; each rule may insert
new steps right after the current one. Rules are deterministic and bounded (each adaptation fires at most once per
trigger, and recomposition is limited by MAX_RETRIES / MAX_REPLANS).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..base import StepResult
from .state import PlanStep


@dataclass
class Adaptation:
    steps: list[PlanStep]
    message: str
    kind: str = "adapt"  # adapt | replan


def _pending(state, action: str) -> bool:
    return any(s.action == action and s.status == "pending" for s in state.plan)


def _ran(state, action: str, **params) -> bool:
    return any(s.action == action and all(s.params.get(k) == v for k, v in params.items()) for s in state.plan)


def observe(state, step: PlanStep, result: StepResult) -> list[Adaptation]:
    make, sig, out = state.make_step, result.signals, []

    if step.action == "retrieval.search":
        if sig.get("flagged") and not _pending(state, "security.screen"):
            out.append(Adaptation([make("security.screen", "Screen flagged passages", "adapt",
                                        "Retrieved text contains instructions aimed at the AI")],
                                  "Instruction-like text found in evidence → Security Agent screens it before any model sees it"))
        if sig.get("weak") and not step.params.get("broaden") and not sig.get("no_documents"):
            out.append(Adaptation([make("retrieval.search", "Broaden the search (legal synonyms, more results)", "adapt",
                                        "Initial evidence was thin", queries=step.params.get("queries", []), broaden=True, k=12)],
                                  "Retrieval returned little relevant evidence → broadening the query"))
        if sig.get("conflict_probe") and not _ran(state, "contradiction.detect"):
            kinds = ", ".join(k.replace("_", " ") for k in sig["conflict_probe"])
            out.append(Adaptation([make("contradiction.detect", "Compare the conflicting sources", "adapt",
                                        f"Retrieved sources give different dates ({kinds})", topic=state.topic)],
                                  f"Evidence gives different dates for the same {kinds} → launching the Contradiction Agent instead of picking one"))

    elif step.action == "contradiction.detect":
        new = [c for c in sig.get("contradictions", []) if not _ran(state, "contradiction.resolve", contradiction_id=c)]
        if new:
            steps = [make("contradiction.resolve", f"Check provenance and search for an independent record ({state.board_topic(c)})",
                          "adapt", "Conflict detected", contradiction_id=c) for c in new[:4]]
            out.append(Adaptation(steps, f"{len(new)} conflict(s) found → checking source provenance and searching for corroboration"))

    elif step.action == "research.search":
        if result.status == "insufficient" and step.params.get("attempt", 1) == 1 and not sig.get("unknown_citation"):
            issue = " ".join(dict.fromkeys(([state.topic] if state.topic else []) +
                                           [c.text[:80] for c in state.board.claims if c.kind == "issue"][:2])) or state.goal
            out.append(Adaptation([make("research.search", "Search again with a reformulated issue", "adapt",
                                        "No authority matched the first formulation", issue=issue, attempt=2)],
                                  "No authority found → reformulating the legal issue and searching once more"))

    elif step.action == "verification.verify":
        bad = sig.get("answer_unsupported") or []
        composes = sum(s.action == "answer.compose" for s in state.plan)
        if bad and composes <= state.limits.max_retries and state.budget.can_replan():
            state.budget.replans += 1
            out.append(Adaptation([make("answer.compose", "Recompose the answer from verified findings only", "replan",
                                        f"{len(bad)} answer statement(s) failed verification", strict=True),
                                   make("verification.verify", "Re-verify the recomposed answer", "replan")],
                                  f"{len(bad)} statement(s) in the answer failed verification → regenerating from verified evidence only", "replan"))
    return out
