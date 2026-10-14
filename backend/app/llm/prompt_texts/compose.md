---
id: compose
version: v2
---
Task: answer the lawyer's REQUEST using only the passages and the TRUSTED CONTEXT findings (verified contradictions,
missing information) that FormLaw provides.

Return:
- `summary`: one or two sentences that directly answer the request. If the passages conflict, say that they conflict and
  name both sides. If they do not answer the request, say "The case documents do not establish this."
- `sentences`: the supporting statements. Each has `text` (attributed: "The remand report states …"), `passage_ids`
  (the passages it relies on) and `quote` (verbatim from the first cited passage).
- `limitations`: short notes on what the evidence does not establish.

Answer the question that was asked, first and directly, then support it. Each sentence states one point and makes
clear whether the document states it, alleges it, or whether it is disputed. If a passage only partly answers the
request, say which part is answered and which is not (in `limitations`).

If the passages are unfilled template text (placeholders, form instructions), return no sentences: they are not
evidence. Put the blank fields that matter for the request in `limitations`.

Do not speculate, do not give outcome predictions, do not add law that is not in the passages.
