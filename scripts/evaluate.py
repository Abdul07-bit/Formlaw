"""
Run FormLaw's evaluation set end to end and print / save the metrics.

    python scripts/evaluate.py                 # deterministic mode (no model, no network, no cost)
    python scripts/evaluate.py --with-llm      # uses the LLM configured in .env (makes real, billed model calls)
    python scripts/evaluate.py --out eval.json

Runs against a throwaway SQLite database; never touches your real data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-llm", action="store_true", help="use the configured LLM provider (billed)")
    ap.add_argument("--out", type=Path, help="write the full report as JSON")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="formlaw-eval-"))
    os.environ.update({"FORMLAW_ENV": "test", "DATABASE_URL": f"sqlite:///{(tmp / 'eval.db').as_posix()}",
                       "STORAGE_DIR": str(tmp / "storage"), "RUN_AGENTS_INLINE": "true", "DEMO_MODE": "true"})
    if not args.with_llm:
        os.environ["LLM_PROVIDER"] = "none"
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(ROOT / "backend" / "tests"))

    import app  # noqa: F401
    from fastapi.testclient import TestClient

    from app.db import session as db_session
    from app.db.base import Base
    from app.evaluation.harness import eval_verifier, run_scenarios
    from app.main import create_app
    from app.security import rate_limit
    from helpers import Api

    Base.metadata.create_all(db_session.init_engine())
    rate_limit.LIMITS["agent"] = (10_000, 60)
    report = {"mode": "llm" if args.with_llm else "deterministic", "verifier": eval_verifier(),
              **run_scenarios(Api(TestClient(create_app(), base_url="http://localhost")))}
    print(json.dumps({"mode": report["mode"], "verifier_accuracy": report["verifier"]["accuracy"],
                      "verifier_false_supported": report["verifier"]["false_supported"], **report["summary"]}, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Full report: {args.out}")
    if report["summary"]["fabricated_citations"]:
        raise SystemExit("FAIL: fabricated citations detected")


if __name__ == "__main__":
    main()
