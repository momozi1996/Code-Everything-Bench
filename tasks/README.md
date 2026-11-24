# Task bank

Two manifests, two tiers, **180 materialised task packs** total:

| Manifest | Tasks | What it is |
|---|---:|---|
| `manifest.json` | 111 | **Core-111** — the paper's full-measurement census; every task has a pinned runnable `.html` reference |
| `manifest_extended.json` | 69 | **Extended-69** — label-balanced tier admitted on verbatim-prompt evidence alone (`has_reference_oracle=false`, meta-test `N/A`) |

`manifest.json` is regenerated from the pinned corpus by
`scripts/build_manifest.py`; `manifest_extended.json` by
`scripts/expand_tasks.py` (fed by `scripts/import_feishu_md.py`). Manifests
store no prompt text and no third-party artifact source — only fields, links
and provenance. Three-axis labels for all 180 live in `taxonomy.json`; the
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
Extended-69 (63 admitted) — see below.

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
complete for all 180. Runs must report the two tiers separately.

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

All **180** packages are materialised (`scripts/build_task_packs.py`, with
`--extended-only` for the 69):

```
<task-id>/
├── task.json                  id, provenance, domains, evidence level,
│                              set / reference_kind / has_reference_oracle
├── prompt.md                  verbatim prompt, materialised from the pinned
│                              corpus or the Feishu export (text, not vendored artifacts)
├── budget.json                30min / 15 rounds / token cap / network deny
├── assertions/task.json       L1 assertions compiled from the interaction model
├── assertions/meta_test.json  reference-as-oracle result, or `not_applicable`
├── mutations.json             D1–D6 injection configs + difficulty ladder
└── reference/SOURCE.md        URL of the runnable reference, or post-only evidence
```

The shared **L0** suite lives in `cebench/assertions/global_suite.py` and is not
duplicated into task packages.

## Running the two tiers

The runner loads prompts from the packs themselves
(`cebench/evaluation.py::load_prompts_from_packs`), so all 180 are reachable:

```
python3 scripts/run_evaluation.py                  # all (default) = 180
python3 scripts/run_evaluation.py --task-set core      # paper census = 111
python3 scripts/run_evaluation.py --task-set extended  # 69
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
