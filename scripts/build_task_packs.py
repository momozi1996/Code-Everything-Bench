#!/usr/bin/env python3
"""Materialise the 111 task packs from the pinned corpus + manifest.

Single source of truth is `data/corpus/cases.jsonl` (fetched by
`scripts/sync_corpus.py`) joined with `tasks/manifest.json`. This script only
writes *derived* files; it never invents prompt text and never copies a
third-party artifact into the repository.

    python3 scripts/build_task_packs.py            # build/refresh all packs
    python3 scripts/build_task_packs.py --dry-run  # report only
    python3 scripts/build_task_packs.py --keep-assertions  # never touch assertions/

Idempotence rules:
  * `prompt.md`, `task.json`, `budget.json`, `reference/SOURCE.md` are rewritten.
  * `assertions/task.json` is only written when missing (or --force-assertions).
  * `mutations.json` is only written when missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tasks" / "manifest.json"
CORPUS = ROOT / "data" / "corpus" / "cases.jsonl"
TASKS = ROOT / "tasks"

# Conservative default. Contamination split is recomputed at run time against
# each configuration's `training_cutoff`, so this value is documentation only.
BASELINE_CUTOFF = "2025-06-30"

BUDGET_TEMPLATE: dict[str, Any] = {
    "wall_clock_minutes": 30,
    "max_repair_rounds": 15,
    "max_output_tokens": 60000,
    "network": "deny",
    "browser": "chromium-pinned",
    "viewport_desktop": "1440x900",
    "viewport_mobile": "360x780",
    "repetitions": 3,
    "seed_policy": "fixed-per-configuration",
    "rationale": "A real user does not accept unlimited repair rounds. Without a budget, delivery degenerates into 'eventually solvable'.",
}

MUTATIONS_TEMPLATE: dict[str, Any] = {
    "difficulty_ladder": [1, 2, 3, 4, 5],
    "operators": [
        {"class": "D1", "status": "needs_review", "note": "selector/DOM removal"},
        {"class": "D2", "status": "needs_review", "note": "external dependency substitution"},
        {"class": "D3", "status": "needs_review", "note": "silent no-op interaction"},
        {"class": "D4", "status": "needs_review", "note": "layout collapse"},
        {"class": "D5", "status": "needs_review", "note": "asset 404"},
        {"class": "D6", "status": "needs_review", "note": "claim/behaviour divergence"},
    ],
    "ground_truth_policy": "exactly the applied records returned by cebench.defect.apply_mutations; no hidden rubric",
    "meta_test": "each injected artifact must be detected by at least one L0/L1 assertion or Gate rule before this config is admitted",
}


def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("id"):
                out[r["id"]] = r
    return out


def infer_four_dimensions(prompt: str, tags: list[str]) -> dict[str, str]:
    """Heuristic mapping from the interaction model (paper §4.3).

    These are placeholders derived from observable prompt/tag evidence, not a
    scored field. They are documented as `inferred` in task.json.
    """
    lowered = prompt.lower()
    long_run = any(k in lowered for k in ("实时", "交互", "动画", "游戏", "拖动", "点击"))
    return {
        "interaction_span": "multi-turn" if long_run else "single-turn",
        "execution_span": "long" if any(t.startswith("code2") for t in tags) else "short",
        "trigger": "user-initiated",
        "deliverable": "objective-artifact" if any(
            k in lowered for k in (".html", "网页", "html")) else "objective-artifact",
    }


def so_md(rec: dict[str, Any], mrec: dict[str, Any]) -> str:
    attribution = rec.get("attribution") or {}
    creator = attribution.get("creator") or mrec.get("author") or "unknown"
    source_url = attribution.get("sourceUrl") or mrec.get("source_post_url") or ""
    license_ = rec.get("contentLicense") or "see licenseNote"
    license_note = (rec.get("licenseNote") or "").strip()
    demo = rec.get("demoUrl") or mrec.get("demo_url") or ""
    return f"""# Reference implementation — source, not a copy

The reference artifact is **not vendored** in this repository. It is a
third-party community artifact; copying it here would duplicate the source of
truth and bypass per-record attribution.

| Asset | URL |
|---|---|
| Runnable artifact | `{demo}` |
| Source post | `{source_url}` |
| Source corpus record | `momozi1996/Code-Everything` → `data/cases.jsonl` (`id={rec.get('id')}`) |

Attribution: **{creator}**.

## What the reference implementation is for

It is **not ground truth for scoring**. It is an **oracle for testing the
assertions**: a known-good artifact must pass every applicable L0 and L1 rule.
If it fails, the assertion is wrong, not the artifact. This meta-test is a CI
gate (`.github/workflows/meta-test.yml`).

Using the reference implementation as a scoring target would bias the
benchmark toward the model that produced it, which is why M2 injects *defects*
into it instead of asking models to imitate it.

## Licensing

`{license_}`

{license_note}

Original authors retain all rights. This repository records attribution and
fetches on demand only. See `data/README.md`.
"""


def build(dry_run: bool, keep_assertions: bool, force_assertions: bool) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = load_jsonl(CORPUS)
    created = refreshed = skipped = 0
    problems: list[str] = []

    for mrec in manifest["tasks"]:
        tid = mrec["task_id"]
        rec = cases.get(tid)
        if rec is None:
            problems.append(f"{tid}: no corpus record")
            continue
        prompt = rec.get("prompt") or ""
        if not prompt.strip():
            problems.append(f"{tid}: empty prompt in corpus")
            continue
        if not (rec.get("demoUrl") or "").endswith(".html"):
            problems.append(f"{tid}: demoUrl is not a runnable .html")
            continue

        tdir = TASKS / tid
        existing = tdir.is_dir()
        if dry_run:
            if not existing:
                created += 1
            else:
                refreshed += 1
            continue

        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "reference").mkdir(exist_ok=True)

        (tdir / "prompt.md").write_text(
            f"<!-- verbatim prompt from momozi1996/Code-Everything (id={tid}) -->\n\n"
            f"{prompt.strip()}\n", encoding="utf-8")

        dims = infer_four_dimensions(prompt, mrec.get("code2_tags") or [])
        task_json = {
            "task_id": tid,
            "source_case_id": tid,
            "title": mrec.get("title"),
            "prompt_status": mrec.get("prompt_status"),
            "evidence_level": mrec.get("evidence_level"),
            "mode": "Replay",
            "track": "CE-Frozen",
            "code2_tags": mrec.get("code2_tags") or [],
            "domains": mrec.get("domains") or [],
            "four_dimensions": {k: v for k, v in dims.items()},
            "four_dimensions_note": "inferred from prompt/tags by scripts/build_task_packs.py; not a scored field",
            "prompt_chars": len(prompt.strip()),
            "prompt_chars_manifest": mrec.get("prompt_chars"),
            "published_at": mrec.get("published_at") or rec.get("publishedAt"),
            "reference_url": rec.get("demoUrl"),
            "source_post_url": mrec.get("source_post_url") or rec.get("xUrl"),
            "contamination_split": None,
            "contamination_split_note": (
                f"computed at run time against each configuration's training_cutoff "
                f"(cebench/evaluation.py); baseline cutoff for documentation: {BASELINE_CUTOFF}"),
            "assertion_target": 12,
            "full_measurement": False,
            "license": rec.get("contentLicense") or "see reference/SOURCE.md",
            "attribution": rec.get("attribution") or {},
            "notes": "Prompt text is fetched from the pinned corpus and is not vendored upstream; "
                     "it is materialised here for offline runs.",
        }
        (tdir / "task.json").write_text(
            json.dumps(task_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        (tdir / "budget.json").write_text(
            json.dumps(BUDGET_TEMPLATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        muts = dict(MUTATIONS_TEMPLATE)
        muts = {"task_id": tid, "substrate": "reference/SOURCE.md", **muts}
        mut_path = tdir / "mutations.json"
        if not mut_path.exists():
            mut_path.write_text(json.dumps(muts, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")

        (tdir / "reference" / "SOURCE.md").write_text(so_md(rec, mrec), encoding="utf-8")

        a_path = tdir / "assertions" / "task.json"
        if force_assertions or not a_path.exists():
            if force_assertions or not keep_assertions:
                a_path.parent.mkdir(parents=True, exist_ok=True)
                a_path.write_text(json.dumps({
                    "task_id": tid,
                    "tier": "L1",
                    "minimum_auto_assertions": 8,
                    "assertions": [],
                    "status": "assertions_pending",
                    "notes": "Generated by build_task_packs.py. Fill via scripts/generate_assertions.py.",
                }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if existing:
            refreshed += 1
        else:
            created += 1

    print(f"packs created={created} refreshed={refreshed} skipped={skipped} "
          f"total_manifest={len(manifest['tasks'])}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:20]:
            print("  -", p)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-assertions", action="store_true",
                    help="never overwrite assertions/task.json")
    ap.add_argument("--force-assertions", action="store_true",
                    help="overwrite assertions/task.json even if present")
    args = ap.parse_args()
    if not CORPUS.is_file():
        print(f"corpus missing: {CORPUS}\nRun scripts/sync_corpus.py first.", file=sys.stderr)
        return 2
    return build(args.dry_run, args.keep_assertions, args.force_assertions)


if __name__ == "__main__":
    sys.exit(main())
