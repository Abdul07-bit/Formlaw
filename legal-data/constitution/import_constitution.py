"""
Import the Constitution of India into the constitutional knowledge layer.

    python ../legal-data/constitution/import_constitution.py --file constitution.json

The input is prepared by the operator FROM THE OFFICIAL PUBLISHED TEXT (Legislative Department) and
must state its source and "as on" date. This tool does not contain or generate constitutional text.

Input shape (see constitution.schema.json):
{
  "source_name": "Constitution of India (as on <date>), Legislative Department",
  "source_url": "https://...",
  "as_on_date": "YYYY-MM-DD",
  "preamble": "official Preamble text",
  "parts": [{"number": "III", "title": "Fundamental Rights", "tags": ["Fundamental Rights"],
             "chapters": [], "articles": [{"number": "21", "title": "...", "text": "...", "clauses": [{"number": "1", "text": "..."}]}]}],
  "schedules": [{"number": "Seventh", "title": "...", "text": "..."}],
  "amendments": [{"number": "42nd", "title": "...", "text": "...", "year": 1976}]
}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import app  # noqa: E402,F401
from sqlalchemy import delete  # noqa: E402

from app.db.session import session_factory  # noqa: E402
from app.models import ConstitutionProvision  # noqa: E402

ARTICLE_NO = re.compile(r"^\d{1,3}[A-Z]{0,3}$")      # 21, 21A, 243ZH
PART_NO = re.compile(r"^[IVXL]+[A-Z]?$")              # III, IVA, IXB
PLACEHOLDER = re.compile(r"lorem ipsum|<paste|todo|tbd|placeholder", re.I)


class ConstitutionError(ValueError):
    pass


def _hash(text: str | None) -> str | None:
    return hashlib.sha256(text.encode()).hexdigest() if text else None


def _text(v: Any, where: str) -> str | None:
    if v is None:
        return None
    if not isinstance(v, str) or PLACEHOLDER.search(v):
        raise ConstitutionError(f"{where}: text must be the official text (placeholders are rejected)")
    return v.strip()


def validate(doc: dict[str, Any]) -> None:
    for k in ("source_name", "source_url", "as_on_date", "parts"):
        if not doc.get(k):
            raise ConstitutionError(f"missing {k}")
    if not str(doc["source_url"]).startswith("https://"):
        raise ConstitutionError("source_url must be https")
    date.fromisoformat(doc["as_on_date"])
    for p in doc["parts"]:
        if not PART_NO.match(str(p.get("number", ""))):
            raise ConstitutionError(f"invalid Part number {p.get('number')!r}")
        for a in p.get("articles", []) + [a for c in p.get("chapters", []) for a in c.get("articles", [])]:
            if not ARTICLE_NO.match(str(a.get("number", ""))):
                raise ConstitutionError(f"invalid Article number {a.get('number')!r} (Articles are numbered like 21 or 21A)")


def load(doc: dict[str, Any], *, replace: bool) -> int:
    validate(doc)
    meta = {"source_name": doc["source_name"], "source_url": doc["source_url"], "as_on_date": date.fromisoformat(doc["as_on_date"])}
    n = 0
    with session_factory()() as db:
        if replace:
            db.execute(delete(ConstitutionProvision))

        def add(kind: str, number: str, parent: str | None, *, part: str | None = None, title: str | None = None,
                text: str | None = None, tags: list[str] | None = None, amendment: str | None = None) -> str:
            nonlocal n
            row = ConstitutionProvision(kind=kind, number=number, parent_id=parent, part=part, title=title, text=text,
                                        tags=tags or [], amendment_ref=amendment, content_hash=_hash(text), **meta)
            db.add(row)
            db.flush()
            n += 1
            return row.id

        def add_articles(articles: list[dict[str, Any]], parent: str, part: str, tags: list[str]) -> None:
            for a in articles:
                where = f"Article {a['number']}"
                aid = add("article", str(a["number"]), parent, part=part, title=a.get("title"), text=_text(a.get("text"), where), tags=tags)
                for c in a.get("clauses", []):
                    add("clause", f"{a['number']}({c['number']})", aid, part=part, text=_text(c.get("text"), f"{where}({c['number']})"), tags=tags)

        if doc.get("preamble"):
            add("preamble", "Preamble", None, title="Preamble", text=_text(doc["preamble"], "Preamble"))
        for p in doc["parts"]:
            tags = p.get("tags", [])
            pid = add("part", str(p["number"]), None, part=str(p["number"]), title=p.get("title"), tags=tags)
            add_articles(p.get("articles", []), pid, str(p["number"]), tags)
            for c in p.get("chapters", []):
                cid = add("chapter", str(c["number"]), pid, part=str(p["number"]), title=c.get("title"), tags=tags)
                add_articles(c.get("articles", []), cid, str(p["number"]), tags)
        for s in doc.get("schedules", []):
            add("schedule", str(s["number"]), None, title=s.get("title"), text=_text(s.get("text"), f"Schedule {s['number']}"))
        for a in doc.get("amendments", []):
            add("amendment", str(a["number"]), None, title=a.get("title"), text=_text(a.get("text"), f"Amendment {a['number']}"),
                amendment=str(a.get("year") or "") or None)
        db.commit()
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Import the Constitution of India from an operator-prepared official-text file")
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--replace", action="store_true", help="Replace the existing constitutional layer")
    a = ap.parse_args()
    print(f"Imported {load(json.loads(a.file.read_text(encoding='utf-8')), replace=a.replace)} provisions.")


if __name__ == "__main__":
    main()
