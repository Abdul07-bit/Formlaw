# FormLaw — legal services and case collaboration for India

Clients describe a legal problem and, where a compliance-reviewed process permits it, connect with a verified advocate.
Advocates run matters in a secure workspace where agentic AI researches, analyses evidence and drafts — with a citation
behind every statement. **Evidence is the source of truth, not the model. The backend enforces security. The advocate decides.**

Product: [PRODUCT_SPEC](docs/PRODUCT_SPEC.md) · Architecture: [ARCHITECTURE](docs/ARCHITECTURE.md) ·
Security: [SECURITY_THREAT_MODEL](docs/SECURITY_THREAT_MODEL.md) · Data: [DATA_MODEL](docs/DATA_MODEL.md),
[DATA_SOURCES](docs/DATA_SOURCES.md), [CORPUS_COVERAGE](docs/CORPUS_COVERAGE.md) · API: [API_CONTRACTS](docs/API_CONTRACTS.md) ·
Decisions: [DECISIONS](docs/DECISIONS.md) · Plan: [IMPLEMENTATION_ROADMAP](docs/IMPLEMENTATION_ROADMAP.md) ·
For counsel: [COUNSEL_REVIEW_BRIEF](docs/COUNSEL_REVIEW_BRIEF.md)

> **Before any real use:** (1) rotate the keys that were in the shared zip's `.env` (Gemini key, `JWT_SECRET`,
> `FILE_ENCRYPTION_KEY`); (2) get the counsel opinion described in COUNSEL_REVIEW_BRIEF.md — advocate discovery stays off
> until a compliance reviewer approves a policy citing it; (3) close the items under *Not yet mitigated* in the threat model.

## Run it

Requirements: Node 20+, Python 3.11+ (Docker only for PostgreSQL).

```bash
npm install
python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt   # Windows: backend\.venv\Scripts\pip
cp .env.example .env            # LLM_PROVIDER=none runs every agent without a model
npm run db:migrate              # SQLite at backend/formlaw.db, or DATABASE_URL (migrations 0001–0011)
npm run db:seed                 # SYNTHETIC demo data (DEMO_MODE only)
npm run api                     # http://localhost:8000  (OpenAPI at /api/docs)
npm run dev                     # http://localhost:5173
```

Demo accounts (synthetic, password `FormLaw-Demo-2026`, or the persona buttons on the sign-in page):
`lawyer@`, `client@`, `admin@`, `compliance@demo.formlaw.in`.

## Tests

| Suite | Command | Result (2026-10-13) |
|---|---|---|
| Backend on SQLite | `npm run test:api` | 183 passed |
| Backend on PostgreSQL 16 + pgvector (schema built by the real migrations) | `FORMLAW_TEST_DATABASE_URL=postgresql+psycopg://user:pw@host:port/db npm run test:api` | 183 passed |
| Browser end to end (Chromium, real API, fresh seeded database) | `npm run test:e2e` (first time: `npx playwright install chromium`) | 6 passed |
| Types / production build | `npm run typecheck` · `npm run build` | pass |

A throwaway PostgreSQL for the suite: `docker run -d --name formlaw-pg-test -e POSTGRES_DB=formlaw_test -e POSTGRES_USER=formlaw -e POSTGRES_PASSWORD=<random> -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16`.

## Operator commands (from `backend/`)

```bash
python -m app.manage create-staff --role compliance --email … --name …   # admin / compliance accounts (never self-registered)
python -m app.manage disable-user --email …
python -m app.ingestion list-sources | validate-sources
python -m app.ingestion plan   --start 2021-10-13 --end 2026-10-13
python -m app.ingestion run    --source aws_sc_judgments --approved-only --dry-run
python -m app.ingestion report --start 2021-10-13 --end 2026-10-13 --out ../docs/CORPUS_COVERAGE.md
python ../scripts/generate_docs.py                                      # regenerate API / data model / sources docs
```

## What works today

* **Trust foundation** — organization + matter isolation (firm owners get no implicit matter access; a metadata-only
  register instead), default-deny policy engine, human approval for every consequential action, audit trail, commits
  before responses.
* **Advocate verification** — documents → provider checks (DEMO provider, clearly labelled) → admin records an official
  Bar Council roll check → VERIFIED for 365 days; expiry, suspension, reinstatement, full history; no biometrics.
* **Compliance-controlled connection** — directory, suggestions and client requests are OFF until a compliance reviewer
  approves a ConnectionPolicy citing counsel; disclosures shown and consent recorded verbatim; no ranking or paid placement.
* **Conflict check** before an advocate sees a matter; a conflict decline reveals nothing to the client.
* **Matter workspace** — agent runtime with 12 agents, verification gate, contradictions, missing information, drafting,
  research over the approved corpus, client portal and messaging.
* **Legal data** — licence-gated registry (including all official URLs from the brief), ingestion CLI, measured coverage report.

## Known limitations (honest status)

* **Corpus coverage is INCOMPLETE**: 150 Supreme Court judgments fall in the 2021-10-13 → 2026-10-13 window (a sample of
  ~30/year from a CC-BY-4.0 mirror); 46 of 61 months are empty; no High Court data; statutes not loaded (access restricted).
  A full Supreme Court run for the window is a multi-GB download — run it on a server, then re-run `report`.
* **Not run with a real AI model** in this rebuild (deterministic mode + scripted-provider tests). Measure model quality
  with `python scripts/evaluate.py --with-llm` (billed) before relying on it.
* **No automated identity provider** — verification relies on documents plus the reviewer's manual roll check.
* Not built: OCR, MFA, password reset, e-mail delivery, object storage with signed URLs, retention/erasure jobs, malware
  scanning, CI pipeline, pagination. See SECURITY_THREAT_MODEL.md → *Not yet mitigated*.
* Legal positions (BCI advertising rules, DPDP Act) are **not** reviewed by counsel; nothing here is a compliance certification.

## Operations

* **Migrations:** `npm run db:migrate` (Alembic). Both suites above build their schema by applying every migration
  (SQLite additionally runs `alembic check` for model drift; downgrades are tested on SQLite only); 0005 refuses to downgrade (it replaced the v1 schema); 0008 refuses to downgrade while compliance accounts exist.
  Strategy: back up → migrate → smoke test → keep the backup until verified. Roll back by restoring the backup, not by
  downgrading production data.
* **Backups (PostgreSQL):** `pg_dump -Fc -d $DATABASE_URL > formlaw-$(date +%F).dump`; restore with
  `pg_restore -c -d $DATABASE_URL formlaw-….dump`. Back up `STORAGE_DIR` together with the database — files are
  encrypted with `FILE_ENCRYPTION_KEY`, so keep that key in a secret manager, separately from the backups. Test a restore regularly.
* **Secret rotation:** `JWT_SECRET` — change and restart (all sessions end). `GEMINI_API_KEY`/`OPENAI_API_KEY`/
  `ANTHROPIC_API_KEY` — rotate at the provider, update the secret, restart. `FILE_ENCRYPTION_KEY` — rotating it makes
  existing files unreadable; re-encryption tooling is not built yet.
* **Production guards:** the API refuses to start without `JWT_SECRET`, refuses `DEMO_MODE` in production, disables
  `/api/docs`, and sends HSTS. Health: `GET /api/v1/health`; admin view: `GET /api/v1/admin/health`.
* **Incidents:** suspend affected advocates (`/admin/verifications/{id}/suspend`), revoke the connection policy
  (instant switch-off), disable accounts (`app.manage disable-user`), rotate secrets, and review `audit_logs` and
  `security_events` (both carry request ids).

## Layout

```
backend/app/        api/v1 · agents (runtime, orchestrator, 11 agents) · ingestion (registry, adapters, coverage, CLI)
                    policies (catalog, engine, connection) · services · security · repositories · models · llm · retrieval
backend/tests/      unit · api · security · agents · retrieval · integration · evaluation
database/           migrations (Alembic 0001–0011) · seeds (synthetic demo)
src/                React: advocate workbench, client portal, admin, compliance
e2e/                Playwright browser tests      scripts/  e2e server, docs generator, evaluation
legacy/             superseded v1 code kept for reference — safe to delete
```

FormLaw is a technology platform. It does not provide legal advice, rank advocates, or predict outcomes.
