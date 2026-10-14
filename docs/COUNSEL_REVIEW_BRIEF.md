# Brief for regulatory counsel

**Purpose:** obtain a written opinion on FormLaw's client–advocate connection model and data handling before launch.
This brief describes what the software does today. It is not legal analysis; the questions are for counsel to answer.

## 1. What FormLaw does

FormLaw is a technology platform (not a law firm). Clients describe a legal problem; advocates manage matters in a
secure workspace with AI assistance. A **connection feature** lets a client find and contact a verified advocate. That
feature is **switched off** in the software until a compliance reviewer approves a written policy that cites your opinion.

## 2. Questions on advocate advertising and solicitation

References to check: Bar Council of India Rules, Part VI, Chapter II (in particular rule 36); Advocates Act, 1961; any
current BCI or Ministry of Law and Justice guidance (the product brief cites an August 2024 release — please confirm it).

1. **Directory.** May the platform publish a list of verified advocates? If yes, which fields may be shown? (The software
   can restrict this to any subset of: city, state, courts, languages, education, qualifications, bio, years of
   practice, verified practice areas, judicial-status flag, whether accepting clients, consultation fee.)
2. **Suggestions.** May the platform suggest advocates for a client's matter using only verified practice area,
   location and language, listed without ranking? Or must the client search/choose without any suggestion?
3. **Client-initiated request.** May a client send their matter summary to an advocate they choose through the platform?
4. **Fees.** May consultation fees be displayed?
5. **Business model.** Which of these would be impermissible: subscription fees charged to advocates; per-matter fees;
   fees charged to clients? (The software has no paid placement, paid ranking or referral fees, and none can be enabled.)
6. **Disclosures.** What must a client be told before sharing a matter? (Current demo text is in
   `database/seeds/seed.py` → `DEMO_DISCLOSURES`.)
7. **Profiles.** Are there restrictions on what an advocate may write in their own profile bio/headline?

## 3. Questions on data protection (DPDP Act, 2023)

8. Is FormLaw a Data Fiduciary for client intake data, the advocate's matter data, or both? What is the advocate's role?
9. What notice and consent text is required at intake, before sharing with an advocate, and for AI processing?
10. Retention: for how long may intake data be kept if no advocate is engaged? Matter data after closure?
11. Processing by AI model providers outside India: what is required (contracts, notice, restrictions)?
12. Advocate verification: may we collect government ID copies? (Biometric/selfie checks were removed pending advice.)

## 4. Questions on legal data

13. Supreme Court judgments are ingested from a CC-BY-4.0 dataset (a third-party mirror of eCourts data, labelled
    non-authoritative). Is reliance on Copyright Act s.52(1)(q)(iv) plus the CC-BY licence sufficient for commercial use?
14. India Code and the eCourts judgment portal restrict automated access. What licensed or permitted route is available?

## 5. How your answers are recorded

An administrator drafts a ConnectionPolicy matching your opinion (features on/off, visible fields, fees, disclosures,
rules relied on). A separate compliance reviewer approves it, entering your opinion reference and confirming you
reviewed that exact version. Any change requires a new version and a new approval; a policy can be revoked instantly.
Every step is audited (`docs/DECISIONS.md`, D-004 and D-008).
