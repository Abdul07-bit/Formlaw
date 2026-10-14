# Legal source terms audit

> Superseded for current status by [DATA_SOURCES.md](DATA_SOURCES.md) (generated from the registry) and
> [CORPUS_COVERAGE.md](CORPUS_COVERAGE.md). Kept for its original 2026-10-08 licensing notes.

Machine-readable registry: [`legal-data/source-config/sources.json`](../legal-data/source-config/sources.json) (synced to the
`legal_sources` table by `python -m app.ingestion.discover_sources`). Only **APPROVED** sources can be ingested; the
pipeline refuses everything else with `STATUS: NOT INGESTED`.

Checked 2026-10-08. This is an engineering record of what was verified, not legal advice — have counsel confirm
before a commercial launch.

**Legal basis for judgments.** Copyright Act, 1957 s.52(1)(q)(iv): reproducing or publishing "any judgment or order of
a court, tribunal or other judicial authority" is not infringement, unless the court has prohibited it.
Statutes are different: s.52(1)(q)(ii) permits reproducing an Act only "together with any commentary thereon or any other
original matter". So statute text cannot simply be bulk-copied into a search index.

| Source | Content | Licence / terms | Decision |
|---|---|---|---|
| **Indian Supreme Court Judgments** — AWS Open Data Registry (Dattam Labs) · [registry](https://registry.opendata.aws/indian-supreme-court-judgments/) · [docs](https://github.com/vanga/indian-supreme-court-judgments) | SC judgments 1950–present, ~35K English; per-year metadata + PDF tar archives in a public S3 bucket | **CC-BY-4.0** declared on the registry; attribution required | **APPROVED** — ingested (sample; see below) |
| **Indian High Court Judgments** — AWS Open Data Registry (Dattam Labs) · [registry](https://registry.opendata.aws/indian-high-court-judgments/) | 25 High Courts, ~17.8M judgments, ~1.25 TiB | **CC-BY-4.0**; attribution required | **APPROVED** — no adapter yet (volume needs a server-side job); not ingested |
| **Constitution of India** — Legislative Department · [policy](https://legislative.gov.in/website-policies/) | Official English text (dated "as on" PDF editions) | "Material … may be reproduced free of charge **after taking proper permission by sending a mail to us**" | **REVIEW_REQUIRED** — not ingested; request permission, then import with `legal-data/constitution/import_constitution.py` |
| **India Code** — Legislative Department · [disclaimer](https://www.indiacode.nic.in/disclaimer.jsp) | Central/State Acts, rules, regulations (exact reproduction of adopted text) | No reuse licence published; owner's policy requires permission; s.52(1)(q)(ii) condition; automated requests refused (HTTP 403) | **REVIEW_REQUIRED** — not ingested (incl. BNS/BNSS/BSA) |
| Supreme Court website / e-SCR | Official judgments | Terms not verified first-hand; maintainers of the open dataset ask users not to scrape it | **REVIEW_REQUIRED** — unnecessary: same judgments available under CC-BY-4.0 |
| eCourts judgments portal | High Court judgments | CAPTCHA-gated; no licence | **REJECTED** — automated access restricted |
| Indian Kanoon | Aggregated judgments/statutes | Proprietary; paid API under its own terms | **REJECTED** — no licence held |
| Community Constitution datasets (e.g. Hugging Face) | Unofficial transcriptions | Uploader-declared licences; unverifiable chain to the official text | **REJECTED** — not authoritative |
| Operator-supplied files (`local_import`) | Anything the operator is licensed to load | Per-row provenance manifest | **APPROVED** channel |

Pre-existing content: the IPC/CrPC excerpts and two judgment summaries in `backend/app/agents/legal/corpus.py` came with
the original project. They stay in the system for the original agents but are labelled **"Source terms under review"**
in search results, pending the same India Code review.

## What is required to go further

1. **Constitution** — e-mail the Legislative Department for permission to reproduce the current "as on" edition
   (state the use: searchable reference text with attribution, no alteration). Then import it.
2. **Statutes (incl. BNS / BNSS / BSA)** — permission from the Legislative Department, or a licensed provider. Note
   the s.52(1)(q)(ii) commentary condition when publishing statute text.
3. **High Courts** — run the CC-BY-4.0 High Court dataset through a server-side job (≈1.25 TiB); write the per-court
   adapter (`STATE~COURT` partitions).
4. **Full Supreme Court decade** — `python -m app.ingestion.ingest --source aws_sc_judgments --years 2016-2026`
   (≈8,100 English judgments, ≈3.3 GB streamed; several hours of PDF parsing on a laptop).

Attribution shown with every judgment: *"Indian Supreme Court Judgments was accessed on DATE from
https://registry.opendata.aws/indian-supreme-court-judgments (CC BY 4.0, Dattam Labs). Original source: Supreme Court of India / eCourts."*
