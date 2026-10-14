# FormLaw — Case/Contract Review Agent (milestone 1)

An evidence-first review agent for legal case files and contracts.
**The LLM is not the source of truth; the supplied document is.**

```
DOCUMENT TEXT + USER QUESTION
        │
        ▼
 ReviewService ──► ReviewAgent ──► LLMProvider (swappable)
                      │
                      ├─ prompt injection defence (delimiters + neutralisation + scan)
                      ├─ schema re-validation (Pydantic, extra="forbid")
                      ├─ deterministic grounding checks (validators.py)
                      └─ bounded retry with validation feedback
        ▼
 ReviewResult  (facts, timeline, issues, risks, contradictions,
                missing information, claims, evidence, warnings, security flags)
```

Scope: only the Review Agent. No orchestrator, auth, database, verification, research or
drafting yet — only the `Agent` contract (`app/agents/base.py`) and two placeholder protocols
(`app/agents/interfaces.py`) that the future Orchestrator will build on.

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # then set LLM_API_KEY and LLM_MODEL
uvicorn app.main:create_app --factory --reload
```

`LLM_BASE_URL` can point at any OpenAI-compatible `/chat/completions` endpoint.
Without `LLM_API_KEY`/`LLM_MODEL` the API starts but `POST /api/v1/reviews` returns `503 LLM_NOT_CONFIGURED`.

## Tests

```bash
pytest                       # whole suite, no API key or network needed
pytest tests/unit            # agent, grounding, prompts, provider, config/logging
pytest tests/security        # injection, oversize/empty input, log hygiene
pytest tests/integration     # FastAPI endpoint
ruff check . && mypy app     # lint / types
```

## API

`POST /api/v1/reviews`

```json
{"request": "When was Arjun Kumar arrested?", "workflow_type": "case_review",
 "document_text": "...", "document_name": "case_001.pdf"}
```
→ `200 {review_id, workflow_type, status, result}` or
`{"error": {"code", "message", "request_id"}}` with `413 DOCUMENT_TOO_LARGE`, `422 INVALID_INPUT|EMPTY_DOCUMENT`,
`502 RETRY_EXHAUSTED`, `503 LLM_NOT_CONFIGURED`. Validation errors never echo the submitted document.

## What is enforced in code (not in the prompt)

| Rule | Behaviour |
|---|---|
| Evidence text must be a verbatim excerpt of the document (whitespace/case-insensitive) | otherwise rejected → retry → fail |
| Cited evidence ids, affected ids, and all item ids must exist / be unique | otherwise rejected |
| Contradictions need two distinct evidence ids; affected facts → `CONTRADICTED`, timeline → `CONFLICTED` | forced by code |
| No evidence ⇒ fact/claim can't be `SUPPORTED`; inference-only risks flagged | downgraded + warning |
| Citations / sections / case names / court names must appear in the document | otherwise rejected |
| Page / section / paragraph labels must be findable in the document | otherwise nulled + warning |
| `document_name` comes from the caller, never the model | overwritten |
| Oversized documents | `DOCUMENT_TOO_LARGE`; never truncated |
| Malformed or out-of-range model output | retry (≤ `MAX_RETRIES`) with feedback, then structured failure |

## Security notes

- Document and request text are delimited (`<UNTRUSTED_DOCUMENT>`, `<USER_REQUEST>`) and any look-alike
  delimiter inside them is defanged; the system prompt states that document instructions are data.
- The agent has **no tools**: no filesystem, shell, network, DB, or secrets. Its only side effect is the
  injected `LLMProvider` call. Injection attempts are flagged (`security_flags`, security log event) without
  copying document text.
- Logs carry ids, counts, durations, error codes and a short document hash — never document text, prompts or keys
  (field-name redaction as a second layer).
- API keys are `SecretStr`, read from the environment only.

## Known limitations (be aware)

- Tests use a **scripted fake LLM**. They prove the pipeline, validation and failure handling are correct; they do
  **not** prove a real model answers well. Validate real-model behaviour with an evaluation run on the Arjun Kumar
  fixtures (`tests/fixtures.py`) before relying on it.
- Code can verify that quotes are real and legal authorities are present in the document; it cannot verify that a
  model's *interpretation* is right (e.g. a claim marked `SUPPORTED` that the cited text doesn't really support).
  That is the future Verification Agent's job — claims are returned verification-ready.
- No auth/tenant/case isolation yet (no data layer exists). `ReviewService` is the place to add it.
- Very large documents are rejected, not chunked; retrieval/chunking arrives with the Retrieval service.

## Next step

Add the Orchestrator skeleton (typed plan/state, limits, failure classification) that calls
`ReviewAgent` through the `Agent` contract, plus a real-model evaluation harness over the Arjun Kumar fixtures.
