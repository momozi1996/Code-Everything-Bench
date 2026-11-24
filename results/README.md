# Results

One subdirectory per evaluated run. `outcomes.csv` is generated from committed
traces and artifacts by `scripts/run_evaluation.py` — **never hand-edited**.
A score may only be produced from a committed trace + committed artifact.

## Runs so far

| Run | Tier | Tasks | Model(s) | What it establishes |
|---|---|---|---|---|
| `2026-11-23-smoke-glm53flash` | Core-111 | 1 (`case-085`) | `z-ai/glm-5.3-flash` (target) + `deepseek/deepseek-v4.1-flash-1017` (judge) | First real M1 chain: 19 KB artifact, 12 370 tokens, L0 7/8, L1 7/10, `evaluation_ready=True`, Gate veto `core_interaction_unusable`. Judge post-processing added later: 2 verdicts, 0 PASS (`insufficient evidence` — no rendered screenshots). |
| `2026-11-24-e2e-180-smoke` | Core + Extended | 2 (`case-001`, `md-1445-A-03`) | `z-ai/glm-5.3-flash` (target) + `deepseek/deepseek-v4.1-flash-1017` (judge) | **End-to-end smoke of the 180-pack loader.** Runner reported `task bank: all (core 1 + extended 1)`. Core `case-001`: 34 KB artifact, `evaluation_ready=True`, score 0 (truncated at the token cap, L0 6/2). Feishu-sourced Extended `md-1445-A-03` (`has_reference_oracle=false`): complete 12.5 KB HTML, **PASS**, score 0.9663, F 0.923, L0 7/1, L1 8/0. `judge.csv`: 2 verdicts, both FAIL for missing screenshot evidence — a real verdict, not a fabricated PASS. |

These are **smoke runs, not leaderboard results**. They exist to prove that
generate → assert → score → trace → judge works for both tiers; they must never
be read as model scores. Model scores require the full matrix.

## Reproducing the 180-task smoke

`z-ai/glm-5.3-flash` is a reasoning model: with `reasoning_effort: low` and a
large `max_tokens` it can spend the whole output budget on hidden reasoning
tokens and stall for 20+ minutes. The committed smoke configs cap that
behaviour (`reasoning_effort: minimal`, `max_tokens: 16000`,
`timeout_seconds: 240`) without changing the model or the judge:

```
set -a; source .env; set +a
python3 scripts/run_evaluation.py --check \
  --models config/models.e2e-smoke.json --run config/run.e2e-smoke.json
python3 scripts/run_evaluation.py \
  --models config/models.e2e-smoke.json --run config/run.e2e-smoke.json
python3 scripts/judge_run.py --run 2026-11-24-e2e-180-smoke
```

Both configs are credential-free (they carry only `api_key_env` variable
names). The `.env` values stay local and git-ignored.

## Layout

```
results/<run-id>/
├── config.json          model id, harness id, exact version, seed, budget (sanitised)
├── traces/*.jsonl       full action/observation trace, one file per task
├── artifacts/*.html     delivered files, exactly as produced
├── delivery_notes/*.md  self-assessed completion + top-3 weak points (RQ5)
├── outcomes.csv         generated from traces — NEVER hand-edited
└── judge.csv            L2 visual-review verdicts (scripts/judge_run.py)
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
5. Report Core-111 and Extended-69 **separately**. Extended tasks have no
   reference oracle, so no meta-test pass rate may be computed over them and
   M2/M3 reference mutation does not apply. See `docs/benchmark-spec.md` §4.1.

## Why the leaderboard still ships a PLACEHOLDER banner

A benchmark whose central claim concerns unverified claims cannot publish a
table before the executions exist. Illustrative numbers would be
indistinguishable from real ones once screenshotted, so
`leaderboard/data/results.csv` stays explicitly `PLACEHOLDER` until the full
matrix is run.

The full matrix is **not** a single 111-task run: the bank is now
**Core-111 + Extended-69 = 180 packs** (`--task-set all`). The paper's headline
census remains Core-111 and is reproducible with `--task-set core`. Smoke runs
above are chain validation only; the scheduled full matrix is
180 tasks × N configurations × 3 repetitions, reported per tier.
See `docs/reproducibility.md` and `docs/expansion-report.md`.
