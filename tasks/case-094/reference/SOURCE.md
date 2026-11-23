# Reference implementation — source, not a copy

The reference artifact is **not vendored** in this repository. It is a
third-party community artifact; copying it here would duplicate the source of
truth and bypass per-record attribution.

| Asset | URL |
|---|---|
| Runnable artifact | `https://miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files/068-bento-portfolio.html` |
| Source post | `https://x.com/DavidSilgado_/status/2102605163257381124` |
| Source corpus record | `momozi1996/Code-Everything` → `data/cases.jsonl` (`id=case-094`) |

Attribution: **@DavidSilgado_**.

## What the reference implementation is for

It is **not ground truth for scoring**. It is an **oracle for testing the
assertions**: a known-good artifact must pass every applicable L0 and L1 rule.
If it fails, the assertion is wrong, not the artifact. This meta-test is a CI
gate (`.github/workflows/meta-test.yml`).

Using the reference implementation as a scoring target would bias the
benchmark toward the model that produced it, which is why M2 injects *defects*
into it instead of asking models to imitate it.

## Licensing

`CC-BY-NC-4.0`

默认许可：署名-非商业使用（CC BY-NC 4.0）。本条内容为第三方原作者作品，若原作者另有明确声明，以原作者声明为准。如需下架请提 Issue，即刻移除。

Original authors retain all rights. This repository records attribution and
fetches on demand only. See `data/README.md`.
