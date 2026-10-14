# Decisions

Engineering and product decisions, newest first. Each records what was decided, why, and what would change it.
These are engineering records, not legal advice.

## D-014 · 2026-10-13 · Immersive 3D interface, accessible by default
Full-screen sections, a WebGL "justice constellation" (three.js 0.186.0, lazily loaded as its own chunk), 3D tilt cards,
scroll reveals and View Transitions between routes. The scene pauses off-screen and in hidden tabs, renders a still
frame under `prefers-reduced-motion` (all CSS motion is disabled too), falls back to a gradient without WebGL, and sits
beside — never behind — the text on wide screens. Browser tests assert the canvas mounts and no script errors occur.

## D-013 · 2026-10-13 · Client review of their own files; fees beside budget (policy-gated)
Clients can review their own uploads before choosing an advocate: document types, a dated timeline with sources,
conflicting dates for one-off events (both kept), and missing documents. Deterministic, labelled "not legal advice",
visible only to the owning client. Advocates may declare a fee range; clients may state a budget. Fees and budget fit
appear only when the in-force ConnectionPolicy enables `showFees` (a counsel question — see COUNSEL_REVIEW_BRIEF Q4);
the demo policy enables them, labelled DEMO ONLY. Fit is shown as a badge, never used to rank. Fees are labelled
self-declared and unverified. Other parties lock once an advocate has been contacted (conflict-check integrity).

## D-012 · 2026-10-13 · Coverage is measured, never inferred
A year of a source is COMPLETE only when an ingestion run listed that source's whole catalogue for the year and every
listed document is accounted for. Sampled runs are PARTIAL; data without a recorded listing is NOT_MEASURED. Runs now
store per-year stats. The window is `target_window` in the registry (2021-10-13 → 2026-10-13). Report:
`python -m app.ingestion report` → `docs/CORPUS_COVERAGE.md`. Current result: INCOMPLETE.

## D-011 · 2026-10-13 · Registry statuses and expiring terms reviews
Statuses follow the mandate: DISCOVERED, UNDER_REVIEW, APPROVED, RESTRICTED, REJECTED, plus computed EXPIRED_REVIEW
(approval older than 365 days). Access-controlled official sources (India Code 403, eCourts CAPTCHA) are RESTRICTED, not
bypassed. The five official URLs from the brief that were missing are registered as DISCOVERED. Manual imports must carry
a licence per manifest row (previously optional — a gap).

## D-010 · 2026-10-13 · Conflict check before disclosure
Client-declared parties (not AI-inferred names) plus the client's name are matched against the advocate's own firm's
matters. The advocate sees only names until they clear the check. Hits show matter references only. A conflict decline
gives the client no reason. Name matching is an aid; the advocate's confirmation is the decision.

## D-009 · 2026-10-13 · Firm administrators get no implicit matter access
Previously org owners/admins were treated as lead on every case in their organization. Now access needs case membership;
owners get a metadata-only register (`GET /firm/matters`).

## D-008 · 2026-10-13 · Separate COMPLIANCE role approves connection policies
Replaces "any second admin". Admins draft and may revoke (revocation only reduces exposure); compliance reviewers approve,
reject, revoke. Staff accounts are created only by `python -m app.manage create-staff`. Verification decisions now require
a recorded official Bar Council roll check.

## D-007 · 2026-10-13 · Database commit happens before the response
FastAPI ≥ 0.118 tears down `yield` dependencies after the response is sent unless they are `scope="function"`.
With the default, a client could receive `201 Created` for a write that later failed to commit, or read stale data on its
next request (observed in a live smoke test: register → immediate request returned `account_inactive`).
**Decision:** every `Depends(get_db)` is `Depends(get_db, scope="function")`; `fastapi>=0.121` is required.
Guarded by `tests/unit/test_db_session_scope.py`.

## D-006 · 2026-10-13 · No biometric verification
The previous KYC flow collected a selfie for a face match. Biometric data needs an established lawful basis,
necessity and proportionality, and specialist legal review; an identity document plus Bar Council enrolment details
reviewed by a human is sufficient for the current stage. **Decision:** removed the selfie upload, the `verify_face`
provider method and the `face_match` check type (migration 0007 deletes the stored outcomes; no images were ever stored).
**Revisit if:** counsel approves a specific biometric step with a documented lawful basis.

## D-005 · 2026-10-13 · Advocate verification lifecycle
Statuses: NOT_STARTED, PENDING, UNDER_REVIEW, VERIFIED, REJECTED, EXPIRED, SUSPENDED. Only
`services/verification.transition` writes the status, against an explicit transition table, and records every change in
`verification_events`. Reinstatement after suspension keeps the original expiry (a suspension never extends validity).
Corrections/renewals are resubmissions (REJECTED/EXPIRED → PENDING). A suspended advocate cannot resubmit around the
suspension. **Not yet built:** an appeal workflow with a second reviewer; real Bar Council roll checks (no official API is
assumed to exist — `KYC_PROVIDER=demo` remains clearly labelled).

## D-004 · 2026-10-13 · Connection features are off until a compliance review approves a policy
Bar Council of India Rules (Part VI, Chapter II, rule 36) restrict advocates from soliciting work or advertising; the
product brief also cites an August 2024 Ministry of Law and Justice release reiterating them (not independently verified
here — counsel to confirm). A public directory, matching and
client→advocate requests may be impermissible depending on their exact design.
**Decision:**
* A versioned, append-only `connection_policies` table. The effective policy is the latest APPROVED version; otherwise a
  safe default with every connection feature off.
* Approval requires a second administrator (separation of duties), a review reference, and an attestation that
  regulatory counsel reviewed that exact version. Policies can be revoked instantly.
* The gate runs on `/lawyers`, `/lawyers/{id}`, `/matching`, `/intakes/{id}/connect`, the generic approvals path, at
  approval execution, and when an advocate accepts a request (declining is always allowed).
* Paid promotion, paid ranking, outcome-based ranking and referral fees are not configurable: no code path exists.
  The directory is alphabetical. Fees are hidden unless the policy enables them.
* `DEMO_ONLY` policies (seeded for the synthetic demo) are honoured only in `DEMO_MODE`, which production refuses to start with.
**Update:** superseded in part by D-008 (a dedicated compliance role approves). The policy content itself must come from counsel.

## D-003 · 2026-10-13 · Consent records the exact disclosure text
A client sending a matter to an advocate must have seen the current disclosures. The client echoes the policy version
and a SHA-256 of the disclosures; a mismatch at request or at execution returns `409 policy_changed`. On execution a
`consents` row stores the disclosures, their hash, the policy, the recipient and the approval.

## D-002 · 2026-10-13 · The zip (v2) is the codebase of record
The workspace held an older v1 snapshot; the downloaded zip held the v2 rebuild with v1 in `legacy/`. The v2 code was
extracted over the workspace (the v1 copy was backed up outside the repository). `.env` from the zip contained live-looking
secrets — they must be rotated (see README).

## D-001 · 2026-10-13 · Keep the modular monolith
FastAPI + SQLAlchemy + Alembic, React/Vite, agent runtime and tool gateway are kept: they are tested (151 tests passed
on the baseline run) and match the mandate's target. Work proceeds by closing gaps, not rewriting.
