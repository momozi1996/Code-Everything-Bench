# Task bank

Two manifests, two tiers, **258 materialised task packs** total:

| Manifest | Tasks | What it is |
|---|---:|---|
| `manifest.json` | 111 | **Core-111** — the paper's full-measurement census; every task has a pinned runnable `.html` reference |
| `manifest_extended.json` | 147 | **Extended-147** — tier admitted on verbatim-prompt evidence alone (`has_reference_oracle=false`, meta-test `N/A`) |

`manifest.json` is regenerated from the pinned corpus by
`scripts/build_manifest.py`; `manifest_extended.json` by
`scripts/expand_tasks.py` (fed by `scripts/import_feishu_md.py`) and appended by
`scripts/import_x_batch.py` for the 2026-11-25 X / Vibe3D batch. Manifests
store no prompt text and no third-party artifact source — only fields, links
and provenance. Three-axis labels for all 258 live in `taxonomy.json`; the
browsable catalogue is `docs/task-catalog.{html,md,csv}`.

Rationale, selection method and before/after label distributions:
[`docs/expansion-report.md`](../docs/expansion-report.md).

## Core-111 census, not a sample

```
739  main-library records
305  have prompt text                     (reject 434)
111  have a runnable .html reference     (reject 194)
111  have xUrl + publishedAt             (reject 0 — verified, not filtered)
```

The library has 120 `.html` demos in total; nine of them belong to records
without prompt text and were already removed at the first gate. **120 is not a
funnel stage.** The 194 records rejected at S2 are the candidate pool for
the 2026-11-23 Extended-69 expansion (63 admitted) — see below.

All paper numbers (funnel, Table 9, §7 stratified reporting, figure captions)
refer to **Core-111 only** and are unchanged by the extension.

## Extended-69 (label balancing)

Records with a verbatim prompt but no pinned `.html` reference — 63 from the
S2-rejected corpus plus 6 newly parsed from a Feishu prompt export. Selection
minimised the squared coefficient of variation of the `primary` / `track` /
`tech` label counts. Extended tasks carry `has_reference_oracle=false` and
`meta_test_applicable=false`: they **do not** enter the meta-test pass-rate
denominator and have no M2/M3 reference-mutation path. L0/L1 assertions still
run against every generated artifact, so M1 generate → assert → score is
complete for all 258. Runs must report the two tiers separately.

## 2026-11-25 X / Vibe3D batch (+78)

The owner supplied 115 additional rows (A-01..A-36, H-01..H-80) and chose
"scale B": admit every row with a *complete verbatim prompt* whose deliverable
a single-file HTML artifact can carry. `scripts/triage_x_batch.py` is the
read-only gate (84 rows pass: 53 full + 31 short-but-complete); 6 of those
hashes were already in the 180-task bank, so `scripts/import_x_batch.py`
admits **78** new tasks → Extended 147, total 258. The 31 rejected rows and
their reasons are listed in `docs/x-batch-triage.md`; the admitted rows live in
`data/corpus/x_batch_2026-11-25.jsonl`.

Two deliberate deviations, both approved by the owner:

* **`short_verbatim` tier** — a complete verbatim prompt shorter than the
  80-char extended-set floor is admissible with
  `prompt_status = short_verbatim` (30 of the 78). The floor was designed to
  reject rows with *no* prompt, not short instructions.
* **No CV² pruning** — this batch is 3D/game/animation heavy and worsens
  three-axis balance. No label was hard-assigned to fix the skew.

All 78 are `post-only` (`has_reference_oracle=false`,
`meta_test_applicable=false`, `meta_test=N/A`), so they do not enter the
meta-test pass-rate denominator. Full details:
[`docs/x-batch-import-report.md`](../docs/x-batch-import-report.md).

## Evidence grades (Core-111)

| `promptStatus` | Count | Track |
|---|---:|---|
| `full` | 102 | strict-D1 main leaderboard (CE-Frozen) |
| `transcribed` | 3 | Replay, annotated |
| `repository` | 4 | Replay, annotated |
| `context` | 2 | Replay, annotated |

`promptStatus` is an **evidence grade**, not an admission gate. All 111 Core
tasks are built; only the strict-D1 subset supports the verbatim-prompt claim.

## Task pack format

All **258** packages are materialised (`scripts/build_task_packs.py`, with
`--extended-only` for the 147):

```
<task-id>/
├── task.json                  id, provenance, domains, evidence level,
│                              set / reference_kind / has_reference_oracle
├── prompt.md                  verbatim prompt, materialised from the pinned
│                              corpus or the Feishu export (text, not vendored artifacts)
├── budget.json                120min / 15 rounds / 512000-token cap / network deny
├── assertions/task.json       L1 assertions compiled from the interaction model
├── assertions/meta_test.json  reference-as-oracle result, or `not_applicable`
├── mutations.json             D1–D6 injection configs + difficulty ladder
└── reference/SOURCE.md        URL of the runnable reference, or post-only evidence
```

The shared **L0** suite lives in `cebench/assertions/global_suite.py` and is not
duplicated into task packages.

## Running the two tiers

The runner loads prompts from the packs themselves
(`cebench/evaluation.py::load_prompts_from_packs`), so all 258 are reachable:

```
python3 scripts/run_evaluation.py                  # all (default) = 258
python3 scripts/run_evaluation.py --task-set core      # paper census = 111
python3 scripts/run_evaluation.py --task-set extended  # 147
python3 scripts/run_evaluation.py --task <task-id>     # one task, either tier
```

## Source skew (disclosed, not hidden)

100 of the 111 Core tasks point to one collection
(`miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files`). Results must be
stratified by source collection; `modelLabel` records the model the original
poster used and is **not** a cross-model score. See paper §9.3.

## Domain counts (reporting only)

`code2Tags` is multi-label and has 155 observed combinations, so it is **not**
used as a sampling stratum. The manifest records both original tag counts and
an 8-domain reporting rollup. Balanced sampling uses the four orthogonal
dimensions (interaction span / execution span / trigger / deliverable form).
