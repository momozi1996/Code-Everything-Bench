# Results

**Empty by design.** No model has been run yet. This directory will hold one
subdirectory per evaluated run:

```
results/<run-id>/
├── config.json          model id, harness id, exact version, seed, budget
├── traces/*.jsonl       full action/observation trace, one file per task
├── artifacts/*.html     delivered files, exactly as produced
├── delivery_notes/*.md  self-assessed completion + top-3 weak points (RQ5)
└── outcomes.csv         generated from traces — NEVER hand-edited
```

## Rules

1. A score may only be produced by `scripts/reproduce_main_table.py` from a
   committed trace and a committed artifact.
2. `leaderboard/data/results.csv` is regenerated, never typed.
3. Maintainers re-execute a **10% random sample** of each submitted run and
   audit `unverified_claims = claimed_checks - trace_verified_checks`. Any
   value > 0 triggers the Gate veto (`artifact_does_not_load` / `unverified_claims`).
4. Result slots `[R0]`–`[R11]` in the manuscript are filled from these files by
   `analysis/` scripts. Placeholder values in the paper are explicit.

## Why an empty results directory is a feature

A benchmark whose central claim concerns unverified claims cannot publish a
table before the executions exist. The leaderboard therefore ships with an
explicit `PLACEHOLDER` banner rather than illustrative numbers: illustrative
numbers would be indistinguishable from real ones once screenshotted.

First full run is scheduled for 2027-Q1 (111 tasks × 5 configurations × 3
repetitions). See `docs/reproducibility.md`.
