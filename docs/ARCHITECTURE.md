# FormLaw — Architecture (v2: lawyer-first agentic workbench)

> FormLaw is an agentic legal workbench for lawyers. Evidence is the source of truth; the LLM is not.
> The backend enforces security; the lawyer makes the decisions.

```
GOAL → UNDERSTAND → PLAN → DELEGATE → RETRIEVE → REASON → ACT → OBSERVE → VERIFY → DETECT FAILURE → ADAPT → REPLAN → COMPLETE
```

Contents: [A. Repository audit](#a-repository-audit) · [B. Previous architecture](#b-previous-architecture) ·
[C. Keep / refactor / replace / delete](#c-keep--refactor--replace--delete) · [D. Target architecture](#d-target-architecture) ·
[E. Database](#e-database) · [F. Agents](#f-agents) · [G. API](#g-api) · [H. RAG](#h-rag) · [I. Security](#i-security) ·
[J. Lawyer workbench UX](#j-lawyer-workbench-ux) · [K. Client portal](#k-client-portal) · [L. Roadmap & status](#l-roadmap--status) ·
[M. Agent boundaries](#m-agent-dependencies--integration-boundaries)

---

## A. Repository audit

Inspected 2026-10-09. Git history has one real commit; almost everything below was uncommitted.

| Area | What was there | Quality |
|---|---|---|
| `backend/` FastAPI | 28 tables, JWT + rotating refresh, RBAC, upload validation, injection scanner, ToolGateway with limits, approvals, audit, KYC demo provider, matching | Security primitives good and tested (171 tests passing) |
| `backend/app/agents/engine/` | "Orchestrator" = one linear function; regex fact extraction tuned to one FIR format; keyword-count classifier | **Not agentic.** Adaptation steps were log lines, not behaviour |
| `backend/app/agents/legal/` + `legal_bridge.py` | Older 6-agent CLI system loaded via `sys.path` injection, temp files and a global lock | Duplicate; unsafe integration pattern |
| `formlaw/` | A third, separate package: LLM review agent with good verbatim-quote validators | Good ideas, wrong place (no DB, no auth) |
| `backend/app/ingestion/`, `retrieval/legal_corpus.py` | Licence-gated legal corpus ingestion, SSRF-safe fetch, quarantine, FTS5 + vectors | Good. Real data: 312 Supreme Court judgments, 13,770 chunks (CC-BY-4.0) |
| Case documents | `extracted_text` in one column, re-chunked per request, no case embeddings | Needs a real per-case index |
| Product model | Clients own cases; lawyers see a brief only via a client connection | **Inverted** relative to a lawyer-first product |
| `src/` React | Marketing landing (three.js, framer-motion), client dashboard, tabbed case page | Not a workbench |
| Root `app.js`, `check.js`, `styles.css`, `privacy.html`, `terms.html`, `favicon.svg` | Leftover static site | Dead code |
| Lawyer model | `rating`, `reviews`, `cases_handled` columns | Unverifiable performance data — removed |

## B. Previous architecture

```
React (client-first) ─► FastAPI ─► analyse() linear pipeline ─► regex agents ─► SQLite
                                  └► legal_bridge ─► sys.path-loaded CLI agents (temp files, global lock)
```

One request ran every agent in a fixed order regardless of the question. Chat was a separate code path that
matched stored contradictions by keyword. There was no plan, no observation, and no replanning.

## C. Keep / refactor / replace / delete

| Decision | Items |
|---|---|
| **Reuse** | `core/` (config, errors, redacting logging) · `db/` · `security/` (passwords, tokens, files, rate limit) · `ingestion/` (legal corpus) · `retrieval/legal_corpus.py` · `services/storage.py` (AES-GCM) · `services/audit.py` · `kyc/provider.py` · legal corpus tables and data |
| **Refactor** | `security/injection.py` (more patterns, span-level flags) · `security/deps.py` (org + case membership) · `policy/risk.py` → `policies/` (principal-aware policy engine) · LLM provider (model routing, Anthropic provider, versioned prompts) · verification core · matching (intake-driven) · lawyer model (verification states, no performance data) |
| **Replace** | Agent engine → state-machine runtime + 12 agent modules · case/document/review tables → lawyer-first case workspace schema · case APIs → workbench APIs · frontend → ChatGPT-style workbench + simple client portal |
| **Delete** | `agents/engine/`, `agents/legal/`, `legal_bridge.py`, `formlaw/` (validator ideas folded in), old case services/serializers, root static-site files, three.js/framer-motion, old seeds |
| **New** | Organizations + memberships, case members, document chunks index, agent runs/steps/tool calls, timeline, drafts, tasks, findings, memory, intake, threads/messages, SSE run events |

---

## D. Target architecture

```
                                 ┌─────────────────────────── src/ (React + Vite + TanStack Query + Zod) ────────────────┐
                                 │  Lawyer workbench (chat-first)        Client portal (guided)         Admin            │
                                 └──────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                                │ /api/v1  (Bearer JWT, SSE for run events)
┌───────────────────────────────────────────────────────────────▼─────────────────────────────────────────────────────────┐
│ backend/app                                                                                                              │
│  api/v1 ──► security (authN, org/case membership) ──► policies (risk, RBAC, approval) ──► services ──► repositories ──► DB│
│                                                              │                                                           │
│                                    agents/runtime  (Orchestrator state machine, budgets, events)                         │
│        CLASSIFY → PLAN → [EXECUTE → OBSERVE → ADAPT]* → VERIFY GATE → QUALITY CHECK → (REPLAN) → FINALIZE                │
│                                                              │                                                           │
│                       ToolGateway (per-agent allow-list, risk, approval, retries, audit, tool_calls)                     │
│        ┌───────────┬───────────┬────────────┬──────────────┬─────────────┬──────────┬──────────┬──────────┐              │
│     retrieval  case_analysis contract   contradiction  missing_info  research  drafting  verification  security          │
│        │                                                                │                                                │
│   retrieval/ (case hybrid index)                              retrieval/legal_corpus (approved sources only)             │
│   llm/ (LLMProvider + router: fast / strong / embed; versioned prompts; trust-separated messages)                        │
│   memory/ (case, episodic, semantic, security — scoped, provenance, expiry)   observability/ (runs, steps, tool calls)   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        PostgreSQL + pgvector + tsvector (production)  ·  SQLite + FTS5 + numpy (development/tests)  ·  encrypted object storage
```

**Principles enforced in code, not prompts**

1. Every LLM-produced item must cite a `chunk_id` and a quote; the quote must appear verbatim in that chunk or the item is dropped.
2. The model that wrote a claim never grades it. Verification is deterministic first; an LLM judge may only downgrade.
3. Unsupported claims are never silently returned. They are labelled and separated from findings.
4. Documents are data. Flagged spans are excluded from model context but stay available as evidence.
5. Agents reach tools only through the ToolGateway. No agent has network, filesystem, e-mail or delete tools.
6. HIGH-risk actions cannot run inside an agent run; they become approval requests for the lawyer.
7. Every query is scoped by `organization_id` **and** `case_id`.
8. The platform works without any LLM (deterministic, extractive paths). Models improve quality, never correctness guarantees.

### Repository layout

```
src/ (repo root)          React app (workbench, client portal, admin) — kept at the root; see README
backend/app/
  api/v1/                 routers: auth, cases, documents, chat, runs, knowledge, drafts, research, lawyers, intake, portal, admin
  agents/
    base.py               AgentSpec + Agent protocol + StepResult
    registry.py           agent catalogue
    runtime/              state, plan, budgets, gateway, tools, observers, engine, events, executor
    orchestrator/         intent classifier, planner, composer
    case_analysis/ contract_review/ research/ retrieval/ verification/ contradiction/
    missing_information/ drafting/ security/ matching/ intake/
  domain/                 enums and value types shared across layers
  llm/                    providers, router, prompt registry, prompts/*.md (versioned)
  retrieval/              case index (hybrid), legal corpus search, reranker, query expansion
  ingestion/              case documents pipeline + legal corpus pipeline
  memory/                 memory service
  observability/          run/step/tool-call recording, metrics
  policies/               action catalogue + policy engine
  security/               authN, deps, files, injection, rate limit, tokens
  services/               use-case orchestration for routers
  repositories/           scoped data access (org + case filters live here)
  models/ schemas/        SQLAlchemy + Pydantic v2
backend/tests/            unit, integration, security, agents, retrieval, evaluation
database/migrations/      Alembic
legal-data/               source registry, corpus tooling
docs/                     this file, PRODUCT_SPEC, SECURITY_THREAT_MODEL, DATA_SOURCES, DATA_MODEL, API_CONTRACTS, DECISIONS, ROADMAP
```

---

## E. Database

Tenant = `organizations`. Every case-scoped row carries `organization_id` and `case_id`.

| Group | Table | Key columns |
|---|---|---|
| Identity | `organizations` | type: individual · law_firm · legal_department · platform |
| | `users` | role (account type): lawyer · client · admin; status; lockout |
| | `memberships` | (organization_id, user_id) unique; role: owner · admin · member |
| | `refresh_tokens` | hash only, family rotation |
| Lawyers | `lawyers` | profile fields; `verification_status` PENDING/UNDER_REVIEW/VERIFIED/REJECTED/EXPIRED (+ NOT_STARTED); server-written only |
| | `lawyer_verifications` | one check per row (government_id, bar_registration, qualification, face_match, judicial_status), provider result, reviewer, expiry |
| | `lawyer_practice_areas` | (lawyer_id, area) + verified flag |
| Cases | `cases` | organization_id, reference, title, matter_type, status, jurisdiction, court, client_user_id, created_by |
| | `case_members` | (case_id, user_id) unique; role: lead · member · viewer · client |
| | `documents` | case_id, organization_id, filename, content_hash, mime_type, size, source, status, doc_type, pages, metadata, security_flags, storage_key |
| | `document_chunks` | document_id, case_id, organization_id, ordinal, page, paragraph, section, text, content_hash, char_start/end, security_flags; FTS (FTS5 / tsvector) |
| | `chunk_embeddings` | chunk_id, model, dim, vector (JSON) / vector_pg (pgvector) |
| Knowledge (lawyer-reviewable) | `evidence` | case-level evidence items referenced by claims (chunk_id, quote, document, page, paragraph, hash) |
| | `claims` | text, kind (fact/allegation/admission/inference/finding), verification_status, confidence, reason, review_status (unreviewed/accepted/rejected), run_id |
| | `citations` | claim_id → evidence_id or legal_authority_id, quote |
| | `contradictions` | topic, statement_a/b, evidence_a/b, nature, confidence, provenance assessment, resolution status |
| | `missing_information` | title, why_needed, basis (evidence that references it), importance, status |
| | `timeline_events` | event_date (ISO or raw), date_text, description, evidence_id, status (consistent/conflicted) |
| | `legal_authorities` | snapshot of a corpus hit (legal_document_id, chunk_id, citation, court, date, source_url, licence, hash) per case |
| | `drafts` | kind, title, sections JSON (facts/authorities/inferences/recommendations), status (draft/approved), version |
| | `tasks` | title, status, due, assignee, source (lawyer/agent suggestion) |
| | `saved_findings` | user's pinned answer/claim with note |
| Conversation | `chat_threads`, `chat_messages` | per case; assistant messages hold the structured result JSON + run_id |
| Agent runtime | `agent_runs` | task id, case, org, user, thread, intent, goal, status, plan JSON, result JSON, counters, error, started/finished |
| | `agent_steps` | run_id, seq, agent, action, status, summary (reasoning summary, not chain-of-thought), latency, input/output digests |
| | `tool_calls` | run_id, step, agent, tool, risk, status, latency, tokens, error |
| Governance | `approvals` | action, risk, payload, summary, status, requester, decider |
| | `audit_logs`, `security_events` | as before + organization_id / case_id |
| | `memory_items` | scope (case/episodic/semantic/security), org, case, key, content, provenance, validated, expires_at |
| | `notifications` | user, kind, payload, read_at |
| Client side | `intakes` | client_user_id, raw description, structured intake JSON, domain, jurisdiction, urgency, status |
| | `intake_documents` | intake-scoped uploads (copied into the case when a lawyer accepts) |
| | `lawyer_matches` | intake_id, lawyer_id, rank, reasons (persisted for audit), no scores shown as probabilities |
| | `connections` | intake_id, client, lawyer, status (requested/accepted/declined/withdrawn), case_id once accepted |
| | `messages` | case-scoped lawyer↔client messages; `client_updates` for lawyer-approved updates |
| Legal corpus (unchanged) | `legal_sources`, `legal_documents`, `legal_chunks`, `constitution_provisions`, `embeddings`, `ingestion_runs` | provenance, licence, hash, quality status |

Migration `0005_lawyer_workbench` drops the v1 case/review tables (demo data only), creates the tables above, and leaves the
legal corpus untouched.

---

## F. Agents

Every agent is a module exporting an `AgentSpec` (purpose, inputs, outputs, tools, permissions, risk, failure modes, verification)
and a `run(ctx, step) -> StepResult`. `ctx` exposes only the gateway-bound tools listed in the spec.

| Agent | Purpose | Tools (allow-list) | Writes to blackboard | Failure modes → response |
|---|---|---|---|---|
| **Orchestrator** | Understand, plan, route, observe, adapt, enforce limits, finalize | `classify_intent`, `plan`, `compose_answer`, `llm_structured` | plan, answer | invalid LLM plan → template plan; budget hit → stop safely with partial result |
| **Retrieval** | Hybrid search over the case index, evidence packs | `case_search`, `get_chunks` | evidence | low recall → broaden (synonyms, drop filters) once → `insufficient_evidence` signal |
| **Case Analysis** | Parties, facts, allegations, admissions, disputed facts, dates/events, issues, procedural events | `llm_structured`, `get_chunks` | claims, timeline, parties, issues | LLM unavailable → heuristic extractor; ungrounded items dropped |
| **Contract Review** | Obligations, rights, deadlines, termination, penalties, unusual/ambiguous/missing/conflicting clauses | `case_search`, `llm_structured` | claims (kind=contract_*), risks | no contract text → `not_applicable` |
| **Legal Research** | Authorities from approved corpus only; distinguishes judgment / statute / constitution / secondary / case document | `corpus_search`, `corpus_lookup_citation` | authorities | nothing found → alternate query once → "not in corpus" (never generated) |
| **Verification** | Verify every important claim against its evidence | `verify_claim`, `llm_judge` | verdicts | judge unavailable → deterministic only |
| **Contradiction** | Conflicting dates/amounts/statements/clauses; provenance assessment; targeted extra search | `case_search`, `get_chunks`, `llm_structured` | contradictions | conflict unresolved → report both sides + request lawyer review |
| **Missing Information** | Documents/facts referenced but absent; matter-type checklists | `case_search`, `list_documents` | missing | — |
| **Drafting** | Lawyer-controlled drafts with FACTS / AUTHORITIES / INFERENCES / RECOMMENDATIONS | `llm_structured`, `save_draft` (MEDIUM) | draft | unverifiable facts → bracketed placeholders, never invented |
| **Security** | Scan requests, documents, retrieved context and model output for injection/exfiltration/tool abuse | `scan_text` | security findings | detection is advisory; policy engine + gateway enforce |
| **Case Matching** | Intake → domain, jurisdiction, expertise, complexity → verified lawyers with reasons | `search_verified_lawyers` | matches | no verified specialist → says so; never fabricates |
| **Client Intake** | Messy description → structured intake + lawyer-readable summary | `llm_structured` | intake | LLM unavailable → rule-based extraction + explicit "unknown" fields |

### Runtime state machine

```
START ─► SECURE_INPUT ─► CLASSIFY ─► PLAN ─► EXECUTE(step) ─► OBSERVE ─┬─► next step ──────────────┐
                │                                    ▲                  ├─► ADAPT (insert steps) ─────┤
                └─ injection ─► REFUSE               └──────────────────┴─► REPLAN (budget allows) ──┘
                                                                         │
                                       all steps done ─► VERIFY GATE ─► QUALITY CHECK ─► FINALIZE ─► PERSIST + MEMORY
                                                                    └─ fails ─► REPLAN (≤ MAX_REPLANS) ─► else finalize with flags
```

Budgets (env): `MAX_AGENT_STEPS`, `MAX_TOOL_CALLS`, `MAX_RETRIES`, `MAX_REPLANS`, `MAX_EXECUTION_SECONDS`, `MAX_TOKEN_BUDGET`.
Exceeding any of them stops the run safely and returns what was verified so far.

### Observers (adaptation rules — real behaviour, each covered by a test)

| Observation | Adaptation |
|---|---|
| Retrieval returned too little / weak evidence | Broaden: synonym expansion, relax filters, more results (once); then report insufficient evidence |
| Retrieved evidence holds different dates/values for the same event | Insert Contradiction detect → resolve (provenance + targeted search for a third source) → lawyer review flag |
| Contradiction found during review | Insert resolve step per contradiction |
| Verification found UNSUPPORTED/CONTRADICTED claims in the answer | Regenerate the answer from verified evidence only, re-verify (≤ `MAX_RETRIES`), then label remaining claims |
| Research found no authority | Retry with reformulated issue once; then "not in verified corpus" |
| Tool failure | Gateway retries transient errors; semantic search failure falls back to keyword; critical failure → stop safely |
| Flagged (injected) chunk retrieved | Exclude from model context, keep as evidence with a warning, security event + audit, continue |

### Intent → plan templates (LLM planner may refine queries/focus; output validated against the action catalogue)

| Intent | Plan |
|---|---|
| `EVIDENCE_QA` | retrieve → (conflict probe) → compose → verify |
| `CONTRADICTIONS` | retrieve(topic) → analyse(focus) → contradiction.detect → resolve* → verify → compose |
| `CASE_REVIEW` | retrieve(multi-query) → analyse → contradiction.detect → missing.detect → verify → compose |
| `TIMELINE` | retrieve(events) → analyse(timeline) → contradiction.detect → verify → compose |
| `MISSING_INFO` | analyse → missing.detect → compose |
| `CONTRACT_REVIEW` | retrieve(clauses) → contract.review → verify → compose |
| `LEGAL_RESEARCH` | research.search → verify(authorities) → compose |
| `DRAFT` | retrieve → analyse → (research) → drafting.compose → verify → compose |
| `COMPARE_DOCUMENTS` | retrieve per document → contradiction.detect(cross-doc) → compose |
| `SUMMARY` | retrieve(multi-query) → analyse → verify → compose |

---

## G. API

All under `/api/v1`. Errors: `{"error": {"code", "message", "request_id", "details?"}}`. Inputs reject unknown fields.

| Method & path | Who | Purpose |
|---|---|---|
| `POST /auth/register` · `/login` · `/refresh` · `/logout` · `GET /auth/me` · `POST /auth/demo` | public / any | Sessions (refresh cookie, CSRF header) |
| `POST /cases` · `GET /cases` · `GET/PATCH /cases/{id}` | lawyer (org member) | Case workspace |
| `GET/POST /cases/{id}/members` | case lead | Team access |
| `POST /cases/{id}/documents` · `GET /cases/{id}/documents` | case member | Upload → validate → hash → extract → chunk → scan → index |
| `GET /documents/{id}` · `GET /documents/{id}/chunks?page=` · `GET /documents/{id}/file` | case member | Viewer with highlight targets |
| `POST /cases/{id}/chat` | case member | `{message, threadId?}` → `202 {runId, threadId}` |
| `POST /cases/{id}/review` · `/research` · `/draft` | case member | Same runtime with a fixed intent |
| `GET /runs/{id}` · `GET /runs/{id}/events` (SSE) | case member | Plan, step progress, final result |
| `GET /cases/{id}/threads` · `GET /threads/{id}/messages` | case member | Conversation history |
| `GET /cases/{id}/evidence` · `/timeline` · `/claims` · `/contradictions` · `/missing-information` · `/authorities` · `/drafts` · `/tasks` · `/findings` · `/activity` · `/audit` | case member | Workspace views |
| `PATCH /claims/{id}` · `/contradictions/{id}` · `/missing-information/{id}` | case member | Lawyer review (accept / reject / resolved) |
| `POST /cases/{id}/findings` · `POST /cases/{id}/tasks` · `PATCH /tasks/{id}` | case member | Save findings, manage tasks |
| `GET/PATCH /drafts/{id}` · `POST /drafts/{id}/approve` | case member | Draft review |
| `POST /approvals` · `POST /approvals/{id}/decision` · `GET /approvals` | requester | HIGH-risk actions |
| `POST /research` | lawyer | Corpus research outside a case |
| `GET/PUT /lawyers/profile` · `POST /lawyers/verification` · `GET /lawyers/verification` | lawyer | Profile + KYC submission (status server-controlled) |
| `GET /lawyers` · `GET /lawyers/{id}` | public | Verified, published profiles only |
| `POST /intakes` · `GET /intakes` · `GET /intakes/{id}` · `POST /intakes/{id}/documents` | client | Submit a matter |
| `POST /matching` `{intakeId}` | client (owner) | Matches with reasons |
| `POST /intakes/{id}/connect` `{lawyerId}` | client | Request a lawyer (shares intake summary — client confirms) |
| `GET /requests` · `POST /requests/{id}/respond` | lawyer | Accept → case created in lawyer's org, client added as `client` member |
| `GET /portal/cases` · `GET /portal/cases/{id}` · `GET/POST /portal/cases/{id}/messages` | client | Client-safe projection only |
| `POST /cases/{id}/client-updates` | case member | Share an update with the client (HIGH → approval) |
| `GET /admin/verifications` · `POST /admin/verifications/{id}/decision` · `GET /admin/security-events` · `GET /admin/audit` · `GET /admin/health` | admin | Platform operations (no case content) |

### Run result contract (`GET /runs/{id}` → `result`)

```jsonc
{
  "intent": "CONTRADICTIONS", "status": "completed",            // completed | partial | refused | failed
  "plan": [{"id": "s1", "agent": "Retrieval Agent", "action": "retrieval.search", "label": "Retrieve arrest-related evidence", "status": "done"}],
  "answer": {
    "summary": "Two documents give different arrest dates.",
    "confidence": {"level": "high", "reason": "Both values are quoted verbatim from their documents."},
    "requiresLawyerReview": true, "reviewReasons": ["Conflicting evidence on arrest date"]
  },
  "claims": [{"id": "c1", "text": "...", "status": "SUPPORTED", "confidence": "high", "reason": "...",
              "citations": [{"evidenceId": "e1", "documentId": "...", "documentName": "RemandReport.pdf", "page": 2, "paragraph": 3, "quote": "..."}]}],
  "unverified": [/* claims that failed verification, shown separately */],
  "contradictions": [], "missing": [], "timeline": [], "authorities": [], "draft": null,
  "evidence": [/* full evidence items */], "security": [/* findings */],
  "actions": [{"kind": "view_evidence"}, {"kind": "research_authority"}, {"kind": "generate_report"}]
}
```

SSE events: `run.started`, `intent`, `plan`, `step.started`, `step.completed`, `step.failed`, `adapt`, `replan`, `security`, `verification`, `run.completed`, `run.failed`.

---

## H. RAG

```
UPLOAD → VALIDATE (ext + MIME + magic bytes, active content, zip bombs) → HASH (SHA-256, per-case dedupe)
 → ENCRYPT + STORE → EXTRACT (PDF text layer / DOCX / TXT; images → needs_ocr) → NORMALIZE (NFKC, whitespace, de-hyphenate)
 → METADATA (doc type, dates, parties, references) → SECURITY SCAN (per paragraph; flags spans)
 → CHUNK (page- and paragraph-aware, sentence boundaries, ~900 chars, overlap; page/paragraph/section/char offsets)
 → EMBED (when an embedding model is configured) → INDEX (FTS5 / tsvector + vectors / pgvector)
QUERY → SECURITY SCAN → EXPANSION (legal synonyms: arrest ⇄ apprehended/detained/custody …)
 → KEYWORD (BM25) ∥ SEMANTIC (cosine) ∥ METADATA FILTERS (document, doc type, page, date)
 → RECIPROCAL RANK FUSION → RERANK (phrase, proximity, key terms: dates/sections/amounts, doc-type prior)
 → EVIDENCE PACK (deduped, per-document cap, flagged chunks marked) → LLM (fenced, nonce-delimited) → VERIFICATION
```

Evidence item: `document_id, document_name, page, section, paragraph, text, source_type, content_hash, relevance_score, chunk_id, security_flags`.

Without an embedding model, retrieval is keyword + expansion only — it says so in run metadata; it does not pretend to be semantic.

---

## I. Security

Layers (zero trust; each layer assumes the one before it failed):

```
USER → AUTH (JWT, rotation, lockout) → RBAC (account type) → MEMBERSHIP (org, case role) → POLICY ENGINE (action risk, approval)
     → TOOL GATEWAY (agent allow-list, risk, budget) → TOOL (scoped repository: org_id + case_id) → VERIFICATION → AUDIT
```

| Control | Implementation |
|---|---|
| Tenant / case isolation | Repositories require `(organization_id, case_id)`; non-members get 404 (no ID oracle) |
| Client vs lawyer data | Clients use `/portal/*` projections: status, lawyer-approved updates, messages, their uploads. Never traces, notes, research, claims |
| Policy engine | `policies/catalog.py` declares every action (risk, roles, approval); default deny |
| Human approval | HIGH: external communication, sharing documents, client updates, deleting case data, connections. Approval records exactly what will happen and is re-validated at execution |
| Tool gateway | Per-agent allow-list; HIGH-risk tools not registered for agents at all; retries bounded; every call recorded in `tool_calls` |
| Prompt security | Versioned prompts; system / trusted context / untrusted documents / user request separated; untrusted content fenced with per-request random nonce; delimiter look-alikes neutralised; output schema-validated, scanned and verified |
| Documents | Upload validation; injection scan per paragraph; flagged chunks excluded from model context, kept as evidence; security event + audit |
| RAG / memory poisoning | Corpus only from APPROVED sources with quarantine; memory written only from verified outcomes with provenance and expiry |
| Web | CORS allow-list, CSRF header on cookie endpoints, security headers + CSP, no `dangerouslySetInnerHTML`, ORM-only SQL, FTS query quoting |
| Files | Random storage keys, AES-256-GCM at rest, sanitised display names |
| Secrets | Env only; production refuses to start without secrets; log redaction |
| Verification status | Lawyer `verified` only via backend KYC + admin decision; judicial status needs its own verification type |

Full threat model: [SECURITY_THREAT_MODEL.md](SECURITY_THREAT_MODEL.md).

---

## J. Lawyer workbench UX

```
┌──────────────┬──────────────────────────────────────────────────────────┬──────────────────┐
│ + New case   │ State v. Arjun Kumar · FL-2026-0001 · Active · 🔒 Private  │ Evidence ▾       │
│ + New chat   │──────────────────────────────────────────────────────────│ Timeline         │
│              │  You: Find contradictions in the arrest timeline…         │ Claims           │
│ Recent       │                                                          │ Risks            │
│  State v. AK │  FormLaw                                                  │ Activity         │
│  ABC Pvt Ltd │   Plan ✓ Retrieve ✓ Analyse ✓ Contradictions ↻ Verify   │                  │
│              │   Finding  Two documents give different arrest dates.    │ [Remand Report   │
│ Workspace    │   [FIR.pdf · p.4]  [RemandReport.pdf · p.2]              │  p.2 — highlight]│
│  Research    │   Confidence: High — both quoted verbatim                │                  │
│  Drafts      │   Missing: certified arrest memo                         │                  │
│  Saved       │   [View evidence] [Research authority] [Generate report] │                  │
│              │──────────────────────────────────────────────────────────│                  │
│ Profile  ⚙   │  [ Ask FormLaw about this case…                    ↑ ]    │   (collapsible)  │
└──────────────┴──────────────────────────────────────────────────────────┴──────────────────┘
```

Progressive disclosure: the default is select case → ask → watch the plan → read the answer → click a citation.
Workspace views (Overview, Documents, Evidence, Timeline, Claims, Contradictions, Missing, Research, Drafts, Tasks,
Activity, Audit) sit behind one compact view switcher in the case header. Light/dark themes; no decorative animation.

## K. Client portal

Three screens: **My matters** (status cards) → **Submit a matter** (guided: describe → a few intake questions → documents →
review summary → see matched verified lawyers with reasons → request one) → **Matter** (status, lawyer-approved updates,
messages, upload more documents). No agent traces, research, claims or lawyer notes are ever sent to the client.

---

## L. Roadmap & status

| Phase | Scope | Status (2026-10-09) |
|---|---|---|
| 1 Foundation | Orgs/memberships, cases, members, documents, migration 0005 | Done |
| 2 RAG | Case ingestion pipeline, chunk index, hybrid retrieval, rerank, evidence packs, citations | Done (PostgreSQL path untested) |
| 3 Runtime | State machine, planner, router, budgets, events/SSE, persistence | Done |
| 4 Legal agents | Case analysis, contract, research, verification, contradiction, missing info, drafting | Done (deterministic + model paths; model quality not yet measured) |
| 5 Workbench | Chat-first UI, right panel, document viewer, workspace views | Done |
| 6 Security | Policy engine, gateway, injection handling, audit, isolation tests | Done |
| 7 Lawyers & matching | Profile, KYC flow (demo provider), intake, matching, connections, portal | Done |
| 8 Evaluation | Labelled set, metrics CLI, adversarial cases | Done (deterministic mode) |
| 9 Demo & polish | Seeded synthetic matters, malicious PDF scenario, browser walkthrough | Done |

Next: measure model mode (`scripts/evaluate.py --with-llm`), run PostgreSQL + pgvector, real KYC provider, OCR, MFA,
frontend test suite, Redis-backed rate limits for multi-instance deployments.

The README "Status" section is the source of truth for what is implemented and verified.

## M. Agent dependencies & integration boundaries

```
                 ┌──────────── Security (request, chunks, output) ────────────┐
                 ▼                                                            │
 Orchestrator ─► Retrieval ─► Case Analysis ─► Contradiction ─► Verification ─► Composer ─► Persist/Memory
       │             ▲              │                ▲               ▲
       │             └── targeted ──┘                │               │
       ├─► Contract Review ──────────────────────────┼───────────────┤
       ├─► Missing Information ◄── (documents, references, checklist)│
       ├─► Research (legal corpus only) ─────────────────────────────┤
       └─► Drafting ◄── verified claims + verified authorities ──────┘
 Client side:  Intake ─► Matching (verified lawyers only) ─► Connection ─► lawyer accepts ─► Case
```

Boundaries:

* Agents communicate only through the run **blackboard** (typed state) — never by calling each other.
* Retrieval is the only agent that reads the case index; others request chunks through gateway tools.
* Research is the only agent that reads the legal corpus. Drafting may cite only authorities on the blackboard that passed verification.
* Verification consumes claims from any agent and is the only writer of verdicts.
* Matching and Intake never see lawyer-side case data; lawyer-side agents never see other organizations' data.
