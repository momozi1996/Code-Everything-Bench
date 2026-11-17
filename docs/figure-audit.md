# Figure quality audit — parity with GameCraft-Bench

Reference: `arXiv:2606.17861` Figures 2, 3, 5 and the project website
`tongxuluo.github.io/gamecraft-bench-website`. The six figure specifications in
[`figures/`](figures/) were written against these images element by element.
This file is the audit trail: **what their figures do, what our corresponding
figure must do, and where we deliberately exceed them.**

## 1. Four reusable properties of their visual language

| # | Property | Where it appears | Why it works |
|---|---|---|---|
| P1 | **Numbered stage badges** ①②③④⑤ reused across figures | Fig 2 left column, Fig 5 all five columns | A reader can map text ("Stage 3") to a picture without re-reading the caption |
| P2 | **Real numbers on the figure**, not just labels | `41.46%`, `39.49`, `140 Tasks`, `15 Families`, `@2FPS`, `duration: 300` | Makes the figure independently citable and signals measured rather than illustrative |
| P3 | **Failure paths drawn explicitly in red** | Fig 5 `BUILD = 0 → Final Score 0` | Shows the boundary of the contract; a reviewer can see what the evaluator refuses to score |
| P4 | **One Overview figure carrying four jobs** | Fig 2: pipeline (left) + result bar (top right) + family donut (bottom right) + three badges (bottom) | A skim-reading reviewer gets "what / how / result / coverage" in one glance |
| P5 | **Aggregation functions written on the diagram** | Fig 5 `avg() or max()`, score matrix `M-1 … A-4`, `Final Score = 0.77` | The scoring rule is auditable from the figure alone |

## 2. Element-by-element parity

### Their Figure 2 (Overview) ↔ our `fig2-overview.md`

| Their element | Our element | Status |
|---|---|---|
| Three numbered stages, left column, vertical | ① Task packaging ② Generation+browser ③ Interactive verification | ✅ same structure |
| Result bar chart, top right, best value highlighted, `41.46%` + "far from solved" | `Pass@Budget` bar across configurations, best highlighted, **bootstrap 95% CI error bars** (theirs has none) | ✅ + **exceeds** |
| Family donut, `15 Tasks Families / 140 Tasks`, labelled segments | 8-domain donut with measured counts, multi-label footnote | ✅ |
| Three bottom badges `Real Engine / End-to-End / Interactive Verification` | `Real Community Prompts / Single-File / Runtime State Probe` | ✅ |
| Caption states the whole protocol in one sentence | Caption written, stored in the figure file | ✅ |
| — | **Rejection-transparency strip** (`739 → 305 → 111`, with rejection counts) | ➕ **ours only** |

### Their Figure 3 (Problem definition) ↔ our `fig3-problem-definition.md`

| Their element | Our element | Status |
|---|---|---|
| Three coloured prompt cards (blue / pink / green), stacked left | Three **real** prompt cards with character counts: 11-char pelican, 20-char night train, 894-char karesansui | ✅ + real data |
| Central `Agent` block with `Environments` grid, `Action ⇄ Feedback` loop | L2 sandbox block with the three observation channels and the budget triple `B=(T,K,C)` | ✅ |
| Right column: three stacked game screenshots, colour-matched to prompts | Three stacked deliverables: `artifact.html` / `trace.jsonl` / `assumptions.md`, labelled `file://` and zero-dependency | ✅ |
| Caption with formal notation `s → G`, `ℰ` | Bottom formula strip with `p → A*`, `B`, `τ` and Definition 1–5 index | ✅ |
| — | **Explicit information boundary** "observes `(p,ℰ)`, not `ρ`" drawn on the agent block | ➕ **ours only** |

### Their Figure 5 (Evaluation pipeline) ↔ our `fig5-evaluation-pipeline.md`

| Their element | Our element | Status |
|---|---|---|
| Five numbered columns: Packaging / Generation / Build Gate / Replay / Score | Five numbered columns: Task Packaging / Generation / Launch Gate / Interactive Verification / Score & Aggregation | ✅ isomorphic |
| `Hidden Rubrics` with distinct background colour | **`L0 ×8 PUBLIC` in green** (visible contrast: open vs hidden rubric) | ✅ + deliberate contrast |
| Red failure branch `BUILD = 0 → Final Score 0` | Red branch `Gate 未过 → Fail · 记录 unverified claims` | ✅ |
| `Demo 001 / Demo 002` trace cards with JSON and score matrix | Trace card with `claimed checks` vs `trace-verified checks` | ✅ |
| `Sampled Frames @2FPS` grid | Interaction recording + sampled frames **@2FPS** grid | ✅ |
| `Aggregation Function avg() or max()` | `0.35F+0.30R+0.20V+0.15E` with **0.80 deterministic** label + bootstrap CI | ✅ + explicit |
| `Hidden` rubric M/D/V/A | `F/R/V/E`, with F/R/E marked deterministic and V judge-assisted | ✅ |
| Multi-modal LLM judge | 3-judge median, blind, evidence-citation enforced | ✅ |
| — | **M2 verification-as-construct branch** (injected defects → defect list) drawn as a second output of column ② | ➕ **ours only — the paper's central claim** |

### Figures they do not have

| Our figure | Why we need it |
|---|---|
| `fig4-construction-pipeline.md` | Their tasks are expert-authored; ours are a measured census with rejection transparency. The funnel *is* the data-quality argument. |
| `fig6-main-results.md` | Their result is one bar chart; our claim is a **correlation/dissociation**, which requires a 2×2 panel (M1×M2 scatter, calibration curve, D1–D6 stacked failures, domain radar). |

## 3. Hard rules for all six figures

1. **Every number on a figure must come from a script in `analysis/` or from
   `tasks/manifest.json`.** No hand-drawn illustrative values. `[R#]` slots are
   filled after the run; before that, figures carry an explicit `PLACEHOLDER`.
2. **Failure branches are drawn with the same visual weight as success paths.**
3. **Numbered badges** ①–⑤ are used consistently across Fig 2, Fig 4 and Fig 5.
4. **Colour semantics**: blue = pipeline, green = public/auditable, red =
   rejection/failure, orange = judge-assisted evidence.
5. **Figure 6 must be script-generated** (R/matplotlib), never hand-drawn —
   reproducibility applies to the main result figure too.
6. Captions in `figures/*.md` must match `manuscript.md` **word for word**.
7. CI error bars appear on every aggregate bar; significance groups (a/b/c)
   replace spurious rank ordering.

## 4. Release checklist

- [ ] All six figures rendered as vector PDF/PNG at 2× journal column width
- [ ] Every numeric label traced to a file in this repository
- [ ] Captions verified against the manuscript
- [ ] Fonts embedded; no external image dependencies
- [ ] Grayscale-legible (journal print): colour is never the only channel
- [ ] Figure 1 hero reused as the website banner with identical numbers
- [ ] `docs/figures/*.md` updated with final asset paths

## 5. Where the website must match them

Their site lists **14 agent configurations** (harness × model, not bare
models) and shows a playable embed plus a five-dimension score card per case,
so a reader can see "Mechanics 100, Visuals 58". Our leaderboard matches this
with: configuration-level rows, three metric groups, per-task drill-down
(assertion breakdown, failure class, trace summary, self-assessment vs actual),
domain and POST/PRE filters, and significance groups instead of a spurious
1–2–3 ordering.
