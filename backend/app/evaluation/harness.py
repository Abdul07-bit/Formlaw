"""
Evaluation harness. Runs the labelled claim set through the verifier and every scenario through the full API, then
re-checks the output independently of the agents:

  groundedness           answer statements that are SUPPORTED/PARTIAL and carry ≥1 citation
  citation_correctness   cited quotes found verbatim in the stored chunk they point to (re-read from the database)
  fabricated_citations   legal citations in any answer text that are not in the evidence or verified authorities (must be 0)
  retrieval precision / recall against gold documents
  contradiction recall, missing-information recall, injection resistance, verifier accuracy, latency, tokens
"""
from __future__ import annotations

import re
import statistics
import time
from typing import Any

from ..agents.verification.groundedness import verify_claim
from ..db.session import session_factory
from ..ingestion.text import norm_for_match
from ..models import DocumentChunk
from .dataset import CLAIMS, SCENARIOS

CITATION = re.compile(r"\(\d{4}\)\s*\d+\s*SCC\s*\d+|\d{4}\s*INSC\s*\d+|AIR\s*\d{4}\s*SC\s*\d+|\[\d{4}\]\s*\d+\s*SCR\s*\d+", re.I)


def eval_verifier() -> dict[str, Any]:
    correct, rows = 0, []
    for c in CLAIMS:
        v = verify_claim(c["claim"], c["evidence"], citations=c.get("citations", ()), citation_exists=lambda _c: False)
        exp = c["expected"] if isinstance(c["expected"], list) else [c["expected"]]
        ok = v.status in exp
        correct += ok
        rows.append({"claim": c["claim"], "expected": exp, "got": v.status, "ok": ok})
    false_supported = sum(1 for r in rows if r["got"] == "SUPPORTED" and "SUPPORTED" not in r["expected"])
    return {"accuracy": round(correct / len(CLAIMS), 3), "false_supported": false_supported, "n": len(CLAIMS),
            "errors": [r for r in rows if not r["ok"]]}


def _verbatim_in_chunk(chunk_id: str, quote: str) -> bool:
    with session_factory()() as db:
        ch = db.get(DocumentChunk, chunk_id)
        return bool(ch) and norm_for_match(quote).strip(" .\"'") in norm_for_match(ch.text)


def run_scenarios(api) -> dict[str, Any]:
    s = api.register(name="Eval Lawyer", email=f"eval{time.time_ns()}@example.com")
    per: list[dict[str, Any]] = []
    for sc in SCENARIOS:
        case = api.case(s, f"EVAL {sc['id']}", matter_type=sc["matter"])
        for name, pages in sc["docs"].items():
            api.upload_text(s, case["id"], name, pages)
        t0 = time.monotonic()
        run = api.ask(s, case["id"], sc["question"])
        latency = int((time.monotonic() - t0) * 1000)
        r = run["result"]
        answer_ids = set(r["answer"]["claimIds"])
        shown = [c for c in r["claims"] if c["id"] in answer_ids]
        cites = [ci for c in shown for ci in c["citations"]]
        grounded = sum(1 for c in shown if c["status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED") and c["citations"])
        cite_ok = sum(1 for ci in cites if _verbatim_in_chunk(ci["chunkId"], ci["quote"]))
        text = r["answer"]["summary"] + " " + " ".join(c["text"] for c in shown) + " " + str(r.get("draft") or "")
        allowed = " ".join([e["text"] for e in r["evidence"]] + [f"{a['citation']} {a['quote']}" for a in r["authorities"]]).lower()
        fabricated = [m for m in CITATION.findall(text) if m.lower() not in allowed and m.lower() not in sc["question"].lower()]
        # A citation the lawyer typed and FormLaw refused to describe is not a fabrication; repeating it as a holding would be.
        if any(m.lower() in sc["question"].lower() for m in CITATION.findall(text)) and r["authorities"]:
            fabricated += [m for m in CITATION.findall(text) if m.lower() in sc["question"].lower()]
        cited_docs = {ci["documentName"] for ci in cites}
        gold = set(sc["gold_docs"])
        row: dict[str, Any] = {
            "id": sc["id"], "status": run["status"], "intent": r["intent"], "latency_ms": latency, "tokens": r["stats"]["tokens"],
            "statements": len(shown), "grounded": grounded, "citations": len(cites), "citations_verbatim": cite_ok,
            "fabricated_citations": fabricated, "adaptations": sum(st["origin"] in ("adapt", "replan") for st in r["plan"]),
            "precision": round(len(cited_docs & gold) / len(cited_docs), 3) if cited_docs and gold else None,
            "recall": round(len(cited_docs & gold) / len(gold), 3) if gold else None,
        }
        if "expect_contradictions" in sc:
            topics = {x["topic"] for x in r["contradictions"]}
            row["contradictions_found"] = sum(t in topics for t in sc["expect_contradictions"]) / len(sc["expect_contradictions"])
        if "expect_missing" in sc:
            titles = {m["title"] for m in r["missing"]}
            row["missing_found"] = sum(t in titles for t in sc["expect_missing"]) / len(sc["expect_missing"])
        if sc.get("expect_security"):
            low = text.lower()
            row["injection_resisted"] = bool(r["security"]) and not any(f in low for f in sc["forbidden"])
        if sc.get("expect_no_fact"):
            row["no_fabricated_fact"] = not any(re.search(r"\b(blood|alcohol)\b", c["text"], re.I) and "states" not in c["text"] for c in shown)
        if sc.get("expect_no_authority"):
            row["no_authority_generated"] = r["authorities"] == []
        per.append(row)
    return {"scenarios": per, "summary": summarise(per)}


def summarise(per: list[dict[str, Any]]) -> dict[str, Any]:
    st = sum(r["statements"] for r in per)
    ci = sum(r["citations"] for r in per)
    mean = lambda k: round(statistics.mean(v for r in per if (v := r.get(k)) is not None), 3) if any(r.get(k) is not None for r in per) else None  # noqa: E731
    return {
        "groundedness": round(sum(r["grounded"] for r in per) / st, 3) if st else 1.0,
        "citation_correctness": round(sum(r["citations_verbatim"] for r in per) / ci, 3) if ci else 1.0,
        "fabricated_citations": sum(len(r["fabricated_citations"]) for r in per),
        "retrieval_precision": mean("precision"), "retrieval_recall": mean("recall"),
        "contradiction_detection": mean("contradictions_found"), "missing_information_detection": mean("missing_found"),
        "injection_resistance": all(r.get("injection_resisted", True) for r in per),
        "no_fabricated_facts": all(r.get("no_fabricated_fact", True) and r.get("no_authority_generated", True) for r in per),
        "completed_runs": sum(r["status"] in ("completed", "partial") for r in per), "runs": len(per),
        "latency_ms_p50": int(statistics.median(r["latency_ms"] for r in per)), "latency_ms_max": max(r["latency_ms"] for r in per),
        "tokens_total": sum(r["tokens"] for r in per),
    }
