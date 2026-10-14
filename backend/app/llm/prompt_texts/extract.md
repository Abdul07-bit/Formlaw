---
id: extract
version: v2
---
Task: extract structured case knowledge from the passages for the lawyer's REQUEST (focus topics, if given, come first).

Return lists (each item cites `passage_id` and a verbatim `quote` from that passage):
- `parties`: name, role (accused, complainant, petitioner, respondent, witness, investigating officer, buyer, seller, employer, …)
- `facts`: statements of fact made in the documents. `kind` is one of fact | allegation | admission | disputed | procedural.
  Write `text` as a neutral sentence that attributes the source: "The FIR states that …", "The remand report records …".
- `events`: dated events for a timeline. `date_text` exactly as written; `date_iso` (YYYY-MM-DD) only when the date is
  unambiguous, otherwise empty; `event_type` short label (arrest, fir_registered, seizure, hearing, notice, payment, …).
- `issues`: legal or factual issues the documents raise, phrased as questions. Only cite statutes/sections that appear in the passage.
- `uncertainties`: things the documents leave unclear.
- `case_details`: identifying details exactly as written — `field` is case_number | court | jurisdiction | case_type |
  police_station | procedural_status | provision (a statute section or article the document itself cites). case_type is the
  nature of the proceeding (e.g. "criminal complaint", "bail application", "civil suit"), never the case title; `value` must
  appear in the `quote`. Omit any detail the passages do not state.

Never state that something happened if the documents only allege it — use kind=allegation and attribute it.
Never extract a placeholder ("[Full Name]", "[DD/MM/YYYY]", "[Names]") or a form instruction as a party, fact, event or
issue. Leave the list empty rather than fill it with template text.
