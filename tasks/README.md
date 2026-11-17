# Task bank

`manifest.json` contains **measured metadata for all 111 tasks**, regenerated
from the pinned corpus by `scripts/build_manifest.py`. It stores no prompt text
and no third-party artifact source — only fields, links and provenance.

## Census, not a sample

```
739  main-library records
305  have prompt text                     (reject 434)
111  have a runnable .html reference     (reject 194)
111  have xUrl + publishedAt             (reject 0 — verified, not filtered)
```

The library has 120 `.html` demos in total; nine of them belong to records
without prompt text and were already removed at the first gate. **120 is not a
funnel stage.**

## Evidence grades

| `promptStatus` | Count | Track |
|---|---:|---|
| `full` | 102 | strict-D1 main leaderboard (CE-Frozen) |
| `transcribed` | 3 | Replay, annotated |
| `repository` | 4 | Replay, annotated |
| `context` | 2 | Replay, annotated |

`promptStatus` is an **evidence grade**, not an admission gate. All 111 tasks
are built; only the strict-D1 subset supports the verbatim-prompt claim.

## Task pack format

Each full task package (one is shipped as an example) contains:

```
<task-id>/
├── task.json                  id, provenance, domains, evidence level
├── prompt.md                  provenance + requirement structure (text fetched, not vendored)
├── budget.json                30min / 15 rounds / token cap / network deny
├── assertions/task.json       L1 assertions compiled from the interaction model
├── mutations.json             D1–D6 injection configs + difficulty ladder
└── reference/SOURCE.md        URL of the runnable reference (not copied)
```

The shared **L0** suite lives in `cebench/assertions/global_suite.py` and is not
duplicated into task packages.

## Source skew (disclosed, not hidden)

100 of 111 tasks point to one collection
(`miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files`). Results must be
stratified by source collection; `modelLabel` records the model the original
poster used and is **not** a cross-model score. See paper §9.3.

## Domain counts (reporting only)

`code2Tags` is multi-label and has 155 observed combinations, so it is **not**
used as a sampling stratum. The manifest records both original tag counts and
an 8-domain reporting rollup. Balanced sampling uses the four orthogonal
dimensions (interaction span / execution span / trigger / deliverable form).
