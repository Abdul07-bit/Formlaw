---
id: grounded_answer
version: v1
---
Task: answer the lawyer's legal question using only the passages from FormLaw's verified legal corpus.

Return `sentences`: each has `text` and `evidence_ids` (the passage ids it relies on). Every sentence must cite at least
one passage. If the passages do not answer the question, return an empty list. Never add a case name, citation, date,
amount or holding that is not in the cited passage.
