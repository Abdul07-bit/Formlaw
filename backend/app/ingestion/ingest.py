"""
Ingest an APPROVED source.

    python -m app.ingestion.ingest --source aws_sc_judgments --years 2016-2026 --limit-per-year 30
    python -m app.ingestion.ingest --source aws_sc_judgments --years 2016-2026          (full years; ~3.3 GB streamed)
    python -m app.ingestion.ingest --source local_import --manifest /path/manifest.jsonl

Refuses any source whose registry status is not APPROVED. Then run `validate`, `index`, `status`.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import app  # noqa: F401

from ..db.base import utcnow
from ..db.session import session_factory
from ..models import IngestionRun
from . import registry
from .core import Stats, process

log = logging.getLogger("formlaw.ingestion")


def _years(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(y) for y in spec.split(",")]


ADAPTERS = {"aws_sc_judgments": "by_year", "local_import": "manifest"}


def _merge(total: Stats, part: Stats) -> None:
    for k in ("seen", "inserted", "quarantined", "duplicates", "conflicts", "out_of_window"):
        setattr(total, k, getattr(total, k) + getattr(part, k))
    total.errors += part.errors


def run(source_key: str, *, years: list[int] | None = None, limit_per_year: int = 0, manifest: Path | None = None,
        start: date | None = None, end: date | None = None) -> Stats:
    """
    Ingest one APPROVED source. Judgments decided before `start` (default: the registry's target window) are counted as
    out_of_window and skipped. Per-year counts are stored on the run (stats.years) so the coverage report can say what was
    discovered vs ingested for each year — without them it reports coverage as unmeasured.
    """
    stats = Stats()
    with session_factory()() as db:
        source, entry = registry.require_approved(db, source_key)  # LICENSE / TERMS CHECK
        license_ref = f"{entry['license'][:120]} · {entry.get('terms_url') or ''}"
        w_start, w_end = registry.target_window()
        start, end = start or w_start, end or w_end
        run_row = IngestionRun(source_key=source_key, stats={"window": [start.isoformat(), end.isoformat()]})
        db.add(run_row)
        db.commit()
        per_year: dict[str, dict] = {}

        def consume(items, st: Stats):
            for item in items:
                try:
                    process(db, source, item, st, license_ref=license_ref, window_start=start)
                    db.commit()  # commit per document: a failure never loses earlier work
                except Exception as e:  # noqa: BLE001 — one bad document must not stop the run; it is recorded
                    db.rollback()
                    st.errors.append(f"{item.external_id}: {type(e).__name__}: {str(e)[:120]}")
                    log.exception("ingest failed for %s", item.external_id)
                if st.seen % 25 == 0:
                    print(f"  … {st.seen} processed ({st.inserted} indexed, {st.quarantined} quarantined)", flush=True)

        if ADAPTERS.get(source_key) == "by_year":
            from .adapters import aws_sc
            for y in years or list(range(start.year, end.year + 1)):
                print(f"[{source_key}] year {y}", flush=True)
                ys = Stats()
                try:
                    consume(aws_sc.iter_items(y, limit=limit_per_year), ys)
                    complete = not limit_per_year
                except Exception as e:  # noqa: BLE001 — a missing/failed year is reported, others continue
                    ys.errors.append(f"year {y}: {type(e).__name__}: {str(e)[:160]}")
                    complete = False
                per_year[str(y)] = ys.as_dict() | {"complete_listing": complete, "limit_per_year": limit_per_year}
                _merge(stats, ys)
        elif ADAPTERS.get(source_key) == "manifest":
            if not manifest:
                raise SystemExit("--manifest is required for local_import")
            from .adapters import local_manifest
            consume(local_manifest.iter_items(manifest, stats.errors), stats)
        else:
            raise registry.IngestionRefused(f"{source_key} is APPROVED but has no adapter yet (see legal-data/README.md).")

        run_row.status, run_row.finished_at = "completed", utcnow()
        run_row.stats = stats.as_dict() | {"window": [start.isoformat(), end.isoformat()], "years": per_year}
        db.commit()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest an approved legal source")
    ap.add_argument("--source", required=True)
    ap.add_argument("--years", help="e.g. 2021-2026 or 2021,2022 (default: the registry's target_window)")
    ap.add_argument("--limit-per-year", type=int, default=0, help="0 = all judgments in each year")
    ap.add_argument("--manifest", type=Path)
    a = ap.parse_args()
    try:
        s = run(a.source, years=_years(a.years) if a.years else None, limit_per_year=a.limit_per_year, manifest=a.manifest)
    except registry.IngestionRefused as e:
        print(f"SOURCE\n{e}", file=sys.stderr)
        raise SystemExit(2)
    print(s.as_dict())


if __name__ == "__main__":
    main()
