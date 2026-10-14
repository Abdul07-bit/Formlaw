## Workflow: CASE_REVIEW
Extract, only where the document supports it:
- parties (accused, complainant, witnesses, counsel, court, organisations) with their roles
- relevant facts and important dates
- a timeline (incident, complaint, arrest, remand, bail, hearings, filings); each event has a
  date string exactly as written in the document or null; conflicting dates for one event must
  appear as separate events with status CONFLICTED, never merged or resolved
- procedural and evidentiary issues (for example identification quality, record gaps)
- contradictions between parts of the document
- missing information (for example incomplete bail records)
- claims worth later verification, each tied to evidence
Facts relevant to alibi, identification or guilt are reported as evidence and what it shows,
never as a conclusion about guilt or innocence.
