"""
Sync the source registry into the database and print the terms audit.

    python -m app.ingestion.discover_sources            (from backend/)
    python -m app.ingestion.discover_sources --probe    also query approved open datasets for available years
"""
from __future__ import annotations

import argparse

import app  # noqa: F401

from ..db.session import session_factory
from . import registry


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync and audit legal sources")
    ap.add_argument("--probe", action="store_true", help="List available years for approved open datasets (network)")
    a = ap.parse_args()
    with session_factory()() as db:
        registry.sync(db)
        db.commit()
    for s in registry.load()["sources"]:
        print(f"\nSource:       {s['name']}\nURL:          {s['base_url']}\nTerms:        {s.get('terms_url')}\n"
              f"Content:      {s.get('coverage')}\nLicense/Terms:{' ' + s['license']}\nPermitted:    {s.get('allowed_usage')}\n"
              f"Restrictions: {s.get('restrictions')}\nDate checked: {s.get('last_checked')}\nDecision:     {s['status']} — {s.get('decision_reason')}")
    if a.probe:
        from .adapters import aws_sc

        years = aws_sc.available_years()
        print(f"\naws_sc_judgments: years {years[0]}–{years[-1]}")
        for y in years[-11:]:
            print("  ", aws_sc.year_stats(y))


if __name__ == "__main__":
    main()
