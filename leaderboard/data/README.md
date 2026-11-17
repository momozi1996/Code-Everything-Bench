# Leaderboard data

| File | Content | Status |
|---|---|---|
| `tasks.json` | 111 real task records + 8-domain counts | ✅ measured, generated |
| `results.csv` | one explicit `PLACEHOLDER_NO_RUN` row | ⬜ no results |

## Regeneration

```bash
python3 scripts/build_manifest.py --source data/corpus/cases.jsonl   # tasks.json
python3 scripts/reproduce_main_table.py --run <run-id>                 # results.csv (after a real run)
```

`results.csv` is **generated, never edited**. `cebench.cli report` deliberately
exits with an error while the placeholder row is present, so a placeholder table
cannot be accidentally published as a result.

## Column groups

- **Result** — `pass_at_budget` (binary main metric), `first_pass_rate`, `m2_f1`, `m3_regression_pass`
- **Process** — wall clock, repair rounds, tokens, `unverified_claims`, `time_to_first_runnable_s`, `self_check_actions`
- **Quality** — `F / R / V / E`, `quality_given_pass`, `cost_to_pass_usd`

Every published number carries `ci_low` / `ci_high` (bootstrap 95%) and a
`significance_group` letter. Configurations sharing a letter are **not ranked
against each other**: a small, non-significant point gap must not be rendered
as an ordering. This is the "perceptual resolution gap" the paper argues about,
applied to the benchmark's own presentation.
