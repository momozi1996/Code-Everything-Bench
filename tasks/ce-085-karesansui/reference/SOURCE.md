# Reference implementation — source, not a copy

The reference artifact is **not vendored** in this repository. It is a
third-party community artifact; copying it here would duplicate the source of
truth and bypass per-record attribution.

| Asset | URL |
|---|---|
| Runnable artifact | `https://miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files/059-zen-sand-garden.html` |
| Baseline spec (`.txt`) | `https://miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files/059-zen-sand-garden.txt` |
| Thumbnail (`.jpg`) | `https://miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files/059-zen-sand-garden.jpg` |
| Source corpus record | `momozi1996/Code-Everything` → `cases/case-085.md`, `data/cases.jsonl` |

The `.txt` companion is structured in four fixed sections across all 100 files
of this collection: **exact prompt used / 10 global baselines / MAJOR VISUAL
TECHNIQUES / INTERACTION MODEL**. Eight of the ten baselines map directly to the
shared L0 assertion suite; the INTERACTION MODEL is the source for L1.

## What the reference implementation is for

It is **not ground truth for scoring**. It is an **oracle for testing the
assertions**: a known-good artifact must pass every applicable L0 and L1 rule.
If it fails, the assertion is wrong, not the artifact. This meta-test is a CI
gate (`.github/workflows/meta-test.yml`).

Using the reference implementation as a scoring target would bias the
benchmark toward the model that produced it (100 of 111 tasks come from one
Opus collection), which is why M2 injects *defects* into it instead of asking
models to imitate it.

## Licensing

Original authors retain all rights. This repository records attribution and
fetches on demand only. See `data/README.md`.
