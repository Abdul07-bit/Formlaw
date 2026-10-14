"""
Legal corpus command line (run from backend/).

    python -m app.ingestion list-sources
    python -m app.ingestion validate-sources
    python -m app.ingestion plan   --start 2021-10-13 --end 2026-10-13
    python -m app.ingestion run    --source aws_sc_judgments --approved-only --dry-run
    python -m app.ingestion run    --source aws_sc_judgments --approved-only [--limit-per-year N]
    python -m app.ingestion report --start 2021-10-13 --end 2026-10-13 [--format md|json] [--out FILE]
    python -m app.ingestion status

Only APPROVED sources with a current terms review are ever fetched. CAPTCHA, logins, robots rules and rate limits are
never bypassed: such sources are RESTRICTED and need a manual or licensed import (local_import + manifest).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import app  # noqa: F401

from ..db.session import session_factory
from . import coverage, registry
from .ingest import ADAPTERS


def _d(s: str) -> date:
    return date.fromisoformat(s)


def cmd_list(_a) -> int:
    data = registry.load()
    print(f"{'key':<32} {'status':<15} {'auth':<5} {'adapter':<9} name")
    for s in data["sources"]:
        print(f"{s['key']:<32} {registry.effective_status(s):<15} {'yes' if s.get('authoritative') else 'no':<5} "
              f"{ADAPTERS.get(s['key'], '-'):<9} {s['name']}")
    return 0


def cmd_validate(_a) -> int:
    problems = registry.validate()
    for p in problems:
        print(f"PROBLEM  {p}")
    print("Registry OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def _plan(start: date, end: date, only: str | None = None) -> list[dict]:
    rows = []
    for s in registry.load()["sources"]:
        if only and s["key"] != only:
            continue
        status, adapter = registry.effective_status(s), ADAPTERS.get(s["key"])
        if status != "APPROVED":
            action = f"skip — {status}: {(s.get('decision_reason') or '')[:120]}"
        elif not adapter:
            action = "skip — approved but no adapter implemented (gap reported)"
        elif adapter == "manifest":
            action = "manual import only (requires --manifest with a licence per row)"
        else:
            action = f"fetch years {start.year}–{end.year}; judgments decided before {start} are counted as outside the window"
        rows.append({"source": s["key"], "status": status, "adapter": adapter, "action": action})
    return rows


def cmd_plan(a) -> int:
    start, end = (_d(a.start), _d(a.end)) if a.start else registry.target_window()
    print(f"Plan for {start} → {end}")
    for r in _plan(start, end, a.source):
        print(f"  {r['source']:<32} {r['status']:<15} {r['action']}")
    return 0


def cmd_run(a) -> int:
    if not a.approved_only:
        print("Refusing to run without --approved-only (explicit acknowledgement that only APPROVED sources are fetched).", file=sys.stderr)
        return 2
    start, end = (_d(a.start), _d(a.end)) if a.start else registry.target_window()
    plan = _plan(start, end, a.source)
    if not plan:
        print(f"Unknown source {a.source}", file=sys.stderr)
        return 2
    if a.dry_run:
        print(f"DRY RUN — nothing fetched or written. Window {start} → {end}")
        for r in plan:
            print(f"  {r['source']:<32} {r['status']:<15} {r['action']}")
        return 0
    from .ingest import run
    try:
        stats = run(a.source, limit_per_year=a.limit_per_year, manifest=Path(a.manifest) if a.manifest else None, start=start, end=end)
    except registry.IngestionRefused as e:
        print(f"REFUSED\n{e}", file=sys.stderr)
        return 2
    print(json.dumps(stats.as_dict(), indent=2))
    print("Queued is not ingested: run `report` to see what is actually covered.")
    return 0


def cmd_report(a) -> int:
    start, end = (_d(a.start), _d(a.end)) if a.start else (None, None)
    with session_factory()() as db:
        r = coverage.build(db, start, end)
    text = json.dumps(r, indent=2) if a.format == "json" else coverage.to_markdown(r)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"Wrote {a.out} — overall {r['overall']}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_status(_a) -> int:
    from .status import main as status_main
    status_main()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.ingestion", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-sources").set_defaults(fn=cmd_list)
    sub.add_parser("validate-sources").set_defaults(fn=cmd_validate)
    p = sub.add_parser("plan")
    p.add_argument("--start"), p.add_argument("--end"), p.add_argument("--source")
    p.set_defaults(fn=cmd_plan)
    r = sub.add_parser("run")
    r.add_argument("--source", required=True), r.add_argument("--approved-only", action="store_true"), r.add_argument("--dry-run", action="store_true")
    r.add_argument("--start"), r.add_argument("--end"), r.add_argument("--limit-per-year", type=int, default=0), r.add_argument("--manifest")
    r.set_defaults(fn=cmd_run)
    rep = sub.add_parser("report")
    rep.add_argument("--start"), rep.add_argument("--end"), rep.add_argument("--format", choices=["md", "json"], default="md"), rep.add_argument("--out")
    rep.set_defaults(fn=cmd_report)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = ap.parse_args(argv)
    if (getattr(a, "start", None) is None) != (getattr(a, "end", None) is None):
        ap.error("--start and --end go together")
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
