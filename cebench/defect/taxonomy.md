# Defect taxonomy (D1–D6)

Every mutation operator is a concrete instance of **specification gaming / reward
hacking** on a visual artifact. Each row records the source of evidence that
justifies it. Reviewers will ask "are these defects things that actually happen?"
— this table is the answer.

| ID | Operator | Observable symptom | Source of evidence | Detected by | Detected by a DOM check? |
|---|---|---|---|---|---|
| **D1** | `d1_remove_feature` | A tool / control disappears but the layout still looks complete | Community failure reports in `Code-Everything`; "non-functional UI buttons" listed in the source corpus baseline | L1 task assertion | ❌ statically, yes; behaviourally, no |
| **D2** | `d2_external_dependency` | CDN `<script>` inserted; artifact stops working under `file://` offline | L0 baseline "no external resources"; single-file contract | **L0-01** | ✅ |
| **D3** | `d3_timer_instead_of_raf` | Animation still moves, but janks and ignores reduced-motion | L0 baseline "rAF + prefers-reduced-motion" | **L0-05** | ❌ |
| **D4** | `d4_remove_reduced_motion` | `prefers-reduced-motion` branch removed | L0 baseline accessibility rule | **L0-06** | ❌ |
| **D5** | `d5_audio_autostart` | `AudioContext` starts with no gesture; console warning / autoplay block | L0 baseline "Web Audio needs gesture" | **L0-08** | ❌ |
| **D6** | `d6_static_fake_3d` | Live canvas replaced by a flat image; "3D" is a backdrop | WorldBench mutation test: code-only judges still award full credit after a feature is deleted; explicit "static background pretending to be 3D" in community specs | Gate `forbidden_shortcut` + pixel probe | ❌ |

## Why a mutation-based M2 is methodologically necessary

1. **Exact ground truth.** Defects are injected by us, so precision/recall are
   computable; there is no hidden rubric and no judge disagreement.
2. **Controllable difficulty.** Injecting 1 → 5 defects creates the difficulty
   gradient IRT calibration needs, without writing new tasks.
3. **No generation confound.** The artifact under review was authored by
   neither the model nor the evaluator's imagination; a strong generator cannot
   talk its way out of an inspection task.
4. **Honesty is measurable.** A model that answers "no defects" has its accuracy
   scored directly against known defects — it cannot predict the answer key.

## Registration rule for new operators

A new operator must cite (a) a real failed case ID from the corpus, or (b) a
published failure mode with a citation, and must declare which L0/L1 rule or
Gate rule detects it. An operator that no assertion can detect is not admitted:
it would create an unverifiable ground truth.
