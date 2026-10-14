# FormLaw threat model

Assets: confidential case documents and derived knowledge, client identities, lawyer credentials and verification state,
the integrity of answers (no fabricated facts or law), and the audit trail.
Trust boundaries: browser ↔ API · API ↔ database/storage · runtime ↔ model provider · **documents ↔ everything** (documents
are always untrusted, including the lawyer's own uploads).

Every control below is enforced in code; the test that proves it is listed. "Detection" controls (the injection scanner,
the Security Agent) are defence in depth — the enforcement points are the policy engine, scoped repositories, the tool
gateway and the verification gate.

| Threat | Controls | Tests |
|---|---|---|
| **Direct prompt injection** (in a chat request) | Request scanned before planning; run refused, no tool but the scanner runs; security event | `security/test_prompt_injection.py::test_direct_injection_in_chat_is_refused` |
| **Indirect prompt injection** (in a document) | Per-chunk scan at ingestion; flagged chunks never enter a prompt (`AgentContext.passages`); untrusted text fenced with a per-call random nonce and delimiter look-alikes defanged; system prompt holds no untrusted text; document kept as evidence; security event + audit | `test_injected_text_never_reaches_a_model_prompt`, `test_malicious_document_flagged_but_kept_as_evidence`, `test_fence_cannot_be_closed_by_document_text` |
| **Model output abuse** (echoing instructions, links, image beacons, fabricated values) | Output scanned (`scan_output`); every model item needs a resolvable passage id and a verbatim quote; statutes/citations must appear in the cited source; verification gate; judge may only downgrade | `test_model_output_with_links_or_instructions_is_dropped`, `agents/test_runtime.py::test_ungrounded_extraction_is_discarded`, `test_judge_can_downgrade_but_never_upgrade` |
| **RAG poisoning** | Legal corpus only from APPROVED, licence-checked sources with quarantine and duplicate-poisoning defence; case chunks scanned; memory written only from verified outcomes | `test_rag_poisoning_document_cannot_mark_claims_verified`, `integration/test_legal_corpus.py` |
| **Memory poisoning** | Memory scoped to organization/case, provenance-tagged, expiring, never stores document text, never treated as evidence (memory only triggers re-checks against chunks) | `integration/test_arrest_timeline.py::test_evidence_question_adapts_to_conflict` |
| **Tool abuse / excessive agency** | Per-agent tool allow-lists (default deny); no HIGH-risk tool is registered for agents; agents have no network, e-mail, file-system or delete tools; HIGH actions require human approval | `test_gateway_default_deny_and_no_high_risk_tools`, `test_agents_can_never_trigger_high_risk_actions` |
| **Agent loops / runaway cost** | `MAX_AGENT_STEPS`, `MAX_TOOL_CALLS`, `MAX_RETRIES`, `MAX_REPLANS`, `MAX_EXECUTION_SECONDS`, `MAX_TOKEN_BUDGET`; stops safely with verified partial results | `test_step_budget_stops_safely`, `test_tool_call_budget_stops_safely` |
| **Hallucinated law / fabricated citations** | Research only from the corpus; unknown citations refused; authorities re-read and hash-checked; drafts strip unbacked references | `test_research_reformulates_then_reports_absence`, `evaluation/test_evaluation.py` (0 fabricated citations), `integration/test_legal_corpus.py` |
| **IDOR / BOLA / cross-tenant access** | Single access function: org membership AND case membership; every repository query filters `organization_id` and `case_id`; outsiders get 404 | `security/test_isolation.py` |
| **Privilege escalation** | Role re-read from DB per request; role change invalidates tokens; admins not self-registrable; viewers cannot run agents; only leads request deletion | `test_isolation.py::test_same_firm_requires_case_membership`, `test_only_case_lead_can_request_deletion` |
| **Client ↔ lawyer data leakage** | Clients use `/portal/*` projections only (status, approved updates, messages, own uploads); never traces, claims, research, notes | `api/test_product_flows.py::test_client_intake_matching_connection_and_portal` |
| **Self-verification / fake credentials** | `extra="forbid"` inputs; verification state written only by server workflows + admin decision; judicial status needs its own check; changing credentials re-opens verification | `test_lawyer_cannot_self_verify_or_publish_unverified`, `test_kyc_verification_flow` |
| **Unlawful advocate solicitation / advertising** (BCI Rules Part VI Ch. II r.36) | Directory, matching and client requests are OFF unless a versioned ConnectionPolicy is APPROVED by a second admin citing a counsel review (DEMO_ONLY policies honoured only in DEMO_MODE, which production refuses); gate re-checked when the client's approval executes; directory alphabetical; no paid placement, ranking or referral-fee code path; profile fields limited to the policy allow-list | `security/test_connection_policy.py` |
| **Consent drift** (client agrees to text that changed) | Client echoes the policy version + disclosure hash it was shown; mismatch → 409 `policy_changed`; consent row stores the exact disclosures and hash | `test_consent_is_recorded_against_the_exact_disclosures`, `test_policy_change_between_request_and_approval_blocks_execution` |
| **Unnecessary biometric collection** | No selfie / face-match step; `face_match` removed from the schema (migration 0007) | `test_no_biometric_verification_type`, `api/test_product_flows.py::test_kyc_verification_flow` |
| **Stale or revoked credentials** | Verification lifecycle enforced by one transition function; SUSPENDED hides the profile and blocks resubmission; every change recorded in `verification_events` | `test_suspension_hides_profile_and_reinstatement_keeps_original_expiry`, `test_illegal_verification_transition_is_rejected` |
| **False success** (response sent before the transaction commits) | `get_db` is function-scoped on every route, so the commit (or its failure) happens before the response | `unit/test_db_session_scope.py` |
| **Unauthorised external communication / deletion** | Approval records the exact action, re-validated at execution, audited; only the requester can decide | `test_client_update_waits_for_approval`, `test_rejected_approval_does_nothing` |
| **Malicious PDF / DOCX** | Extension + MIME + magic bytes; PDF active content refused; DOCX bombs/macros/path entries refused; size caps; malicious upload recorded as a security event in its own transaction | `security/test_file_uploads.py`, `unit/test_security_primitives.py` |
| **Path traversal** | Random storage keys; filenames sanitised and used only as labels | `test_path_traversal_filename_is_neutralised` |
| **SQL injection / FTS syntax injection** | ORM parameters only; FTS terms quoted | `integration/test_legal_corpus.py::test_fts_query_syntax_cannot_be_injected` |
| **XSS** | React escapes all text; no `dangerouslySetInnerHTML`; API sends `nosniff`, `X-Frame-Options: DENY`, restrictive CSP; downloads served as attachments with a fixed type list | manual review |
| **CSRF** | Bearer token in memory; refresh cookie httpOnly SameSite=Strict scoped to `/api/v1/auth` and requiring `X-Requested-With` | `api/test_auth.py::test_refresh_requires_csrf_header`, `test_refresh_cookie_is_httponly_strict` |
| **SSRF** | Agents have no network tools; corpus fetcher restricted to registered https hosts, public IPs, no redirects | `test_legal_corpus.py::test_ssrf_guard` |
| **Secret leakage** | Keys only in backend env; production refuses to start without secrets; log redaction; prompts never include secrets | `unit/test_security_primitives.py::test_log_redaction` |
| **Firm administrator over-reach** | Organization owner/admin grants no case access; firm management sees a metadata-only register (reference, type, status, leads — no titles, clients or content) | `test_isolation.py::test_firm_owner_gets_no_access_to_matters_they_are_not_on` |
| **Platform staff bypassing matter authorization** | Admin and compliance roles are not case roles; every case route requires case membership | `test_isolation.py::test_platform_admin_and_compliance_cannot_bypass_matter_authorization` |
| **Self-approval of compliance decisions** | Only the COMPLIANCE role approves connection policies; drafter ≠ reviewer even across a role change; staff accounts only via `python -m app.manage` | `test_connection_policy.py` (`…requires_a_compliance_reviewer…`, `…via_role_change`, `test_staff_accounts_…`) |
| **Conflict-of-interest leakage** | Advocate sees only the names involved until they clear a conflict check; automated hits name the firm's matter by reference only; a conflict decline tells the client nothing; the check searches only the advocate's own firm | `security/test_conflict_check.py`, `e2e/flows.spec.ts` |
| **Verification without evidence** | VERIFIED requires a recorded official Bar Council roll check (source, reference, date, enrolment + name match); recorded in the verification history | `api/test_product_flows.py::test_kyc_verification_flow` |
| **Unlicensed corpus documents** | Only APPROVED sources with a terms review under 365 days old are fetched; manual imports must carry a licence per row; RESTRICTED sources (CAPTCHA/403) are never bypassed | `integration/test_legal_corpus.py`, `integration/test_coverage_report.py` |
| **Overstated corpus coverage** | Coverage is COMPLETE only against a recorded full listing of the source; sampled or unrecorded years are PARTIAL / NOT_MEASURED; gaps listed | `integration/test_coverage_report.py` |
| **Database-specific failures** (SQLite hides VARCHAR overflow, `ORDER BY` differences) | Full suite runs on PostgreSQL 16 + pgvector; CHECK-constrained values must fit their columns | `FORMLAW_TEST_DATABASE_URL=postgresql+psycopg://… pytest`, `unit/test_schema_widths.py` |
| **Brute force / session theft** | Per-IP rate limits, lockout after 5 failures, generic errors; refresh-token rotation with reuse detection revoking the family; forged and `alg=none` tokens rejected | `api/test_auth.py` |

## Not yet mitigated (must be addressed before handling real client data)

| Threat | Status | What is needed |
|---|---|---|
| Malware in uploads | Structural validation only (magic bytes, active PDF content, DOCX macros/bombs); **no antivirus scan** | ClamAV or a managed scanning service before ingestion |
| Account takeover | Passwords + lockout only; **no MFA**, **no password reset** | TOTP/WebAuthn MFA for advocates and staff; reset via verified e-mail |
| Multi-instance abuse | Rate limits are **in-process** (one API instance) | Shared store (Redis) behind the same interface |
| Unauthorized data retention | **No retention or deletion jobs**; deletion of a case is a soft delete | Retention schedule per data class, DPDP-compliant erasure workflow, backups that honour erasure |
| Insecure backups | Not configured in this repository | Encrypted, access-controlled backups with restore drills (see README operations section) |
| Compromised dependencies | `npm audit` / `pip-audit` **not run in CI**; no CI pipeline in the repository | CI with lockfile installs, dependency and secret scanning |
| Object storage | Files are AES-GCM encrypted on the **local disk**; no object-storage adapter or signed short-lived URLs | S3/MinIO adapter with server-side encryption and signed URLs |
| Identity of advocates | Documents + a reviewer's manual Bar Council roll check; **no automated identity provider** is integrated | A contracted identity/KYC provider (no official Bar roll API is assumed to exist) |
| Secrets distribution | The project zip that was shared contained `.env` with live-looking keys | Rotate those keys; never share `.env`; managed secrets in deployment |

Accepted residual risk: pattern-based injection *detection* is incomplete by nature; enforcement (gateway, policy engine,
verification, client projections) never depends on detection succeeding.
