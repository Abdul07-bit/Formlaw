"""
Corpus coverage report for a date window (default: the registry's target_window, 13 Oct 2021 – 13 Oct 2026).

A year is reported COMPLETE only when an ingestion run listed the source's entire catalogue for that year
(no per-year limit, no listing error) and every listed document is accounted for (ingested, quarantined for review,
duplicate of an existing record, or outside the window). Anything less is PARTIAL, NOT_MEASURED or NOT_ATTEMPTED.
The report never infers completeness from document counts alone, and it never counts SYNTHETIC records.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import IngestionRun, LegalDocument, LegalSource
from . import registry


def _months(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _latest_year_runs(db: Session, source_key: str) -> dict[int, dict]:
    """For each year, the stats of the most recent run that recorded that year."""
    out: dict[int, dict] = {}
    for run in db.scalars(select(IngestionRun).where(IngestionRun.source_key == source_key).order_by(IngestionRun.created_at)):
        for y, st in ((run.stats or {}).get("years") or {}).items():
            out[int(y)] = st | {"runAt": run.created_at.isoformat(timespec="minutes") if run.created_at else None}
    return out


def build(db: Session, start: date | None = None, end: date | None = None) -> dict[str, Any]:
    data = registry.load()
    w_start, w_end = registry.target_window(data)
    start, end = start or w_start, end or w_end
    months = _months(start, end)
    years = list(range(start.year, end.year + 1))
    in_window = (LegalDocument.decision_date >= start) & (LegalDocument.decision_date <= end) & \
                (LegalDocument.data_class == "VERIFIED_SOURCE") & (LegalDocument.kind == "judgment")

    sources, gaps = [], []
    by_court: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_month: dict[str, int] = {m: 0 for m in months}
    for entry in data["sources"]:
        row = db.scalar(select(LegalSource).where(LegalSource.key == entry["key"]))
        status = registry.effective_status(entry)
        out: dict[str, Any] = {
            "key": entry["key"], "name": entry["name"], "registryStatus": status, "authoritative": bool(entry.get("authoritative")),
            "licence": entry.get("license") or "not reviewed", "commercialUse": entry.get("commercial_use_allowed"),
            "termsLastReviewed": entry.get("last_checked"), "kinds": entry.get("kinds", []), "knownGaps": entry.get("known_gaps", []),
        }
        if status != "APPROVED":
            out["notIngestedReason"] = entry.get("decision_reason") or status
            if "judgment" in entry.get("kinds", []):
                gaps.append(f"{entry['name']}: {status} — not ingested ({(entry.get('decision_reason') or '')[:160]})")
        if row is None:
            sources.append(out | {"ingested": 0, "quarantined": 0, "years": {}})
            continue
        base = select(LegalDocument).where(LegalDocument.source_id == row.id, in_window)
        passed = db.scalars(base.where(LegalDocument.quality_status == "passed")).all()
        quarantined = db.scalar(select(func.count()).select_from(base.where(LegalDocument.quality_status == "quarantined").subquery())) or 0
        per_year_db: dict[int, dict[str, int]] = defaultdict(lambda: {"ingested": 0, "quarantined": 0})
        for d in passed:
            per_year_db[d.decision_date.year]["ingested"] += 1
            by_court[d.court or "unknown court"][str(d.decision_date.year)] += 1
            by_month[f"{d.decision_date.year:04d}-{d.decision_date.month:02d}"] += 1
        for d in db.scalars(base.where(LegalDocument.quality_status == "quarantined")):
            per_year_db[d.decision_date.year]["quarantined"] += 1
        runs = _latest_year_runs(db, entry["key"])
        year_rows = {}
        for y in years:
            dbc, st = per_year_db[y], runs.get(y)
            r: dict[str, Any] = {"ingested": dbc["ingested"], "awaitingReview": dbc["quarantined"]}
            if st is None:
                r["status"] = "NOT_ATTEMPTED" if not (dbc["ingested"] or dbc["quarantined"]) else "NOT_MEASURED"
                r["note"] = "No per-year listing recorded for this year; completeness unknown."
            else:
                errors = len(st.get("errors", []))
                r |= {"discovered": st.get("seen", 0), "duplicates": st.get("duplicates", 0), "outsideWindow": st.get("out_of_window", 0),
                      "failed": errors, "lastRun": st.get("runAt")}
                accounted = st.get("inserted", 0) + st.get("quarantined", 0) + st.get("duplicates", 0) + st.get("out_of_window", 0) + st.get("conflicts", 0)
                if not st.get("complete_listing"):
                    r["status"] = "PARTIAL"
                    r["note"] = f"Sampled run (limit {st.get('limit_per_year')} per year) or the listing failed; not a complete count."
                elif errors or accounted < st.get("seen", 0):
                    r["status"] = "PARTIAL"
                    r["note"] = f"{st.get('seen', 0) - accounted + errors} listed document(s) not accounted for or failed."
                else:
                    r["status"] = "COMPLETE"
            year_rows[str(y)] = r
        dates = db.execute(select(func.min(LegalDocument.ingested_at), func.max(LegalDocument.ingested_at))
                           .where(LegalDocument.source_id == row.id)).one()
        sources.append(out | {"ingested": len(passed), "awaitingReview": quarantined, "years": year_rows,
                              "firstIngested": dates[0].isoformat(timespec="minutes") if dates[0] else None,
                              "lastIngested": dates[1].isoformat(timespec="minutes") if dates[1] else None})

    kinds = dict(db.execute(select(LegalDocument.kind, func.count()).where(LegalDocument.data_class == "VERIFIED_SOURCE",
                                                                            LegalDocument.quality_status == "passed")
                            .group_by(LegalDocument.kind)).all())
    empty_months = [m for m, n in by_month.items() if n == 0]
    if empty_months:
        gaps.append(f"{len(empty_months)} of {len(months)} months in the window have no ingested judgment: "
                    + ", ".join(empty_months[:24]) + (" …" if len(empty_months) > 24 else ""))
    year_statuses = [r["status"] for s in sources for r in s.get("years", {}).values() if s["registryStatus"] == "APPROVED"
                     and "judgment" in s["kinds"]]
    courts = sorted(by_court)
    if not any("high court" in c.lower() for c in courts):
        gaps.append("No High Court judgments are ingested.")
    complete = bool(year_statuses) and all(s == "COMPLETE" for s in year_statuses) and not empty_months
    statement = ("Coverage of every approved judgment source is complete for this window, measured against each source's own "
                 "catalogue. This is not national coverage of all Indian courts." if complete else
                 "Coverage is INCOMPLETE or UNMEASURED for this window. Do not describe the corpus as covering this period.")
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "overall": "COMPLETE" if complete else "INCOMPLETE",
        "statement": statement,
        "totals": {"judgmentsInWindow": sum(by_month.values()), "courts": len(courts),
                   "awaitingReview": sum(s.get("awaitingReview", 0) for s in sources)},
        "byMonth": by_month, "byCourt": {c: dict(v) for c, v in sorted(by_court.items())}, "byDocumentType": kinds,
        "sources": sources, "gaps": gaps,
    }


def to_markdown(r: dict[str, Any]) -> str:
    L = [f"# FormLaw corpus coverage report", "",
         f"Window **{r['window']['start']} → {r['window']['end']}** · generated {r['generatedAt']} · overall **{r['overall']}**", "",
         f"> {r['statement']}", "",
         f"Judgments in window: **{r['totals']['judgmentsInWindow']}** · courts: {r['totals']['courts']} · "
         f"awaiting review (quarantined): {r['totals']['awaitingReview']}", "", "## Gaps", ""]
    L += [f"* {g}" for g in r["gaps"]] or ["* none recorded"]
    L += ["", "## Sources", "", "| Source | Registry status | Authoritative | Ingested (window) | Awaiting review | Licence |", "|---|---|---|---|---|---|"]
    for s in r["sources"]:
        L.append(f"| {s['name']} | {s['registryStatus']} | {'yes' if s['authoritative'] else 'no'} | {s.get('ingested', 0)} | "
                 f"{s.get('awaitingReview', 0)} | {(s['licence'] or '')[:60]} |")
    for s in r["sources"]:
        if s.get("years") and (s.get("ingested") or s["registryStatus"] == "APPROVED") and "judgment" in s["kinds"]:
            L += ["", f"### {s['name']} — by year", "", "| Year | Status | Discovered | Ingested | Awaiting review | Duplicates | Outside window | Failed | Note |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for y, v in s["years"].items():
                L.append(f"| {y} | {v['status']} | {v.get('discovered', '—')} | {v['ingested']} | {v['awaitingReview']} | "
                         f"{v.get('duplicates', '—')} | {v.get('outsideWindow', '—')} | {v.get('failed', '—')} | {v.get('note', '')} |")
    L += ["", "## By court and year", "", "| Court | " + " | ".join(str(y) for y in range(int(r['window']['start'][:4]), int(r['window']['end'][:4]) + 1)) + " |"]
    L.append("|---|" + "---|" * (int(r['window']['end'][:4]) - int(r['window']['start'][:4]) + 1))
    for c, v in r["byCourt"].items():
        L.append(f"| {c} | " + " | ".join(str(v.get(str(y), 0)) for y in range(int(r['window']['start'][:4]), int(r['window']['end'][:4]) + 1)) + " |")
    L += ["", "## By month", "", "| Month | Judgments |", "|---|---|"] + [f"| {m} | {n} |" for m, n in r["byMonth"].items()]
    L += ["", "## By document type (all verified documents)", "", "| Type | Documents |", "|---|---|"] + \
         [f"| {k} | {n} |" for k, n in sorted(r["byDocumentType"].items())]
    return "\n".join(L) + "\n"
