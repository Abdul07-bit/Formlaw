"""Migrations apply cleanly; legal-data ingestion and the constitutional importer enforce provenance."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "legal-data"))


def test_alembic_upgrade_and_check(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(tmp_path / 'm.db').as_posix()}"}
    run = lambda *args: subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT / "backend", env=env, capture_output=True, text=True)  # noqa: E731
    for args in (["upgrade", "head"], ["check"]):
        r = run(*args)
        assert r.returncode == 0, r.stderr
    # 0005 replaces the v1 schema; downgrading would silently lose data, so it refuses explicitly.
    r = run("downgrade", "0004")
    assert r.returncode != 0 and "cannot be downgraded" in r.stderr


def test_constitution_importer_rejects_placeholders_and_sections(seeded):
    from constitution.import_constitution import ConstitutionError, load

    base = {"source_name": "Test fixture (not real text)", "source_url": "https://example.org/c", "as_on_date": "2024-01-01"}
    with pytest.raises(ConstitutionError):
        load({**base, "parts": [{"number": "III", "articles": [{"number": "Section 21", "text": "x"}]}]}, replace=True)
    with pytest.raises(ConstitutionError):
        load({**base, "parts": [{"number": "III", "articles": [{"number": "21", "text": "<paste official text>"}]}]}, replace=True)
    n = load({**base, "parts": [{"number": "III", "title": "Fixture part", "tags": ["Fundamental Rights"],
                                 "articles": [{"number": "21", "title": "Fixture", "text": "FIXTURE TEXT ONLY",
                                               "clauses": [{"number": "1", "text": "FIXTURE CLAUSE"}]}]}]}, replace=True)
    assert n == 3  # part + article + clause


def test_research_serves_ingested_articles_as_articles(api, seeded):
    from constitution.import_constitution import load

    load({"source_name": "Test fixture (not real text)", "source_url": "https://example.org/c", "as_on_date": "2024-01-01",
          "parts": [{"number": "III", "articles": [{"number": "21", "title": "Fixture title", "text": "FIXTURE personal liberty text"}]}]},
         replace=True)
    s = api.register()
    r = api.c.post("/api/v1/research", json={"query": "Article 21 personal liberty", "kinds": ["constitution_article"]}, headers=s.h).json()
    assert r["results"][0]["reference"] == "Article 21" and r["results"][0]["kind"] == "constitution_article"
    assert "Section" not in r["results"][0]["reference"]
