# CE-Bench protocol summary

Companion to the manuscript `Can Agents Deliver and Verify What Real Users
Actually Ask For?`. This file is the **implementer's view**: what the code in
this repository must enforce. Where a rule and the paper disagree, the paper's
§3–§5 formulation is authoritative and the code must be corrected.

## 1. What is measured

Three separable constructs, on the *same* task bank:

| Construct | Input | Output | Metric |
|---|---|---|---|
| Generation **G** (M1) | prompt `p` | artifact `A` | `Pass@Budget` (binary) |
| Verification **V** (M2) | `(p, Â_m)` | defect list `D̂` | Precision / Recall / F1 vs known `D` |
| Repair **R** (M3) | `(p, Â_m, D̂)` | `Â′` | regression assertion pass rate |
| Calibration **C** | delivery note, trace, observation | self-score `s`, weak points `W` | ECE / top-3 hit rate |

M2 is independent of M1 by construction: the artifact inspected is a **mutated
reference implementation**, not the model's own output, so generation ability
cannot substitute for verification ability and ground truth is exact.

## 2. Three desiderata

Derived from the three spaces of the evaluation problem; jointly complete over
the success path, each with a refutation in the paper §3.3.

- **D1 Real-intent Grounding** — task space: verbatim community prompts, `publishedAt` present.
- **D2 Artifact Completeness** — artifact space: a single self-contained HTML file, `file://` openable.
- **D3 Interactive Verification** — evidence space: browser execution, runtime state, interaction recordings.

## 3. Information boundary

The configuration observes `(p, ℰ)` but **not** the hidden rubric `ρ`.
Publication policy: `ρ_L0` is public (8 global assertions are downloadable),
`ρ_L1` is released with each task pack, `CE-Hidden` keeps its rubric hidden.
Public L0 is a deliberate departure from GameCraft-Bench's fully hidden rubric:
it enables community auditing of the deterministic majority of the score, at
the cost of some checklist gaming (discussed in paper §3.6).

## 4. Construction funnel

Measured by `scripts/build_manifest.py` from the pinned `cases.jsonl` — not
estimated, not sampled.

| Stage | Rule | Remaining | Rejected |
|---|---|---:|---:|
| Source | main library | 739 | — |
| **S1** | `prompt` field non-empty | 305 | 434 (426 `unavailable` + 8 `demo`) |
| **S2** | `demoUrl` is a loadable `.html` reference | **111** | 194 |
| **S3** | verify `xUrl` + `publishedAt`; assign evidence grade | **111** | 0 |
| S4 | ≥8 auto/state-probe assertions + CI meta-test | `[R1]` | `[R1]` |
| S5 | three reviewers, Fleiss' κ ≥ 0.6 | `[R1]` | `[R1]` |
| S6 | IRT calibration (2PL, discrimination a ≥ 0.5) | `[R1]` | `[R1]` |

**The 120 trap.** The library contains 120 `.html` demos in total, but nine of
those records have no prompt text and are already removed at S1. Therefore 120
is *not* an intermediate funnel stage, and there is no "reject 9" stage: all
111 admitted tasks carry both `xUrl` and `publishedAt`. Mixing a whole-library
statistic with a conditional one produces a funnel that the corpus's own
validator contradicts (paper `design-decisions.md` #22).

**`promptStatus` is an evidence grade, not a gate.** 102 `full` → strict-D1 main
leaderboard; 9 (`transcribed` 3, `repository` 4, `context` 2) → Replay with an
evidence-completeness label. All 111 are built.

**Source skew (disclosed).** 100/111 point to one Opus collection. Results are
stratified by source; `modelLabel` is the original poster's model, not a score.

### 4.1 Two-tier task bank (v0.2)

The funnel above defines **Core-111**, the paper's full-measurement census:
every admitted task has a pinned runnable `.html` reference, so a
reference-as-oracle meta-test is meaningful and POST/PRE coverage is 111/111.
All paper numbers (Table 9, §7 stratified reporting, figure captions) refer to
this tier and are unchanged.

A second tier, **Extended-69**, was added to reduce label skew
(`tasks/manifest_extended.json`; see `docs/expansion-report.md`). It admits
records that have a verbatim prompt but no pinned `.html` reference — 63 from
the 194 records rejected by S2, plus 6 newly parsed from a Feishu prompt
export. Selection minimised the squared coefficient of variation of the
`primary` / `track` / `tech` label counts. The full bank is **180** packs.

Extended tasks have `has_reference_oracle=false` and
`meta_test_applicable=false`. They **do not** enter the meta-test pass-rate
denominator, and the M2/M3 reference-mutation path is not available for them.
L0/L1 assertions still run against every generated artifact, so M1
generation → assert → score is complete for all 180 tasks. Runs must report the
two tiers separately; the paper's headline census remains Core-111 unless
explicitly restated as two-tier.

## 5. Assertion tiers

| Tier | Count | Nature | Cost |
|---|---:|---|---|
| **L0** global | 8 | static source checks (6) + browser runtime (2) | written once, all 180 tasks |
| **L1** task-specific | 4–12 | Playwright interaction scripts + harness-side state probes | per task, from 8 domain templates |
| **L2** visual | closed questions | multimodal judge on interaction recordings | only for passing runs / top configurations |

L0 rules: single file & no external resources · DOCTYPE + viewport · zero
console errors under `file://` · no horizontal overflow at 360px ·
`requestAnimationFrame` animation · `prefers-reduced-motion` · pointer/keyboard
parity · Web Audio gated by a user gesture.

**Four statuses**: `PASS`, `FAIL`, `SKIP`, `NA`. SKIP means a check could not
run (e.g. no Playwright) and is never converted to PASS. The score denominator
is the **effective assertion count** (PASS + FAIL); NA and SKIP are reported
separately so tasks with different assertion counts are not implicitly weighted.

**Harness-side probes.** Requiring the artifact to expose `window.__state` is
not feasible for third-party reference code or model output. The evaluator
injects read-only observation code (global scan, canvas pixel hash, API usage
counters) and infers state from pre/post interaction deltas. Evidence grades:
E1 explicit state, E2 behavioural, E3 pixel, E0 none. DOM-only scoring was
measured as nearly uncorrelated with true state correctness (WorldCoder-Bench,
Kendall τb = −0.02).

## 6. Scoring

```
Score = 1[Gate] × min(0.35·F + 0.30·R + 0.20·V + 0.15·E, Cap)
```

**Generation contract (v0.7).** Every target runs with a single output cap of
**512,000 tokens** (`TARGET_MAX_TOKENS`), a 3600 s per-request timeout and a
120-minute wall-clock budget; the judge stays at 8192 tokens. The cap is a
ceiling, not a target, and is identical across models and across both harness
regimes so it cannot explain a leaderboard difference. Cost is deliberately
not optimised for the full 180-task batch. `finish_reason=length` and
`completion_tokens >= cap` are recorded as `truncated`.

- **Gate** (multiplicative veto, five rules): does not load · core interaction
  unusable · unverified claims · forbidden shortcut (e.g. static image posing
  as 3D) · no deliverable file. Any hit → `Pass@Budget = 0`.
  - *does not load* (v0.6) requires a **complete** document: a missing closing
    `</html>`/`</body>` or a browser that could not open the file. A token-
    truncated artifact is attributed here (`truncated` flag), not to the
    interaction rule.
  - *core interaction unusable* (v0.6) is driven **only** by runtime
    interaction probes (`interaction_delta`, `selector_exists`): zero PASS
    among them is a veto. Static `source_contains` / `source_absent` failures
    are requirement signals; they reduce F/R/E through the rubric but must not
    zero the run. See `docs/assertion-review.md`.
- **Cap** applies only to *passing* runs; it compresses quality among delivered
  artifacts and never contaminates the binary main metric. A *partly* failing
  runtime probe set (some PASS, some FAIL) sets `core_interaction_degraded`
  and caps quality at 0.5; an all-failing set is a Gate veto instead.
- **Deterministic mass** = F + R + E = **0.80** by construction, enforced by
  `cebench.scoring.assert_verifiability_budget()` in CI. This turns the
  "verifiability budget" from a policy into a property of the formula.

**Four reported numbers**, never merged: `Pass@Budget` (main), `Quality | Pass`
(conditional), `Cost-to-Pass` (efficiency), and the failure-class distribution
(diagnostic). The leaderboard adds process metrics but never ranks by a total.

**Unverified claims.** `claimed_checks − trace_verified_checks > 0` triggers the
Gate. A delivery note saying "tested in browser" is a claim; a screenshot event
in the trace is evidence. See `cebench/trace.py`.

## 7. Modes, tracks and contamination

- **Modes**: `Replay` (verbatim prompt, evidence-annotated), `Rebuild`
  (structured spec), `Transfer` (same capability structure, new theme).
- **Tracks**: `CE-Frozen` (versioned, comparable), `CE-Live` (rolling, 25%
  weekly refresh to resist overfitting), `CE-Hidden` (transfer audit).
- **POST / PRE**: for each configuration, split by `publishedAt` vs its stated
  training cutoff. Main results on POST; the POST−PRE gap is an upper-bound
  contamination estimate. Coverage is 111/111, so no task is lost.

## 8. Judge protocol and agreement thresholds

Deterministic assertions decide gates and the majority of the score. A judge is
used only where no rule can be written, and is subject to:

| Check | Threshold |
|---|---|
| judge accuracy on known-defect calibration set | ≥ 0.85 to be activated |
| human vs deterministic assertion (Cohen's κ) | ≥ 0.90 (a failure here is an **assertion bug**) |
| human vs judge (Cohen's κ) | ≥ 0.70 (else the judge may not score) |
| three reviewers (Fleiss' κ) | ≥ 0.60 for task admission |
| judge stability, fixed evidence, K = 10 re-runs | SD reported (paper §8.2) |

Six anti-bias rules: blind evaluation, pairwise comparison preferred, ≥3 judges
from different vendors with median aggregation, self-preference interaction
reported, mandatory evidence citation (screenshot region or line number),
closed questions only.

## 9. Reproducibility contract

Pinned Chromium + Playwright version in `Dockerfile`; fixed seeds; full traces
committed; one command regenerates the main table; 10% of each submitted run is
re-executed by maintainers. See [`reproducibility.md`](reproducibility.md).
