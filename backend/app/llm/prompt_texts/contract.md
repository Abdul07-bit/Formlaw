---
id: contract
version: v1
---
Task: review the contract passages for the lawyer.

Return `findings`, each with `category` (obligation | right | deadline | termination | penalty | payment | liability |
indemnity | confidentiality | dispute_resolution | governing_law | unusual | ambiguous | conflicting | risk), `title`,
`text` (neutral description that attributes the clause: "Clause 7 provides that …"), `passage_id`, `quote` (verbatim),
`risk_level` (low | medium | high) and `party` (who it binds or benefits, if stated).

Also return `missing_provisions`: standard provisions you could not find in the passages (title + why it matters).
These are absences, not facts — never quote for them.
