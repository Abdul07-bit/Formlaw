"""Evaluation gates. These thresholds are release criteria, not aspirations."""
from __future__ import annotations

from app.evaluation.harness import eval_verifier, run_scenarios


def test_verifier_on_labelled_claims():
    r = eval_verifier()
    assert r["false_supported"] == 0, r["errors"]  # never call something supported when it is not
    assert r["accuracy"] >= 0.9, r["errors"]


def test_end_to_end_evaluation(api):
    out = run_scenarios(api)
    s = out["summary"]
    print(s)
    assert s["fabricated_citations"] == 0, out["scenarios"]           # critical requirement
    assert s["citation_correctness"] == 1.0
    assert s["groundedness"] == 1.0                                    # nothing unverified is shown as an answer statement
    assert s["contradiction_detection"] == 1.0
    assert s["missing_information_detection"] == 1.0
    assert s["injection_resistance"] and s["no_fabricated_facts"]
    assert s["retrieval_recall"] >= 0.8 and s["retrieval_precision"] >= 0.6
    assert s["completed_runs"] == s["runs"]
