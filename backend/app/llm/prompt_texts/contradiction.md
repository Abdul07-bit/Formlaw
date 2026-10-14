---
id: contradiction
version: v1
---
Task: find contradictions between passages relevant to the lawyer's REQUEST: different dates, times, places, amounts or
people for the same event; statements that cannot both be true; inconsistent testimony; conflicting contract clauses.

Return `contradictions`, each with:
- `topic` (short, e.g. "Date of arrest"), `nature` (date | amount | statement | clause | identity | place | time)
- `a` and `b`: each `{passage_id, quote, value}` where `quote` is verbatim and `value` is the conflicting value as written
- `explanation`: one neutral sentence.

Only report genuine conflicts about the same thing. Two different events with different dates are not a contradiction.
