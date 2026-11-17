# Reproducibility contract

A benchmark is an instrument, not a PDF. The following is what another person
must be able to do with this repository.

## 1. One command, three levels

```bash
# Level 1 — zero dependencies, verifies the instrument itself
python3 -m unittest discover -s tests -v
python3 -m cebench.cli selftest

# Level 2 — full browser mode, pinned environment
docker build -t cebench .
docker run --rm cebench python3 -m unittest discover -s tests -v

# Level 3 — regenerate the main table from committed traces
python3 scripts/reproduce_main_table.py --run <run-id>
```

Level 3 **refuses to run** while `leaderboard/data/results.csv` contains the
placeholder row. `python3 -m cebench.cli report` exits non-zero for the same
reason. This is intentional: an empty table is honest, an illustrative one is
not.

## 2. What is pinned

| Component | Pin | Why |
|---|---|---|
| Corpus | `CORPUS_COMMIT` in `cebench/config.py` + `--ref <hash>` | Task set must be immutable for a published version |
| Chromium / Playwright | `requirements.txt` + `Dockerfile` | `scrollWidth` and font metrics drift across browser versions and would change L0-04 outcomes |
| Viewports | 1440×900 desktop, 360×780 mobile | Responsive assertions need fixed device geometry |
| Budget | `budget.json` per task: 30 min / 15 rounds / 60k tokens / network deny | Without a budget, "delivery" degenerates into "eventually solvable" |
| Seeds | fixed per configuration; 3 repetitions | Retest reliability (ICC) requires controlled variance |
| Scoring | `0.35F + 0.30R + 0.20V + 0.15E` in `cebench/config.py` | Constants are code, not prose; CI checks them |

## 3. Submitted run format

```
results/<run-id>/
├── config.json          model id, harness id, exact version, seed, budget, cutoff date
├── traces/*.jsonl       one action/observation record per step, per task
├── artifacts/*.html     delivered files, byte-for-byte as produced
├── delivery_notes/*.md  self-assessed completion + top-3 weak points
└── outcomes.csv         GENERATED from traces, never hand-edited
```

Trace event schema: `{step, action, target, observation}`. Actions that count as
evidence: `browser_open`, `screenshot`, `console_read`, `assertion_run`,
`test_execute`, `state_probe`, `interaction`, `build`, `file_read`.

## 4. Maintainer audit (submission-based scaling)

The benchmark author does not run every model. Contributors submit artifacts
and traces; maintainers:

1. **Re-execute a 10% random sample** of each run in the pinned container.
2. **Audit unverified claims**: `claimed_checks − trace_verified_checks`. Any
   value > 0 sets Gate = 0.
3. **Verify the assertion meta-test** on each admitted task's reference
   implementation (`.github/workflows/meta-test.yml`).
4. Regenerate `results.csv`, leaderboard and all `[R#]` slots from the traces.

This makes leaderboard growth marginal-cost-free for the author while keeping
the author in the role of *standard setter* rather than *compute provider*.

## 5. Statistical reporting

- Bootstrap 95% CI on every aggregate (2000 resamples, fixed seed).
- Paired comparisons + permutation p-values, Cliff's δ effect size, Holm
  correction for multiple comparisons.
- Retest reliability ICC(2,1); inter-rater Cohen's κ / Fleiss' κ.
- IRT 2PL calibration; tasks with discrimination a < 0.5 removed after the
  pilot, so the final leaderboard size is decided by data.
- Significance groups (a/b/c): configurations sharing a letter are **not
  ordered** on the leaderboard.

Implementations live in `analysis/` and run on the standard library alone;
`numpy` / `scipy` are optional accelerators.

## 6. Versioning

| Change | Version action |
|---|---|
| Model configuration added | leaderboard row, no version bump |
| New weekly CE-Live tasks | `CE-Live-YYYY-Www` tag |
| Assertion or rubric corrected | **CE-Frozen minor version**, all historical scores recomputed and labelled |
| Task removed (takedown / IRT) | changelog entry with IDs; published scores remain interpretable |

The arXiv v1 title and the corpus commit hash are frozen together; see
`CITATION.cff` and the Data Availability statement in the manuscript.
