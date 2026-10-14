"""
Adapter: Indian Supreme Court Judgments (AWS Open Data Registry, CC-BY-4.0, Dattam Labs).

Per year it reads metadata/tar/year=YYYY/metadata.tar (small) and streams data/tar/year=YYYY/english/*.tar
sequentially, pairing `<path>.json` with `<path>_EN.pdf`. Metadata is parsed verbatim from the official
e-SCR listing HTML captured in the dataset; nothing is inferred. Unknown fields stay None.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
import tarfile
from collections.abc import Iterator
from typing import Any

from ..core import IngestItem
from ..fetch import get_json, open_stream
from ..normalize import clean_meta

log = logging.getLogger("formlaw.ingestion.aws_sc")
BASE = "https://indian-supreme-court-judgments.s3.ap-south-1.amazonaws.com"
TAR_CAP = 1200 * 1024 * 1024
META_CAP = 50 * 1024 * 1024


def _field(raw: str, label: str) -> str | None:
    m = re.search(rf"{re.escape(label)}\s*:\s*</span>\s*<font[^>]*>(.*?)</font>", raw, re.S)
    return clean_meta(m.group(1)) if m else None


def parse_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Map one dataset JSON record to FormLaw metadata. Only values present in the record are used."""
    raw = record.get("raw_html") or ""
    raw = re.sub(r"<select.*?</select>", "", raw, flags=re.S)
    raw = re.sub(r"<div class='modal.*?</div></div></div></div>", "", raw, flags=re.S)  # portal disclaimer modal

    title = None
    m = re.search(r'aria-label="([^"]+?)\s*pdf"', raw)
    if m:
        title = clean_meta(m.group(1))
    if not title:
        m = re.search(r"<strong>(.*?)</strong>\s*-", raw, re.S)
        title = clean_meta(m.group(1)) if m else None
    parties = None
    if title and re.search(r"\s+versus\s+", title, re.I):
        parties = [p.strip() for p in re.split(r"\s+versus\s+", title, maxsplit=1, flags=re.I)]

    scr = re.search(r"<span class='escrText'>(.*?)</span>", raw)
    nc = re.search(r"<span class='ncDisplay'>(.*?)</span>", raw)
    cnr = re.search(r"id='cnr'\s+value=['\"]?([A-Z0-9]+)", raw)
    coram = re.search(r"Coram\s*:\s*(.*?)</strong>", raw, re.S)
    judges = None
    if coram:
        cleaned = re.sub(r"<sup.*?</sup>", "", coram.group(1), flags=re.S)
        judges = [j for j in (clean_meta(x, 120) for x in cleaned.split(",")) if j]
    issue = re.search(r"Issue for Consideration(.*?)(?:<br>\s*<strong class='caseDetailsTD'|$)", raw, re.S)
    case_no = _field(raw, "Case No")
    case_type = None
    if case_no:
        ct = re.match(r"([A-Z][A-Z .()/&-]+?)\s+No\.?", case_no)
        case_type = clean_meta(ct.group(1), 80) if ct else None
    neutral = clean_meta(nc.group(1), 60) if nc else None
    if not neutral and record.get("nc_display"):
        neutral = clean_meta(re.sub(r"^(\d{4})INSC(\d+)$", r"\1 INSC \2", record["nc_display"]), 60)

    return {
        "title": title,
        "parties": parties,
        "court": "Supreme Court of India",
        "jurisdiction": "India",
        "citation": clean_meta(scr.group(1), 60) if scr else None,
        "neutral_citation": neutral,
        "cnr": cnr.group(1)[:40] if cnr else None,
        "judges": judges,
        "decision_date": _field(raw, "Decision Date"),
        "case_number": case_no,
        "case_type": case_type,
        "disposal": _field(raw, "Disposal Nature"),
        "subject": clean_meta(html_lib.unescape(issue.group(1)), 600) if issue else None,
        "source_url": "https://registry.opendata.aws/indian-supreme-court-judgments/",
        "language": "en",
    }


def _parts(year: int, kind: str) -> list[str]:
    folder = f"data/tar/year={year}/english" if kind == "english" else f"metadata/tar/year={year}"
    idx = get_json(f"{BASE}/{folder}/{'english' if kind == 'english' else 'metadata'}.index.json", BASE)
    return [f"{BASE}/{folder}/{p['name']}" for p in idx.get("parts", [])]


def available_years() -> list[int]:
    import httpx  # listing the bucket prefixes (public, read-only)

    r = httpx.get(f"{BASE}/?list-type=2&prefix=metadata/tar/&delimiter=/", timeout=60)
    r.raise_for_status()
    return sorted(int(y) for y in re.findall(r"metadata/tar/year=(\d{4})/", r.text))


def year_stats(year: int) -> dict[str, Any]:
    idx = get_json(f"{BASE}/data/tar/year={year}/english/english.index.json", BASE)
    return {"year": year, "english_judgments": idx.get("file_count"), "size": idx.get("total_size_human")}


def iter_items(year: int, *, limit: int = 0) -> Iterator[IngestItem]:
    """Yield judgments for one year, streaming the archives sequentially. limit=0 means the whole year."""
    meta: dict[str, dict[str, Any]] = {}
    for url in _parts(year, "metadata"):
        with open_stream(url, BASE, cap=META_CAP) as f:
            tar = tarfile.open(fileobj=f, mode="r|")
            for m in tar:
                if not (m.isfile() and m.name.endswith(".json") and m.size < 2_000_000):
                    continue
                fh = tar.extractfile(m)
                try:
                    meta[m.name.rsplit("/", 1)[-1][:-5]] = json.loads(fh.read()) if fh else {}
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log.warning("skipping unreadable metadata %s", m.name)
    emitted = 0
    for url in _parts(year, "english"):
        with open_stream(url, BASE, cap=TAR_CAP) as f:
            tar = tarfile.open(fileobj=f, mode="r|")
            for m in tar:
                name = m.name.rsplit("/", 1)[-1]
                # Member names are never used as filesystem paths (no extraction to disk).
                if not (m.isfile() and name.endswith("_EN.pdf")):
                    continue
                key = name[:-7]
                fh = tar.extractfile(m)
                data = fh.read() if fh else b""
                yield IngestItem(
                    external_id=key, kind="judgment", file_kind="pdf", data=data,
                    document_url=f"{BASE}/data/pdf/year={year}/english/{name}",
                    meta=parse_metadata(meta.get(key, {})), expected_year=year,
                )
                emitted += 1
                if limit and emitted >= limit:
                    return
