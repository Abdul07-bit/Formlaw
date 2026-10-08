# FormLaw — Justice, connected

Agentic legal intelligence, grounded in evidence. FormLaw is the mediator between **clients** and **KYC-verified advocates & judges** in India: agents review a client's case documents, ground every fact in evidence, flag contradictions and missing documents, find related verified outcomes, draft a first document — then match and connect the client with the right lawyer at a transparent fee.

> Frontend prototype. No backend required — all data lives in `localStorage` behind a service layer (`src/services/api.ts`) that maps 1:1 to the FastAPI endpoints listed below.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build
```

## 3-minute judge demo

| Time | Action |
|---|---|
| 0:00 | Open `/` — 3D hero, "Your case, prepared by AI. Resolved by verified lawyers." |
| 0:20 | Click **Run full agentic review** (or open `/demo`) — agents animate step by step |
| 0:45 | **CONTRADICTION DETECTED** — 14 March vs 12 March → click *Compare both sources* |
| 1:10 | Click any evidence chip → source page with highlighted text and hash |
| 1:25 | **Ask AI** → "When was Arjun Kumar arrested?" → conflicting-evidence answer with both citations |
| 1:40 | **Matched Lawyers** → Connect with Adv. Meera Iyer → brief sent |
| 1:55 | Sidebar persona **Lawyer** → Client Requests → Accept with fee → chat |
| 2:10 | Open `/demo/attack` → **Prompt injection blocked**, document quarantined, analysis continues |
| 2:30 | `/how-it-works` → click agents to see permissions, risk, approvals |
| 2:45 | Draft tab → **Human approval required** (HIGH risk external action) |
| 3:00 | "AI can reason. Evidence decides." |

KYC loop: Get Started → *Advocate* → profile → degree → ID → live face (webcam, or *Demo verify*) → switch to **Admin** persona → Approve → the advocate appears in `/lawyers`.

## What is live vs simulated

| Capability | Status |
|---|---|
| File validation (ext + MIME + size), filename sanitising, text extraction for TXT/MD/CSV | **Live** |
| Security agent (prompt-injection / tool / exfiltration detection, quarantine) | **Live** |
| Classification, fact extraction, contradiction detection, verification grading, missing-info checklists | **Live** (deterministic, client-side) |
| Grounded Q&A, related-case retrieval, lawyer matching & fee estimates, drafting | **Live** (client-side) |
| Client ↔ lawyer connection, accept/decline, chat, completed-case publishing, admin KYC desk | **Live** (localStorage) |
| Webcam capture for face verification | **Live**; liveness + face-match score **simulated** |
| PDF/DOCX/XLSX/image extraction & OCR | **Future backend** (files accepted, marked "queued") |
| Observability metrics | **Simulated** (labelled) except live counts |
| Payments / escrow, Bar Council roll lookup, e-filing | **Future backend** |

## Structure

```
src/
  types/            domain types = API contract
  data/             synthetic seed data (lawyers, verified case DB, demo case + malicious doc)
  services/
    store.ts        local persistence (swap for HTTP)
    api.ts          API facade — one function per endpoint
    ingest.ts       validation, sanitising, chunking
    agents.ts       orchestrator + security, review, verification, contradiction,
                    missing-info, precedent, matching, drafting agents; grounded Q&A
  components/       ui, layout, three (3D hero), art (Indian legal SVGs), agents, case, kyc
  pages/            Landing, GetStarted, HowItWorks, Lawyers, Messages, client/, lawyer/, admin/
```

## Backend contract (FastAPI)

| Endpoint | Replaces |
|---|---|
| `POST /api/auth/session` | `signIn` |
| `POST /api/lawyers/{id}/kyc` (multipart → object storage, server face-match) | `submitKyc` |
| `POST /api/admin/kyc/{id}/decision` (admin) | `reviewKyc` |
| `POST /api/lawyers/{id}/completed-cases` (server NER anonymiser) | `addCompletedCase` |
| `POST /api/admin/completed-cases/{id}/verify` | `verifyCompletedCase` |
| `POST /api/cases`, `POST /api/documents` | `createCase`, `ingestFile` |
| `POST /api/cases/{id}/review` (SSE stream of `TraceStep`, returns `Analysis`) | `runAnalysis` |
| `POST /api/cases/{id}/ask` → `GroundedAnswer` | `answerQuestion` |
| `POST /api/connections`, `/{id}/decision`, `/{id}/messages` | `requestLawyer`, `respondToRequest`, `sendMessage` |

Suggested storage: PostgreSQL (+ pgvector for evidence chunks), object storage for files/KYC (encrypted, separate vault), Redis for task queues. Keep `types/index.ts` as the shared schema (mirror in Pydantic).

## Security controls in the prototype

Allow-listed extensions + MIME match, 15 MB cap (8 MB for KYC), sanitised filenames (no path traversal), uploaded text never rendered as HTML or executed, injection detection with whole-document quarantine, PII redaction on lawyer-published cases, raw files shared only after the lawyer accepts, human approval for HIGH-risk actions, no secrets in the frontend.

All people, cases and enrolment numbers are synthetic. FormLaw is not a law firm and does not provide legal advice. The State Emblem of India is intentionally not used.
