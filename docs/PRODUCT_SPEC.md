# FormLaw — product specification

FormLaw is a legal-services and case-collaboration platform for India. Clients describe a legal problem and, where a
compliance-reviewed process permits it, connect with a verified advocate. Advocates run real matters in a secure workspace
where agentic AI researches, analyses evidence and drafts — with a citation behind every statement and the advocate
accountable for every legal judgment.

The platform must be useful without AI, better with it, and never claim more than it can show.

## Users and roles

| Role | Who | Can | Cannot |
|---|---|---|---|
| Client | A person or business with a legal problem | Submit a guided enquiry, upload documents, request an advocate (when permitted), message their advocate, see advocate-approved updates | See agent traces, research, internal notes, unapproved drafts, or other clients' anything |
| Advocate | A lawyer, verified against a State Bar Council roll | Run matters they are members of, use the AI workbench, review client requests after a conflict check | Open matters they are not a member of — including as firm owner |
| Firm owner / admin | Advocate who manages a firm | See the firm's matter register (metadata only) | Read any matter they have not been added to |
| Platform admin | FormLaw operations | Verify advocates (with a recorded roll check), suspend/reinstate, draft connection policies, monitor security and audit, view corpus coverage | Read case content; approve a connection policy |
| Compliance reviewer | Person accountable for regulatory compliance | Approve/reject/revoke connection policies, review the compliance audit trail | Draft policies; administer users; read case content |

Staff accounts (admin, compliance) are never self-registered: `python -m app.manage create-staff`.

## Core journeys

1. **Client enquiry** — describe the problem in plain language → guided questions (dates, place, urgency, goal, other
   parties) → optional documents → a structured summary that separates what the client said from what was inferred.
   The summary is private until the client chooses to share it.
2. **Compliance-controlled connection** — only when the in-force ConnectionPolicy enables it: suggestions by verified
   practice area, location and language (alphabetical, no ranking, no paid placement) → the client reads the required
   disclosures and agrees → a consent record stores the exact text → the advocate is notified without the matter title.
3. **Conflict check** — the advocate sees only the names involved and any matches in their own firm's matters (by
   reference) → clears or declines. A conflict decline tells the client only that the advocate cannot take the matter.
4. **Engagement** — accepting creates a private matter in the advocate's firm, with the client as a portal member and
   their documents ingested.
5. **Matter work** — chat-first workspace: ask, watch the plan, read an answer whose statements are verified against
   quoted evidence; evidence, timeline, claims, contradictions, missing information, research, drafts, tasks, activity, audit.
6. **Client collaboration** — messages; updates and drafts reach the client only through a human approval of that exact content.
7. **Advocate verification** — profile + documents → provider checks (demo provider today, clearly labelled) → an admin
   records an official Bar Council roll check → VERIFIED for 365 days → expiry, suspension, reinstatement, full history.

## Capabilities and status

Status as of 2026-10-13. "Done" means implemented and covered by passing tests (SQLite and PostgreSQL; browser flows by Playwright).

| Capability | Status |
|---|---|
| Accounts, sessions, RBAC, organization + matter isolation, firm-admin restriction | Done |
| Advocate verification lifecycle with roll-check evidence, expiry, suspension, history | Done (manual roll check; no automated identity provider) |
| ConnectionPolicy gate (off by default), compliance-reviewer approval, consent records | Done — the policy *content* needs counsel (see COUNSEL_REVIEW_BRIEF.md) |
| Conflict check before disclosure | Done (name matching within the advocate's firm; advocate confirms) |
| Guided intake with client-declared parties | Done |
| Matter workspace, documents, secure messaging, approvals, audit | Done |
| Agent runtime (orchestrator, 12 agents, gateway, budgets, verification gate) | Done — deterministic mode tested; model mode exercised with a scripted provider only |
| Legal source registry, licence gate, ingestion CLI, coverage report | Done |
| Five-year judgment corpus | **Incomplete**: 150 Supreme Court judgments in the window (sampled); no High Courts — see CORPUS_COVERAGE.md |
| OCR, MFA, password reset, e-mail delivery, object storage, retention jobs, malware scanning, billing | Not built (see SECURITY_THREAT_MODEL.md) |

## Principles enforced in code

* Evidence is the source of truth: every AI statement cites a passage and quote that must exist verbatim, or it is
  labelled unsupported/unverified and kept apart from findings.
* The backend is the security boundary: default-deny policy engine, membership checks on every matter route, 404 for
  anything the caller may not see.
* Consequential actions (sharing, sending, deleting, connecting) need a human approval of the exact action.
* No outcome predictions, ratings, win rates, rankings or paid placement — FormLaw cannot verify them and they risk
  breaching advocate advertising rules.
* Nothing is claimed that is not measured: corpus coverage, verification and compliance status say exactly what was checked.

## Non-goals

FormLaw is not a law firm, does not give legal advice, does not decide anyone's rights, and does not recommend or
rank advocates. It does not claim to be the first or only product of its kind (no competitor study has been done).
