# Assertion & Gate review (v0.6)

**Date:** 2026-11-24 · **Scope:** local, offline, no API calls · **Status:** applied

This note records why three previously published `FAIL` rows were not
attributable to a model failure, what was changed, and what is deliberately
**not** changed. It is the audit trail for the scoring-semantics revision; the
original `results/*/outcomes.csv` files are kept untouched and a separate
`rescored.csv` is produced by `scripts/rescore_artifacts.py`.

---

## 1. The defect

Three real runs existed (`glm-5.3-flash`, `single-shot-l2`). All three produced
an artifact, none timed out, none had an API or tool error
(`error=""`, `evaluation_ready=True`). Yet two were recorded as `FAIL` with
`final_score = 0.0` and the note `core_interaction_unusable`.

Root cause, `cebench/evaluation.py::build_observation` (pre-v0.6):

```python
l1_auto = [r for r in l1 if r["status"] in ("PASS", "FAIL")
           and r["id"].startswith("L1")]
interaction_ok = bool(l1_auto) and all(r["status"] == "PASS" for r in l1_auto)
```

`core_interaction_ok` — documented as a **runtime** property — was bound to
*every automatic L1 assertion*, of which most are static source regexes.
Consequences:

- One strict regex missing an equivalent implementation erased the whole run
  (`Gate.factor = 0`), compressing real quality differences (F = 0.64 vs 0.79)
  into two indistinguishable zeros.
- A single unmatched pattern was mislabelled "core interaction unusable", so
  the failure taxonomy could not distinguish a broken page from a narrow regex.
- `CAP_CORE_INTERACTION_FAIL` became dead code, and `loads` was merely
  `bool(artifact_html)` — a truncated, unclosed HTML counted as "loaded".
- `E = 0.0` was serialised as `""` by `0.0 or ""`, hiding a genuine zero.

This is a **scoring-validity** defect, not a harness or timeout problem. Adding
a harness changes neither the assertion set nor the Gate formula.

---

## 2. Full-bank scan

Scanned all 180 task packs (`tasks/*/assertions/task.json`):

| | count |
|---|---:|
| tasks with assertions | 180 |
| assertions | 1,640 |
| `source_contains` | 1,159 |
| `source_absent` | 5 |
| `interaction_delta` (runtime state probe) | 181 |
| `selector_exists` (runtime probe) | 114 |
| `visual_review` (routed to L2 judge, `NA`) | 181 |
| tasks with at least one `interaction_delta` | **180 / 180** |
| tasks with no browser-kind assertion | **0** |

Because every task has a runtime probe, the corrected Gate needs no
"no runtime evidence" fallback branch: there is always a real observation.

**Hard-coded reference selectors:** 295 browser assertions, of which only **2**
used an id/class selector (`#sand`, `#rake`, both in `case-085`). The other 293
use implementation-agnostic `body` (180), `svg` (58), `canvas` (55). There is
no bank-wide selector problem — the fix is two precise edits, not a global
rewrite.

---

## 3. Applied edits (14)

### 3.1 Single-API literal → equivalent implementations (11 packs)

| task | assertion |
|---|---|
| `b24-astra-2097323734504017936` | L1-02 |
| `case-001` | L1-02 |
| `case-008` | L1-02 |
| `case-018` | L1-02 |
| `case-023` | L1-02 |
| `gpt6-astra-2102565403109085669` | L1-02 |
| `gpt6-sol-2102665046568673765` | L1-03 |
| `new-085a7334aca5` | L1-02 |
| `new-660d2fdb371a` | L1-02 |
| `u28-opus-2104085484347818226` | L1-04 |
| `x-2102665046568673765` | L1-03 |

- before: `getContext\(\s*['\"]webgl`
- after: `(?:getContext\(\s*['"]webgl2?|WebGLRenderer|WebGL2RenderingContext|THREE\.WebGL)`
- reason: `THREE.WebGLRenderer` requests `webgl2` internally and never emits the
  literal `getContext('webgl')`. A correct Three.js delivery was systematically
  marked FAIL. The revised pattern accepts webgl/webgl2 and the renderer APIs,
  and still fails a page with no 3D path at all.

### 3.2 Gesture binding literal → event family (1 pack)

- `case-085` / L1-10 `chime is gesture-bound`
- before: `addEventListener\(\s*['"]click`
- after: `(?:addEventListener\(\s*['"](?:click|pointerdown|pointerup|touchstart|touchend|keydown|keyup)|onclick\s*=)`
- reason: a chime bound to `pointerdown`, `touchend` or `onclick=` is equally
  gesture-bound; the old pattern only recognised the `click` string.

### 3.3 Reference-implementation DOM ids → semantic selectors (2 assertions)

| task | assertion | before | after |
|---|---|---|---|
| `case-085` | L1-07 `raking changes runtime state` | `#sand` | `canvas` |
| `case-085` | L1-08 `rake tool button is reachable` | `#rake` | `button, [role="button"], [onclick]` |

Reason: these ids come from the third-party reference. The information-boundary
rule (§3.2) forbids showing the reference to the model, so requiring its exact
DOM id tests guessing, not capability. The judge note for this run ("buttons
have only icon/title, no visible text label") is consistent: the controls
existed, they simply had different ids.

A defensive fallback was also added in `cebench/assertions/task_spec.py`: if a
declared selector misses, the probe retries a generic semantic selector and
records `generic selector fallback` in the assertion evidence. An
`interaction_delta` still requires a real pre/post state delta
(`infer_evidence_grade != "E0"`), so the fallback cannot manufacture a PASS.

### 3.4 Deliberately retained

| pattern | packs | why kept |
|---|---:|---|
| `#e8e0cf` | 1 | the verbatim prompt for `case-085` contains this exact hex value; it is a requirement, not an implementation detail |
| `gradient\(` | 45 | matches `linear-gradient(`, `radial-gradient(` and `createLinearGradient(`; broad enough |
| `draggable\|mousedown\|pointerdown\|touchstart` | 38 | covers the standard pointer-entry events |
| `THREE\.\|three(\.module\|\.min)?\.js` | 24 | the assertion is literally "Three.js runtime referenced" |
| `perspective\|transform: 3d\|THREE.\|webgl` | 49 | four alternatives, already implementation-agnostic |

`L0-06 prefers-reduced-motion honoured` fails on all three artifacts. That is a
real, shared requirement gap and is **kept as a quality deduction** in F — it is
no longer a whole-run veto.

---

## 4. Corrected Gate / Cap semantics

`cebench/config.py`, `cebench/scoring/gate.py`, `cebench/evaluation.py`,
`cebench/scoring/rubric.py`:

| rule | v0.6 meaning |
|---|---|
| `artifact_does_not_load` | deliverable is not a complete, loadable HTML: missing closing `</html>`/`</body>`, or the pinned browser could not open it. **Token truncation lands here**, with its own `artifact_truncated` / `truncated` flag. |
| `core_interaction_unusable` | runtime probes (`interaction_delta`, `selector_exists`) produced **zero PASS**. Static `source_*` failures are excluded. |
| `unverified_claims` | unchanged: claimed checks with no trace evidence |
| `forbidden_shortcut` | now also fires on a failed `source_absent` assertion (static image standing in for the artifact); the old name-only check could never fire |
| `no_deliverable_file` | unchanged |

- **Cap revived:** `runtime_pass > 0 and runtime_fail > 0` ⇒
  `core_interaction_degraded = True` ⇒ `CAP_CORE_INTERACTION_FAIL = 0.5`.
  The run is usable (Gate passes) but quality is compressed. An all-failing
  probe set remains a Gate veto. This is the distinction design-decisions #19
  lost when it moved the rule from Cap to Gate.
- Static assertion failures flow into F/R/E through the rubric's weighted
  pass rate, so F = 0.64 / 0.79 / 0.92 remain visible instead of being
  flattened to zero.
- `outcomes.csv` gains a `truncated` column, explicit `notes` attribution
  (`output_truncated_at_token_cap`, `runtime_interaction_degraded(cap=0.5)`,
  `static_assertions_failed:...`), and `F/R/V/E` now preserve a real `0.0`.

**Two leaderboards remain separate.** Nothing here merges Regime 1 (bare API)
and Regime 2 (pinned `mini-swe-agent`); `Core-111` / `Extended-69` layering is
untouched; the judge stays `deepseek-v4.1-flash-1017`.

---

## 5. Output cap alignment (the other half of the fix)

`case-001` stopped at exactly `tokens_out = 16000` — its configured cap —
mid-`restore.addEventListener(...)`. The run plan declared
`max_output_tokens: 96000`, but the target entry said `16000` and both provider
clients fell back to a hard-coded `16000`.

Applied:

- `cebench/config.py`: `TARGET_MAX_TOKENS = 96000`, recommended floor 64000;
  `DEFAULT_BUDGET.max_output_tokens = 96000`.
- All `config/*.json`: every **target** `params.max_tokens = 96000`; judge stays
  at 8192; target timeouts raised to 600 s; run-plan budgets = 96000.
- `cebench/providers.py`: both clients fall back to `TARGET_MAX_TOKENS`;
  `validate_configs()` emits a `warnings` entry for a target below the floor;
  `LLMResponse.finish_reason` is captured (`length` / `max_tokens` ⇒ truncated).
- `cebench/generate.py`: `GenerationResult.truncated` combines `finish_reason`
  and `completion_tokens >= cap`; recorded in the trace and `outcomes.csv`.

96000 is the run-plan budget already used by the smoke runs, not a claim that a
provider supports the full 512k–1M context window. It is a *cap*, not a target:
the model is free to stop earlier.

### v0.7 update (2026-11-24) — 96k → 512k

The 96k ceiling was still judged too tight for the full 180-task batch. Cost is
explicitly not a constraint here; the priority is that every task can deliver a
complete single-file artifact. Applied:

- `cebench/config.py`: `TARGET_MAX_TOKENS = 512000` and
  `TARGET_MAX_TOKENS_RECOMMENDED_MIN = 512000`; `DEFAULT_BUDGET` follows it and
  `wall_clock_minutes` 30 → 120.
- All `config/*.json`: every target `params.max_tokens`, `defaults.max_tokens`
  and `budget.max_output_tokens` = 512000; target per-request timeout 600 s →
  3600 s. Judge stays at 8192.
- All 180 `tasks/*/budget.json` (and the generator `BUDGET_TEMPLATE`):
  `max_output_tokens` 60000 → 512000, `wall_clock_minutes` 30 → 120.
- `scripts/rescore_artifacts.py` keeps a pinned `HISTORICAL_TARGET_CAP = 96000`
  so the v0.6 offline re-score still classifies the committed `case-001`
  truncation correctly. Published `results/<run-id>/config.json` snapshots are
  immutable and were NOT edited.

The cap remains a ceiling, not a target: models normally stop far earlier. If a
provider rejects a 512k `max_tokens`, override it per model and record the
deviation in the run plan.

---

## 6. Residual gaps (explicitly not fixed here)

1. **`visual_review` is still `NA`** — the L2 multimodal judge writes only
   `judge.csv` and `scripts/judge_run.py` states it "updates nothing else".
   The V dimension is therefore empty in every row; all four `judge.csv`
   verdicts are `FAIL` with "no rendered screenshots provided". Wiring
   screenshots → judge → `outcomes.csv` is the next评测-side task (P2).
2. **No rerun variance** — a single repetition per task remains below the
   2026 literature's noise floor (harness swap flips 13% of tasks; a no-change
   rerun flips another 13%). Published deltas below ~8–10 pp on 111 tasks
   must be reported as indistinguishable within noise.
3. **`forbidden_shortcut`** now fires on `source_absent` failures but still does
   not treat an `L0-01` external-resource failure as a shortcut. Deliberate:
   that is a deliverable-completeness issue, not cheating.
4. The manuscript's §5.5 wording (in the separate Overleaf project) still says
   "core interaction unusable" without the runtime/static distinction and must
   be synchronised before submission. This repository's
   `docs/benchmark-spec.md` §6 has been updated.

---

## 7. Reproduce

```bash
python3 -m unittest discover -s tests          # scoring + provider contracts
PYTHONPATH=. python3 -m cebench.cli selftest  # 180-pack contract
python3 scripts/run_evaluation.py --models config/models.harness.example.json --check
python3 scripts/rescore_artifacts.py          # offline re-score of existing artifacts
python3 scripts/build_results_dashboard.py    # refresh the evidence board
```
