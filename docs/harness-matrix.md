# CE-Bench harness policy (v0.5 design)

**Status: P0 approved and P1 implemented (this session).** The owner approved
**both regimes** on 2026-11-24: Regime 1 (all bare) and Regime 2 (all
`mini-SWE-agent`), as two parallel experiments. `cebench/providers.py` now
accepts and sanitises `harness_impl` / `harness_version`; no other code path
has changed. The v0.3 four-harness matrix is demoted to Appendix A. Sampling numbers below
reflect the v0.7 contract: `max_tokens = 512000`, `timeout_seconds = 3600` for
every target, judge unchanged at 8192.

Companion to [`benchmark-spec.md`](benchmark-spec.md) §4.1 (two-tier task bank)
and §9 (reproducibility contract). Where this design and the spec disagree, the
spec is authoritative until the spec is amended.

---

## 0. Decision in one paragraph

**Both regimes run, as two separate parallel experiments.** Regime 1: every
tested model under `single-shot-l2` (bare API, one call). Regime 2: every
tested model under one pinned `mini-SWE-agent` release. Each regime produces
its **own leaderboard** — inside a regime the harness is constant, so any
ranking difference is attributable to the model. Cross-regime comparison is
**pairwise per model only** (same model, same tasks, same assertions, same
judge; the only changed variable is the loop), which yields a per-model
`bare → minimal-loop` Δ as a by-product analysis. The two tables are never
merged into one ranking, and no "harness leaderboard" is claimed. Because both
regimes exist, rank stability across harnesses comes **for free** (§5).

---

## 1. Why uniform, and why "one model, one harness" is a trap

The research question is **which model delivers what users actually ask for**.
Model is therefore the only independent variable; following arXiv:2608.20485,
the other four components of the tested system — `interface`, `harness`,
`runtime`, `environment` — must be fixed within each regime. A row naming only
a model is not a valid system description, but a valid *comparison* requires
that the rest of the description be identical across rows.

| Option | Design | Identifiable? | What it actually measures | Verdict |
|---|---|---|---|---|
| **A** | one harness per model (especially vendor harness + vendor model) | **No.** Model and harness are perfectly collinear; their effects cannot be separated by any statistical test. | A **product / system** benchmark, not a model benchmark. | **Not recommended** unless the paper's claim is explicitly changed to "we compare complete agent products" and the leaderboard is renamed accordingly. |
| **B** | **one identical harness for every model** | **Yes.** Any Δ is attributable to the model, subject to rerun noise. | Model capability under a declared, fixed system. | **Chosen — instantiated twice (Regimes 1 and 2).** |
| C | four harnesses × every model (v0.3) | Yes, but expensive. | A model × harness interaction study — a different paper. | Demoted to Appendix A. |

Option A *feels* fairer ("give each contestant their best equipment"), but it is
the opposite: customising the apparatus per contestant removes comparability. A
sprint is comparable when everyone wears the same shoes.

2026 evidence also argues directly against A: arXiv:2610.04433 ran
DeepSeek's own CLI with DeepSeek-V4-Flash and found it solved the same 21 of 45
hard tasks as Claude Code on that model, **at the top of the cost range**. A
vendor harness is neither automatically better nor automatically fairer.

And 2026 evidence argues for B on cost/benefit: the same paper found a harness
swap flips **13%** of task outcomes — exactly as many as a plain rerun — while
cost per task differs up to **3×**. Running two pinned regimes instead of a
four-harness matrix captures the useful signal at roughly half the cost.

---

## 2. The two regimes

| Regime | Harness | Claim measured | Cost profile |
|---|---|---|---|
| **1** | `single-shot-l2` (bare API) | *one-shot delivery capability* | cheapest; already the live chain; 180-task E2E smoke passed |
| **2** | `mini-SWE-agent` (pinned) | *delivery capability inside one declared minimal agent loop* | cheap (<1k token preamble/step); adds step budget + local bash/browser loop |

Why `mini-SWE-agent` is the Regime 2 harness, and nothing else:

- Open source and version-pinnable; ~100 lines; bash-only; no context
  management; BYOM via any openai-compatible endpoint (no vendor-model
  binding, no gateway); used as the minimal control in three 2026 studies.
  Bash suffices to write `index.html` and run a local headless browser.
- `Claude Code` — rejected as a constant: Anthropic-Messages-only (needs an
  anthropic↔openai gateway, an extra unpinned component), closed source,
  in-quarter behaviour drift (arXiv:2609.00006), ~16.6k token preamble/step.
- `Codex CLI` — rejected: closed source, same drift exposure, wire-API
  verification needed against a non-OpenAI endpoint.
- `OpenHands` — rejected: 25+ tools + Docker add degrees of freedom the main
  question does not need.
- Vendor harness + vendor model — **prohibited**: perfect collinearity (§1).

**Reporting rules.**
1. Two leaderboards, one per regime; each row is `model @ <pinned harness>`.
2. Never merge the two rankings; no cross-regime rank claims.
3. The per-model paired Δ (Regime 2 − Regime 1, same tasks) **is** a valid
   result and is reported as an analysis, with paired tests.
4. Extended-69 never enters either regime's meta-test denominator (§4).

---

## 3. Reproducibility contract

Every item is recorded in the sanitised `results/<run-id>/config.json`.
Within each regime the following are constant across all model rows.

| Field | Requirement | Source |
|---|---|---|
| `harness` | constant per regime: `single-shot-l2` or `agent-harness-l2` | this policy |
| `harness_impl` | concrete implementation id (defaults to `harness` for bare) | P1 |
| `harness_version` | exact pinned release — required even for a single harness | arXiv:2609.00006: behaviour drifted within three months |
| `protocol` | `openai-compatible` for all rows; no gateway | `config/README.md` |
| sampling | identical `temperature`, `max_tokens`, `top_p`, `reasoning_effort`, `seed` across models | comparability |
| target (reference) | `z-ai/glm-5.3-flash`, `minimal` / `512000` / `3600s` | v0.7: cap raised 96k → 512k and timeout 600 s → 3600 s so no task is cut off (docs/assertion-review.md §5); 16k truncated the 34 KB artifact |
| judge | `deepseek/deepseek-v4.1-flash-1017`, `temperature: 0` — fixed, never varies by regime | project decision |
| `network` | **disabled in both regimes** | arXiv:2610.04433: with web access 71% of attempts fetched the correct fix from GitHub |
| `initial_workspace` | fixed snapshot (empty dir + `prompt.md`), checksum recorded | arXiv:2608.20485 |
| `step_budget` / `context_window` / `tool_set` / `timeout` | N/A for Regime 1; pinned for Regime 2 | arXiv:2609.20804 |
| trace | commands, failures, retries, state changes, verification acts | arXiv:2608.20485 |
| scoring | identical Gate / Cap / Rubric / L0 / L1 / judge in both regimes | spec §6 |

**Rerun control is still mandatory.** A rerun flips 13% of task outcomes
(arXiv:2610.04433). Recommend **≥ 3 repetitions** per `(model, task)` cell in
Regime 1; ≥ 2 in Regime 2 (disclose the asymmetry). With 111 Core tasks, a
single paired comparison cannot reliably resolve gaps below **~8–10 pp** (45
tasks detect 12.9 pp only half the time; 447 tasks resolve ~5 pp). Smaller
differences must be reported as *indistinguishable within rerun noise*. Paired
Wilcoxon with Holm correction; McNemar on per-task PASS/FAIL flips; never pool
across tiers.

---

## 4. Task subset

Measured directly from the 180 `tasks/*/task.json` packs on 2026-11-24:

```
set:                  core 111, extended 69
reference_kind:       runnable-html 111, post-only 69
has_reference_oracle: True 111, False 69
meta_test_applicable: True 111, False 69
```

> **Snapshot note (2026-11-25, v0.8).** The counts above are the historical
> 180-task bank as measured on 2026-11-24 and are kept verbatim. The current
> bank is **258** packs (Core-111 unchanged, Extended-147 after the 2026-11-25
> X / Vibe3D batch, `docs/x-batch-import-report.md`). The subset rule below is
> unchanged: both regimes still run on Core-111 only; Extended-147 stays out of
> the meta-test denominator and out of either regime's agent comparison.

**Both regimes run on Core-111** (`has_reference_oracle == true AND
reference_kind == "runnable-html"`). Extended-69 may run bare-only for the
two-tier stratified report, but never enters the meta-test denominator or
either regime's agent comparison (spec §4.1). The paper's headline census
stays Core-111; Table 9, §7 stratified reporting and all figure captions are
unchanged.

**Regime 2 workload contract.** The task is a self-contained single HTML file
(spec D2), not a repository repair. Per task: clean workspace containing only
`prompt.md`; the agent writes the deliverable to a fixed path (`index.html`);
a local headless browser may be used for self-checks (encourage — this is D3);
the runner collects the final artifact + full trace and applies the unchanged
L0/L1 assertions, Gate/Cap/Rubric and fixed judge.

---

## 5. Rank stability comes for free

A reviewer will ask whether the ranking is an artefact of the chosen harness —
arXiv:2608.20485 found system gaps of 21.25 pp on one benchmark but ≤ 7 pp
with the ranking *reversing* on another. With both regimes in place:

- compute **Kendall τ (and Spearman ρ) between the two regime leaderboards** on
  the same models and tasks;
- bootstrap the τ over task resamples;
- ranking stable → one sentence: *"the model ordering is not an artefact of
  the execution harness"*;
- ranking reverses → a genuine, citable finding and a mandatory limitations
  paragraph. Do not hide it.

No third harness is needed unless a reversal appears; only then consult
Appendix A for the optional extension.

---

## 6. Configuration and code impact (P1, implemented 2026-11-24)

The existing design already treats a configuration as `harness × model`
(`config/README.md`), so no structural change is needed. Changes made in P1:

1. `cebench/providers.py` — `ModelConfig` accepts two optional fields,
   `harness_impl` (defaults to the `harness` value when absent) and
   `harness_version` (defaults to `""`); both are carried into the sanitised
   output. Nothing else in the validation path changed.
2. `config/README.md` — documents the two new fields and the dual-regime
   policy.
3. `config/models.harness.example.json` — a dual-regime template: one bare
   target, one `mini-swe-agent` target, one fixed judge.

```json
{
  "id": "cfg-glm53flash-miniswe",
  "role": "target",
  "protocol": "openai-compatible",
  "base_url": "https://<endpoint>/v1",
  "api_key_env": "TOKENPLUS_API_KEY",
  "model": "z-ai/glm-5.3-flash",
  "harness": "agent-harness-l2",
  "harness_impl": "mini-swe-agent",
  "harness_version": "PINNED_EXACT_RELEASE",
  "training_cutoff": "2025-12-31",
  "params": { "temperature": 0.7, "max_tokens": 512000, "top_p": 1.0, "reasoning_effort": "minimal" },
  "timeout_seconds": 3600
}
```

Still to build (P2, not yet started): the `mini-swe-agent` execution adapter
that gives the runner `(artifact, trace)` for `agent-harness-l2` rows. The
scoring, evaluation, runner, judge and task packs are untouched.

---

## 7. Impact on the manuscript

- Keep: §7 two-tier stratified reporting, Table 9 (Core-111), POST/PRE split,
  Gate/Cap/Rubric, L0/L1, judge protocol, the four reported numbers
  (`Pass@Budget`, `Quality | Pass`, `Cost-to-Pass`, failure-class distribution).
- Add: **two leaderboards** (Regime 1 / Regime 2), each internally fixed-system.
- Add: the per-model paired Δ analysis (Regime 2 − Regime 1) with Wilcoxon /
  McNemar and bootstrap CIs.
- Add: the §5 rank-stability statistic (Kendall τ between regimes).
- Add: an explicit statement of the fixed system five-tuple
  (`model + interface + harness + runtime + environment`) with pinned versions.
- Add: limitations — Regime 1 measures one-shot delivery, not long-horizon
  agentic repair; Regime 2 is conditional on the declared minimal loop; the
  paired Δ is specific to one harness pair.
- **Remove**: any claim about a general "harness leaderboard" or vendor-harness
  superiority. Those belong to a different paper.
- The 2026 references in §9 remain the justification for the fixed-harness +
  rerun + offline protocol.

---

## 8. Implementation phases

| Phase | Work | Exit gate | Status |
|---|---|---|---|
| **P0** | Choose regime(s). | owner decision | **done 2026-11-24: both regimes** |
| **P1** | `providers.py`: accept + sanitise `harness_impl` / `harness_version`; `config/README.md`; `config/models.harness.example.json`. | unit tests + selftest, `--check`, `--dry-run` green. | **done this session** |
| **P2** | `mini-swe-agent` adapter (`agent-harness-l2` → `(artifact, trace)`); pin the release; single-task smoke in both regimes; verify the offline rule. | scoreable artifact + full trace per regime; zero network egress. | next |
| **P3** | **Core-111 × N models × repetitions, both regimes** (≥3 reps Regime 1, ≥2 reps Regime 2). | complete `outcomes.csv` / `judge.csv` / `traces/`; this is the full BMK result. | — |
| **P4** | Δ analysis + §5 rank stability + manuscript §7 / limitations / references. | two separate leaderboards, no mixed ranking. | — |

---

## 9. References (2026, identifiers verified 2026-11-24)

1. Barbaste, P., Darrigol, T., Vu, G., Wiltberger, T. (2026). *Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents — A Source-Code Study of Eleven Systems*. arXiv:2609.00006. Submitted 15 Jul 2026, 83 pp.
2. Fan, R.-Z., Zhang, Z., Ma, S., Hu, Y., Wang, S., Song, K., Liu, F., Zamani, H., Wang, X. (2026). *An Empirical Study of Harness Design for Coding Agents*. arXiv:2609.20804. Submitted 17 Sep 2026, 43 pp.
3. Liu, Y., Han, Z. (2026). *What Does a Harness Buy? Tokens, Mostly.* arXiv:2610.04433. 3 Oct 2026. Code and data: `github.com/YangzeLiu/what-does-a-harness-buy`.
4. Bin, Y., Yuan, X., Zeng, H., Ye, W., Shao, W., Qian, C., Ye, W., Ding, Y., Wang, Z., Zeng, P., Song, J., Shen, H. T. (2026). *Terminal Agents: A Survey of AI Agents in Command-Line Environments*. arXiv:2608.20485. 20 Aug 2026, 52 pp.
5. Le, C., Cheng, J., He, Q., Li, R., Li, Y., Chen, X. (2026). *Multi-Harness Reinforcement Learning for Coding Agents: Training Gains and Harness Dependence*. arXiv:2609.04518v2. v1 3 Sep 2026, v2 9 Oct 2026.
6. Lewis, S. (2026). *Same Model, Different Harness: Different Coding-Agent Results*. arXiv:2608.26218. 26 Aug 2026. *(Author list not independently verified — check before citing.)*
7. Merrill, M. A., Shaw, A. G., Carlini, N., et al. (2026). *Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces*. arXiv:2601.11868. 17 Jan 2026.
8. Terminal-Bench 2.0 / 2.1 official leaderboards, tbench.ai, 2026. *(Online artefact, not a paper.)*
9. CodeSOTA, *SWE-bench / Autonomous Coding Agents*, 2026-04 snapshot. *(Industry summary; motivation only.)*

---

## Appendix A. The demoted four-harness matrix (v0.3, optional extension)

Retained for the case where the §5 check shows a ranking reversal and a
dedicated follow-up study is warranted. Not part of the main experiment.

| ID | Harness | Represents | 2026 anchors |
|---|---|---|---|
| H0 | `single-shot-l2` | bare API, one call | CE-Bench native |
| H1 | `mini-swe-agent` | minimal neutral, bash-only, no context management | 2610.04433 · 2608.20485 · 2609.00006 |
| H2 | `claude-code` | heavyweight commercial, 43 tools, auto compression | 2609.00006 · 2610.04433 · TB boards |
| H3 | `codex-cli` | OpenAI official CLI, cross-session memory | 2601.11868 · tbench.ai · 2609.00006 |
| H4 | `openhands` | open platform, Docker, 25+ tools | 2609.04518 · 2608.20485 · 2609.00006 |

Tier B substitutes: `Aider` (git-native), `SWE-agent` (academic ACI),
`Terminus 2` (Terminal-Bench neutral reference) — use only if a main cell is
blocked.

Excluded and why: `Gemini CLI` (model-bound), `OpenCode` (arXiv:2610.04433
measured a 9 pp deficit, about half caused by an output-cap bug in the tested
1.18 release — a confound, not a capability effect), `Qwen Code` /
`Mistral Vibe` / `Hermes` / `Pi` / `OpenClaw` / `Omnigent` (single-paper,
niche), and all one-off Terminal-Bench custom scaffolds (`NexAU-AHE`,
`LemonHarness`, `Capy`, `Droid`, `Mux`, `WOZCODE`, `TongAgents`, `Crux`,
`Goose`, `Letta Code`, `Junie CLI`, `Terminus-KIRA`, …): high scores, but not
installable, not pinnable and not comparable.
