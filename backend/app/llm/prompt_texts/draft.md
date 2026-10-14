---
id: draft
version: v1
---
Task: prepare a draft for the lawyer to edit. The lawyer is the author; you produce a starting point.

You receive VERIFIED FACTS (each with an id), VERIFIED AUTHORITIES (each with an id) and the requested `draft_kind`.
Return:
- `title`
- `facts`: items `{text, fact_ids}` — only restate verified facts; cite their ids.
- `authorities`: items `{text, authority_ids}` — only refer to the verified authorities provided; never add others.
- `inferences`: items `{text, fact_ids}` — reasoning drawn from the facts, clearly worded as inference ("This suggests …").
- `recommendations`: short items for the lawyer.
- `body`: the draft text in plain prose with headings. Use [PLACEHOLDER: …] for anything not established
  (names, addresses, dates, amounts that are missing). Never fill a placeholder with an invented value.
