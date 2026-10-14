# Implementation roadmap

Status values: **done** (implemented and covered by passing tests) · **partial** · **not started**.
Nothing is marked done without a test that demonstrates it.

## Release gates

| Gate | Scope | Status |
|---|---|---|
| 1 Trust foundation | Auth, RBAC, matter + firm isolation, verification with roll-check evidence, connection gate, compliance role, consents, audit | **done** in software; MFA, malware scanning, retention not built (threat model) |
| 2 Real legal knowledge | Approved sources, ingestion CLI, measured coverage report, hybrid retrieval, verifiable citations | **partial** — tooling done; corpus INCOMPLETE (150 SC judgments in window, no High Courts) |
| 3 Client → advocate workflow | Intake, policy-gated connection, conflict check, messaging, workspace, agents, E2E-tested UI | **done** in software; connection features await a counsel-backed policy |

## Milestone 1 — trust foundation (2026-10-13) · done
ConnectionPolicy gate, consents, verification lifecycle + SUSPENDED + history, biometric check removed, migration 0007,
commit-before-response fix (D-001…D-007).

## Milestone 2 — completion pass (2026-10-13) · done

| Item | Evidence |
|---|---|
| COMPLIANCE role approves policies; admins only draft/revoke; staff accounts via `app.manage` | `security/test_connection_policy.py`, `e2e/flows.spec.ts` |
| Firm owners/admins lose implicit matter access; metadata-only register | `security/test_isolation.py` |
| Admin/compliance cannot bypass matter authorization | `test_isolation.py::test_platform_admin_and_compliance_cannot_bypass_matter_authorization` |
| Conflict check before disclosure (client-declared parties, firm-only search, silent decline) | `security/test_conflict_check.py`, E2E test 2 |
| Verification requires a recorded official Bar Council roll check | `api/test_product_flows.py::test_kyc_verification_flow` |
| Full suite on PostgreSQL 16 + pgvector via the real migrations | 179/179 passed; fixed: migration rebuilds on PG, broken tsvector search, fixed-dimension pgvector writes, VARCHAR overflow crashing case reviews |
| Registry: mandate statuses, expiring reviews, validator, all 8 official URLs; per-row licence for manual imports | `integration/test_legal_corpus.py` |
| Ingestion CLI (`list-sources`, `validate-sources`, `plan`, `run --approved-only --dry-run`, `report`, `status`) | `integration/test_coverage_report.py` |
| Measured coverage report + admin view | `docs/CORPUS_COVERAGE.md` (INCOMPLETE), E2E test 4 |
| Browser E2E suite (Chromium, real API) incl. phone width | `e2e/flows.spec.ts` — 5 passed |
| Docs: PRODUCT_SPEC, SECURITY_THREAT_MODEL, DATA_SOURCES, DATA_MODEL, API_CONTRACTS (last three generated), COUNSEL_REVIEW_BRIEF | `docs/` |
| Migrations 0008–0010 | tested on SQLite (`alembic check`) and PostgreSQL |

## Next milestones

| # | Milestone | Key deliverables | Blocked on |
|---|---|---|---|
| 3 | Counsel-backed connection policy | Draft a policy from the opinion; compliance approval | Counsel opinion |
| 4 | Full five-year corpus | Full-catalogue Supreme Court run for 2021-10-13 → 2026-10-13 on a server; High Court adapter (aws_hc_judgments); report until COMPLETE per source | Server + storage (multi-GB) |
| 5 | Production hardening | MFA, password reset + e-mail, malware scanning, object storage with signed URLs, Redis rate limits, retention/erasure jobs, CI with dependency scanning, pagination | — |
| 6 | Identity provider | Contracted KYC provider behind `KycProvider` | Provider contract |
| 7 | Model-mode evaluation | `scripts/evaluate.py --with-llm` baseline and thresholds | Model API budget |
