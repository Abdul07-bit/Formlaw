# Legal data

FormLaw never fabricates legal text, citations or metadata, and only ingests sources whose terms permit it.
Terms audit: **[docs/LEGAL_SOURCES.md](../docs/LEGAL_SOURCES.md)**. Registry: `source-config/sources.json`.

```
APPROVED SOURCE → DOWNLOAD (SSRF-safe, streamed) → LICENSE / TERMS CHECK → FILE VALIDATION → HASH → METADATA EXTRACTION
  → TEXT EXTRACTION → NORMALIZATION → DEDUPLICATION → INJECTION SCAN → QUALITY CHECK (else QUARANTINE)
  → CHUNKING (page-aware) → EMBEDDING → INDEX (FTS5 / tsvector + numpy / pgvector)
```

## Commands (run from `backend/`)

```bash
python -m app.ingestion.discover_sources [--probe]      # sync registry → DB, print terms audit, list available years
python -m app.ingestion.ingest --source aws_sc_judgments --years 2016-2026 --limit-per-year 30   # sample
python -m app.ingestion.ingest --source aws_sc_judgments --years 2016-2026                       # full decade (~8.1K judgments)
python -m app.ingestion.ingest --source local_import --manifest /path/manifest.jsonl              # licensed local files
python -m app.ingestion.validate [--fix] [--release <doc-id>]                                     # re-check; quarantine; human release
python -m app.ingestion.index                                                                     # embeddings (needs GEMINI_API_KEY)
python -m app.ingestion.status                                                                    # per-source counts
```

Any source that is not APPROVED is refused:
```
SOURCE
india_code
STATUS: NOT INGESTED
REASON: REVIEW_REQUIRED — Usage rights for bulk ingestion unclear/restricted …
```

## Code

| Location | Purpose |
|---|---|
| `backend/app/ingestion/registry.py` | Registry sync + terms gate (`require_approved`) |
| `backend/app/ingestion/fetch.py` | https only, registered host only, public IPs only, no redirects, size caps, streamed |
| `backend/app/ingestion/core.py` | Shared stages, quarantine, dedupe & duplicate-poisoning defence |
| `backend/app/ingestion/adapters/aws_sc.py` | Supreme Court CC-BY-4.0 dataset (metadata parsed verbatim from the e-SCR listing) |
| `backend/app/ingestion/adapters/local_manifest.py` | Operator-licensed files with a provenance manifest |
| `backend/app/retrieval/legal_corpus.py` | Keyword + vector + metadata filters + rerank, evidence with provenance |
| `legal-data/constitution/import_constitution.py` | Preamble / Part / Chapter / Article / Clause / Schedule / Amendment importer (needs a permitted source) |

## Local manifest format

```json
{"file": "sc/2021_123.pdf", "kind": "judgment", "title": "…", "court": "…", "case_number": "…", "decision_date": "2021-03-04",
 "citation": null, "neutral_citation": null, "jurisdiction": "India", "subject": null, "parties": null,
 "act": null, "section_or_article": null, "source_url": "https://…original…", "license": "…", "language": "en"}
```
Unknown metadata stays `null`. Constitutional provisions are Articles, never "sections".

## Constitution

Once the Legislative Department grants permission, prepare a JSON file from the official edition (record its
"as on" date) as documented in `constitution/import_constitution.py`, then from `backend/`:
```bash
python ../legal-data/constitution/import_constitution.py --file constitution.json --replace
```
Until then, Article questions return *"I could not find sufficient verified source material…"* with the reason.
