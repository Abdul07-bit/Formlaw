# Evaluation

`npm run eval` (or `python scripts/evaluate.py [--with-llm] [--out report.json]`) runs FormLaw's labelled evaluation set
against a throwaway database and re-checks the output independently of the agents. The same metrics gate CI in
`backend/tests/evaluation/test_evaluation.py`.

## Data (`backend/app/evaluation/dataset.py`, synthetic)

* **17 labelled claims** for the verifier: supported, contradicted (date / section), unsupported (wrong amount,
  invented confession), partially supported, no evidence, fabricated citations.
* **9 end-to-end scenarios**: conflicting arrest dates, "which document establishes…", missing referenced records, a fact
  absent from the record, witness identification, a malicious affidavit, a fake authority, a contract with conflicting
  notice periods, an ambiguous question.

## Metrics

| Metric | How it is measured | Gate | Deterministic mode (2026-10-09) |
|---|---|---|---|
| Verifier accuracy / false SUPPORTED | labelled claims | ≥ 0.9 / 0 | 1.0 / 0 |
| Groundedness | answer statements SUPPORTED/PARTIAL **and** cited | 1.0 | 1.0 |
| Citation correctness | each cited quote re-found verbatim in the stored chunk (database re-read) | 1.0 | 1.0 |
| **Fabricated citations** | legal citations in any answer/draft not present in evidence or verified authorities | **0** | **0** |
| Retrieval precision / recall | cited documents vs gold documents | ≥ 0.6 / ≥ 0.8 | 0.83 / 0.86 |
| Contradiction detection | expected conflicts found | 1.0 | 1.0 |
| Missing-information detection | expected referenced records flagged | 1.0 | 1.0 |
| Injection resistance | security finding raised and no injected content in the answer | pass | pass |
| No fabricated facts / authorities | absent fact not asserted; fake authority not generated | pass | pass |
| Completed runs, latency, tokens | per scenario | all complete | 9/9 · p50 47 ms · 0 tokens |

Model mode has not been measured yet (it makes billed calls). Run it with `--with-llm` and compare: groundedness and
citation correctness must stay at 1.0 and fabricated citations at 0; extraction recall is where a model should improve.
