"""
Adapter: operator-supplied licensed files described by a provenance manifest (JSON lines).

    {"file": "sc/2021_123.pdf", "kind": "judgment", "title": "...", "court": "...", "case_number": "...",
     "decision_date": "2021-03-04", "citation": null, "neutral_citation": null, "jurisdiction": "India",
     "subject": null, "parties": null, "act": null, "section_or_article": null,
     "source_url": "https://...original document...", "license": "...", "language": "en"}

Missing optional metadata stays null; it is never guessed.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

from ...models import AUTHORITY_KINDS
from ..core import IngestItem

# Every row carries its own licence/permission: this channel has no source-level terms, so a row without one is refused.
REQUIRED = ("file", "kind", "title", "source_url", "license")
OPTIONAL = ("court", "case_number", "decision_date", "citation", "neutral_citation", "parties", "subject", "jurisdiction",
            "act", "section_or_article", "language")
FILE_KINDS = {".pdf": "pdf", ".docx": "docx", ".txt": "text", ".md": "text"}


class ManifestError(ValueError):
    pass


def validate_row(raw: dict) -> dict:
    missing = [k for k in REQUIRED if not raw.get(k)]
    if missing:
        raise ManifestError(f"missing required provenance: {', '.join(missing)}")
    if raw["kind"] not in AUTHORITY_KINDS:
        raise ManifestError(f"unknown kind {raw['kind']}")
    url = urlparse(str(raw["source_url"]))
    if url.scheme != "https" or not url.hostname:
        raise ManifestError("source_url must be an https URL to the original document")
    row = {k: raw[k] for k in REQUIRED}
    for k in OPTIONAL:
        v = raw.get(k)
        row[k] = v if v not in ("", [], {}, "unknown", "n/a", "NA") else None
    if row["kind"] == "constitution_article" and row["section_or_article"] and str(row["section_or_article"]).lower().startswith("section"):
        raise ManifestError("Constitutional provisions are Articles, not sections")
    if row["parties"] is not None and not isinstance(row["parties"], list):
        raise ManifestError("parties must be a list or null")
    return row


def iter_items(manifest: Path, errors: list[str]) -> Iterator[IngestItem]:
    base = manifest.resolve().parent
    for n, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = validate_row(json.loads(line))
            path = (base / row["file"]).resolve()
            if base not in path.parents:
                raise ManifestError("file path escapes the manifest folder")
            kind = FILE_KINDS.get(path.suffix.lower())
            if not kind:
                raise ManifestError(f"unsupported file type {path.suffix}")
            yield IngestItem(external_id=f"{manifest.name}:{row['file']}", kind=row["kind"], file_kind=kind, data=path.read_bytes(),
                             document_url=row["source_url"], meta=row)
        except (ManifestError, OSError, json.JSONDecodeError) as e:
            errors.append(f"line {n}: {e}")
