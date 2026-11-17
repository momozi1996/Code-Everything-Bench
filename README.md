# Code-Everything Bench

**Can Agents Deliver and Verify What Real Users Actually Ask For?**

> 中文主张句：**面向用户的最后一次真实考验**

[![Status: Pre-registration](https://img.shields.io/badge/status-pre--registration-blue)]()
[![Tasks: 111](https://img.shields.io/badge/tasks-111-green)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)]()

> **⚠️ NO RESULTS YET.** This repository is the companion artifact of a pre-registered study. Every number on the leaderboard is an explicit `PLACEHOLDER`. No model scores are published until the evaluation run defined in [`docs/benchmark-spec.md`](docs/benchmark-spec.md) has been executed and its traces are committed under `results/`. Filling in a score by hand is a violation of the benchmark contract.

---

## What this is

CE-Bench converts **naturally occurring community stress tests** into reproducible evidence. Its tasks are not written by researchers: they are verbatim prompts that real users posted on X when testing newly released models, each paired with a runnable single-file HTML reference implementation and a traceable original post.

It measures three separable constructs on the **same task bank**:

| Measurement | Input | Question | Primary metric |
|---|---|---|---|
| **M1 Generation** | prompt `p` | Can it deliver a runnable artifact within budget? | `Pass@Budget` (binary) |
| **M2 Verification** | mutated reference `Â_m` | Can it find defects in an artifact it did not write? | Precision / Recall / F1 |
| **M3 Repair** | `Â_m` + defect report | Can it fix them without regressions? | regression assertion pass rate |

The pre-registered, falsifiable claim is the **verification gap**: generation has saturated across frontier configurations, verification has not, the two orderings are weakly correlated, and self-calibration degrades with capability.

**Three properties that make this benchmark different:**

1. **Real-intent Grounding** — tasks come from organic demand, reproduced verbatim, with `publishedAt` timestamps that induce POST/PRE contamination splits.
2. **Artifact Completeness** — the unit of scoring is a self-contained single-file HTML artifact opened via `file://`; no build step, no CDN, no dependency resolution.
3. **Interactive Verification** — evidence comes from browser execution, harness-side runtime state probes, and interaction recordings, with **≥ 80% of the score derived from deterministic assertions** rather than LLM judging.

## Three numbers

| | |
|---|---|
| **111** | fully measurable tasks (a census, not a sample) |
| **8** | shared global assertions (L0), written once, applied to every task |
| **3** | measurement modes (M1 / M2 / M3) on the same task bank |

Construction ceiling, measured from the source corpus by `scripts/build_manifest.py`:

```
739 records → 305 (prompt text exists, reject 434) → 111 (runnable .html reference, reject 194)
             → 111 (traceability check: xUrl + publishedAt on 111/111, reject 0)
```

The library contains 120 `.html` demos in total, but nine of those records have no prompt text and were already removed at S1 — **120 is not a funnel stage**. No task is synthesized, no task is sampled, and no task is removed for traceability. See [`docs/benchmark-spec.md`](docs/benchmark-spec.md#4-construction-funnel).

## Quickstart (zero dependencies)

```bash
git clone https://github.com/momozi1996/Code-Everything-Bench.git
cd Code-Everything-Bench
python3 -m unittest discover -s tests -v       # runs the L0 assertion suite + scoring tests
python3 -m cebench.cli selftest                 # prints the contract and validates all task packs
python3 -m cebench.cli verify tasks/ce-085-karesansui/artifact.html   # score one artifact (static mode)
```

The core package uses **only the Python standard library**, so a fresh clone can be validated immediately. Installing `requirements.txt` enables the full browser mode (`playwright`), YAML task specs (`PyYAML`), and the statistical analysis (`numpy` / `scipy`). Without Playwright, `cebench` runs static assertions and reports `browser_unavailable` explicitly — it never claims to have executed a check it did not execute.

```bash
pip install -r requirements.txt
playwright install chromium
python3 scripts/reproduce_main_table.py --check   # full reproduction contract (requires results/)
```

## Running a real evaluation — you supply the keys

The repository ships **templates and scripts only**. No API key, no base URL and
no model result is committed. Fill them in locally when you are ready:

```bash
cp config/models.example.json config/models.json   # git-ignored: base_url, model, api_key_env
cp config/run.example.json   config/run.json       # git-ignored: task set, repetitions, budget, split
cp .env.example              .env                  # git-ignored: the actual key values
set -a; source .env; set +a

python3 scripts/sync_corpus.py --ref <commit-hash>     # fetch verbatim prompts (not vendored)
python3 scripts/run_evaluation.py --check               # validate config; no API call
python3 scripts/run_evaluation.py --dry-run             # rehearse offline; writes nothing
python3 scripts/run_evaluation.py --task case-001 --limit 1   # one real generation
python3 scripts/run_evaluation.py                       # full 111 x N x 3 batch
```

Supported protocols: **`openai-compatible`** (OpenAI, vLLM/SGLang, Ollama shim,
most gateways) and **`anthropic`**. Each entry names an environment variable via
`api_key_env`; a literal key anywhere in the config is rejected by validation.
`--dry-run` uses a stub client whose output is explicitly non-scoreable, so a
rehearsal can never leak into the leaderboard. Without a pinned Chromium,
runtime assertions return `SKIP` and **no score is written**.

Outputs land in `results/<run-id>/` (artifacts, traces, delivery notes,
`outcomes.csv`, and a **sanitised** `config.json` with no key values). Then
`python3 scripts/reproduce_main_table.py --run <run-id>` regenerates the
leaderboard. Full field reference: [`config/README.md`](config/README.md).

## Repository layout

```
├── cebench/                  core package (stdlib only)
│   ├── assertions/           L0 global suite, L1 task loader, harness-side state probe
│   ├── scoring/              Gate (5 vetoes), Cap, F/R/V/E rubric, aggregation formula
│   ├── defect/               D1–D6 parameterized mutation operators
│   ├── runner.py             L2 sandbox interface + trace collection
│   ├── trace.py              trace schema and unverified-claim audit
│   └── cli.py                `cebench verify | score | selftest | report`
├── tasks/
│   ├── manifest.json         measured metadata for all 111 tasks
│   └── ce-085-karesansui/    one complete example task pack
├── scripts/                  corpus sync, manifest build, one-command reproduction
├── analysis/                 IRT (2PL), inter-rater agreement, bootstrap / effect sizes
├── config/                   API + run templates (filled-in copies are git-ignored)
├── cebench/providers.py      unified API client (openai-compatible / anthropic / dry-run)
├── cebench/generate.py       M1 generation, delivery-note parsing, trace events
├── cebench/evaluation.py     run orchestration -> sanitised results/<run-id>/
├── tests/                    runnable fixtures (pass + targeted failures)
├── leaderboard/              static site + CSV — all values PLACEHOLDER until first run
├── docs/
│   ├── benchmark-spec.md     protocol summary aligned with the paper §3–§5
│   ├── figure-audit.md       element-by-element parity check against GameCraft-Bench
│   ├── reproducibility.md    one-command reproduction contract
│   └── figures/              six figure specs (mermaid + layout + data provenance)
├── data/croissant.json       Croissant dataset metadata (NeurIPS E&D requirement)
└── .github/workflows/        CI: unit tests + assertion meta-test gate
```

## Relation to the source corpus

This repository is the **evaluation layer**; [`momozi1996/Code-Everything`](https://github.com/momozi1996/Code-Everything) is the **case library**. The two are deliberately separate: the case library serves browsing, this repository serves reproduction. `scripts/sync_corpus.py` pulls a pinned commit from the case library and rebuilds `tasks/manifest.json`, so there is a **single source of truth** — no duplicated prompt text.

Third-party reference implementations are **not vendored**. Each task pack records the reference URL in `reference/SOURCE.md` and the runner fetches it on demand, respecting the original license and attribution.

## Status

| Component | State |
|---|---|
| Task bank metadata (111 tasks, real fields) | ✅ committed |
| L0 global assertion suite (8 rules) + runnable fixtures | ✅ committed, tested |
| Gate / Cap / rubric / aggregation formula | ✅ committed, tested |
| **Model API input layer (config templates + env-var keys + provider clients)** | ✅ committed, tested — **you fill in key / base_url / model** |
| **Generation + run orchestration scripts** | ✅ committed — `--check` / `--dry-run` / real batch |
| Harness-side state probe, D1–D6 mutation operators | ✅ implemented (task-specific configs pending) |
| Trace schema, unverified-claim audit | ✅ implemented |
| Leaderboard site, filters, drill-down | ✅ implemented, **PLACEHOLDER data** |
| 111 task-specific L1 assertion packs | ⬜ pipeline in progress |
| 111 mutation configs + reference self-check | ⬜ pipeline in progress |
| Model runs (M1/M2/M3) and `[R#]` result slots | ⬜ first run scheduled 2027-Q1 |
| arXiv preprint / journal submission | ⬜ |

## Citation

```bibtex
@misc{cebench2027,
  title  = {Code-Everything Bench: Can Agents Deliver and Verify What Real Users Actually Ask For?},
  author = {momozi1996},
  year   = {2027},
  note   = {Pre-registration and benchmark artifact},
  url    = {https://github.com/momozi1996/Code-Everything-Bench}
}
```

See [`CITATION.cff`](CITATION.cff). **The title is frozen from arXiv v1 onward** to keep Google Scholar version clustering intact.

## License

Code: [MIT](LICENSE). Task metadata: derived from `Code-Everything`, attribution and per-record license fields are preserved in `tasks/manifest.json`; original prompts and artifacts remain under their respective authors' terms. See [`data/README.md`](data/README.md).
