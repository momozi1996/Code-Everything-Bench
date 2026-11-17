# Contributing

## The one rule

**Never write a result by hand.** Every number in `leaderboard/` and `results/` is produced by a script from a committed trace. A submission containing a manually entered score is rejected, because it would be exactly the failure mode this benchmark measures (an unverified claim).

## Adding a task

1. Add a directory under `tasks/<task-id>/` with `task.json`, `prompt.md`, `budget.json`, `assertions/task.json`, `mutations.json`, `reference/SOURCE.md`.
2. Rebuild the manifest: `python3 scripts/build_manifest.py`.
3. **The meta-test gate must pass**: all L0+L1 assertions must pass on the reference implementation before the task can enter scoring. Run `python3 scripts/reproduce_main_table.py --check` or let CI do it.
4. Open a PR. CI runs `.github/workflows/meta-test.yml`; a failing task cannot merge.

Assertion authoring protocol (from the paper §4.3): extract candidate assertions from the prompt and the reference implementation's interaction model; classify each as `auto-assertable`, `state-probe`, or `visual-only`; the first two must total ≥ 8 for full-measurement admission. Reference-implementation self-check is a test of the *assertions*, not of the model — if a known-good artifact fails, fix the assertion.

## Submitting an evaluation run

Runs are submitted as artifacts, not scores:

```
results/<run-id>/
├── config.json          model, harness, exact version, seed, budget
├── traces/*.jsonl       full execution trace (every action + observation)
├── artifacts/*.html     delivered files
└── outcomes.csv         per-task assertion outcomes (generated)
```

Then `python3 scripts/reproduce_main_table.py --run <run-id>` regenerates the leaderboard. Maintainers re-execute a 10% sample and audit `unverified_claims = claimed_checks - trace_verified_checks`; any value > 0 triggers the Gate veto.

## Adding a mutation operator

Operators live in `cebench/defect/operators.py` and must be registered in `cebench/defect/taxonomy.md` with a **source of evidence**: a real failed case from the corpus or a published failure mode. An operator invented without such evidence will be rejected — the defect taxonomy is a contribution claim, not a convenience list.

## Reporting a benchmark defect

Open an issue with the label `benchmark-defect` and classify it as one of: task ambiguity, unquantifiable rubric, model capability, or agent behaviour. This four-way attribution is part of the published methodology; the defect rate is reported in the paper.
