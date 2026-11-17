# Task `ce-085-karesansui` — prompt

> **Not vendored on purpose.** The verbatim community prompt is fetched from the
> pinned corpus by `scripts/sync_corpus.py`. Reproducing it here would create a
> second source of truth and would redistribute a third party's text without a
> per-record license check. This file records its *structure* for reviewers.

## Provenance

| Field | Value |
|---|---|
| Source corpus | `momozi1996/Code-Everything` @ `v556ab07` |
| Case ID | `case-085` |
| `promptStatus` | `full` (verbatim, not an excerpt) |
| Reference artifact | `059-zen-sand-garden.html` (see `reference/SOURCE.md`) |
| Baseline spec | `059-zen-sand-garden.txt` — exact prompt + 10 global baselines + MAJOR VISUAL TECHNIQUES + INTERACTION MODEL |

## Requirement set (from the prompt's specification, for assertion authoring)

1. Single-file HTML, `file://` openable, **no external resources**.
2. Palette anchored on sand `#e8e0cf` with muted stone tones.
3. A rakeable sand surface; raking leaves persistent grooves (real state, not a static image).
4. Five distinct tools exposed in the UI.
5. Wind chime implemented with Web Audio, started **only after a user gesture**.
6. Vertical (writing-mode) title treatment.
7. Mobile-first: no horizontal scrolling at 360px.
8. `prefers-reduced-motion` respected; animation driven by `requestAnimationFrame`.
9. Pointer and keyboard must reach the same functionality.
10. No decorative-but-dead controls; every visible control changes state.

Items 1, 7, 8, 9 map to the shared **L0** suite. Items 3–6, 10 map to **L1**
(`assertions/task.json`). Subjective aesthetic quality is *not* scored here —
L2 scores observable adherence to stated visual requirements, not taste (§9.5).

## Why this task is a good pilot

It is a **long specification** (894 chars), not a one-line prompt. The source
corpus is bimodal: 103 prompts under 200 chars and 152 at >= 800 chars. A pilot
drawn only from short prompts would not exercise requirement coverage at all.
