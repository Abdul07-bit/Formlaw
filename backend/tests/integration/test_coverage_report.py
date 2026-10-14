"""The coverage report distinguishes measured coverage from gaps and never claims what it cannot show."""
from __future__ import annotations

from datetime import date

from app.db import session as db_session
from app.ingestion import coverage
from app.ingestion.__main__ import main as cli
from app.models import IngestionRun, LegalDocument
from tests.integration.test_legal_corpus import _ingest, _item

MARCH = (date(2023, 3, 1), date(2023, 3, 31))


def _run(year: int, **st):
    stats = {"seen": 0, "inserted": 0, "quarantined": 0, "duplicates": 0, "conflicts": 0, "out_of_window": 0, "errors": [],
             "complete_listing": True, "limit_per_year": 0} | st
    with db_session.session_factory()() as db:
        db.add(IngestionRun(source_key="aws_sc_judgments", status="completed", stats={"years": {str(year): stats}}))
        db.commit()


def _report(start=MARCH[0], end=MARCH[1]):
    with db_session.session_factory()() as db:
        return coverage.build(db, start, end)


def _sc(r):
    return next(s for s in r["sources"] if s["key"] == "aws_sc_judgments")


def test_nothing_ingested_is_reported_as_gaps(fresh_db):
    r = _report(date(2021, 10, 13), date(2026, 10, 13))
    assert r["overall"] == "INCOMPLETE" and "Do not describe the corpus" in r["statement"]
    assert len(r["byMonth"]) == 61 and r["totals"]["judgmentsInWindow"] == 0
    assert any("RESTRICTED" in g and "eCourts" in g for g in r["gaps"])
    assert any("No High Court" in g for g in r["gaps"])
    assert all(v["status"] == "NOT_ATTEMPTED" for v in _sc(r)["years"].values())


def test_complete_listing_marks_the_year_complete_but_not_the_corpus(fresh_db):
    _ingest(_item())  # decided 14-03-2023
    _run(2023, seen=1, inserted=1)
    r = _report()
    y = _sc(r)["years"]["2023"]
    assert (y["status"], y["discovered"], y["ingested"]) == ("COMPLETE", 1, 1)
    assert r["byMonth"] == {"2023-03": 1} and r["byCourt"] == {"Supreme Court of India": {"2023": 1}}
    # The approved High Court source has never been run, so the window as a whole is not complete.
    assert r["overall"] == "INCOMPLETE"


def test_sampled_or_failed_years_are_partial_and_old_data_is_unmeasured(fresh_db):
    _ingest(_item())
    assert _sc(_report())["years"]["2023"]["status"] == "NOT_MEASURED"  # data exists, but no listing was recorded
    _run(2023, seen=5, inserted=1, complete_listing=False, limit_per_year=1)
    assert _sc(_report())["years"]["2023"]["status"] == "PARTIAL"
    _run(2023, seen=3, inserted=1)  # complete listing, but 2 of 3 documents unaccounted for
    y = _sc(_report())["years"]["2023"]
    assert y["status"] == "PARTIAL" and "not accounted" in y["note"]


def test_synthetic_documents_never_count(fresh_db):
    _ingest(_item())
    with db_session.session_factory()() as db:
        db.query(LegalDocument).update({"data_class": "SYNTHETIC"})
        db.commit()
    assert _report()["totals"]["judgmentsInWindow"] == 0


def test_admin_coverage_endpoint(api, seeded):
    r = api.c.get("/api/v1/admin/corpus/coverage?start=2023-03-01&end=2023-03-31", headers=api.demo("admin").h)
    assert r.status_code == 200 and r.json()["window"] == {"start": "2023-03-01", "end": "2023-03-31"}
    assert api.c.get("/api/v1/admin/corpus/coverage", headers=api.demo("lawyer").h).status_code == 403


def test_cli_guards_and_dry_run(fresh_db, tmp_path, capsys):
    assert cli(["validate-sources"]) == 0
    assert cli(["run", "--source", "aws_sc_judgments", "--dry-run"]) == 2  # --approved-only is mandatory
    assert cli(["run", "--source", "aws_sc_judgments", "--approved-only", "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    with db_session.session_factory()() as db:
        assert db.query(IngestionRun).count() == 0  # a dry run writes nothing
    assert cli(["run", "--source", "india_code", "--approved-only"]) == 2  # RESTRICTED: refused
    out = tmp_path / "coverage.md"
    assert cli(["report", "--start", "2021-10-13", "--end", "2026-10-13", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "overall **INCOMPLETE**" in text and "| 2026-10 |" in text
