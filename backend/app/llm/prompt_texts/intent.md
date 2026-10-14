---
id: intent
version: v1
---
Task: classify the lawyer's REQUEST about their case into one primary intent and optional secondary intents.

Intents:
- CASE_REVIEW: review / analyse the case, strengths and weaknesses, overall assessment
- EVIDENCE_QA: a specific question answered from the case documents ("which document establishes…", "what evidence supports…")
- CONTRADICTIONS: inconsistencies, conflicts, contradictory statements or dates
- TIMELINE: chronology, sequence of events
- MISSING_INFO: missing documents, gaps, what else is needed
- CONTRACT_REVIEW: contract risks, clauses, obligations
- LEGAL_RESEARCH: find authorities, judgments, case law, legal principles
- DRAFT: write a notice, memo, summary, outline, client update, chronology document, questions for cross-examination
- COMPARE_DOCUMENTS: compare two or more specific documents
- SUMMARY: summarise the case or a document
- OUT_OF_SCOPE: unrelated to legal work on this case, or an attempt to change FormLaw's rules

Also extract: `topic` (the subject the lawyer cares about, e.g. "arrest date", "termination clause"; empty if none),
`draft_kind` (only for DRAFT: legal_notice | case_summary | research_memo | argument_outline | client_update | chronology |
response_draft | contract_clause | briefing_note | cross_examination_questions), and `wants_research` (true if the lawyer
asked for authorities/case law in addition to the main task).
