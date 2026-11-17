# Data, licensing and provenance

## What is in this repository

| Asset | Status | Notes |
|---|---|---|
| `tasks/manifest.json` | ✅ measured | 111 task metadata records, regenerated from the pinned corpus |
| `leaderboard/data/tasks.json` | ✅ measured | lightweight index for the leaderboard filters |
| `leaderboard/data/results.csv` | ⬜ **PLACEHOLDER** | header + explicit placeholder row; no scores |
| `data/corpus/cases.jsonl` | ⬜ generated | fetched by `scripts/sync_corpus.py`, not committed |
| `data/croissant.json` | ✅ declared | MLCommons Croissant metadata (required by NeurIPS E&D since 2025) |

## What is deliberately NOT here

- **Verbatim prompt text.** It is fetched from `momozi1996/Code-Everything` on
  demand. This keeps a single source of truth and avoids redistributing
  third-party text without a per-record license check.
- **Reference HTML artifacts.** Each task pack records the URL instead. They are
  fetched at evaluation time and used only as an oracle for assertion validity
  and as a substrate for defect injection — never as a scoring target.
- **Model outputs, traces and scores.** These appear under `results/` only after
  the first real run. Publishing illustrative numbers would be indistinguishable
  from real ones once screenshotted.

## License chain

- Benchmark **code** in this repository: MIT (see `LICENSE`).
- Task **metadata**: derived from `Code-Everything`; per-record `author` and
  `license` fields are preserved in `tasks/manifest.json`.
- Original prompts, posts, demos and thumbnails: rights remain with their
  authors, under the terms recorded per record (default CC BY-NC 4.0 with a
  takedown channel in the source corpus).
- A takedown request can be opened as an issue on either repository; the
  affected task is removed from CE-Frozen and its removal is recorded in the
  changelog so published scores remain interpretable.

## Reproducibility pin

Published runs must pass `--ref <commit-hash>` to `scripts/sync_corpus.py`, not
`main`. The corpus commit hash is recorded in `cebench/config.py`
(`CORPUS_COMMIT`) and in the arXiv version's Data Availability statement.
