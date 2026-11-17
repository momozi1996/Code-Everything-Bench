#!/usr/bin/env python3
"""Build tasks/manifest.json from the pinned Code-Everything corpus.

The 111-task census is a *measured* consequence of the data structure, not a
design choice. This script recomputes it from the raw JSONL so every number in
the paper can be reproduced:

    739  main-library records
    305  with prompt text                    (reject 434: 426 unavailable + 8 demo)
    111  with a runnable .html demoUrl      (reject 194)
    111  with original post + publishedAt   (reject 0 — checked, not filtered)

The whole library contains 120 `.html` demos, but 9 of those records have no
prompt text and were already removed at S1. 120 is therefore NOT a funnel
stage; reporting it as one mixes a whole-library statistic with a conditional
one. This was corrected in paper design-decisions #22.

IMPORTANT: `promptStatus` is NOT an admission gate here. It is an evidence
grade: 102 `full` tasks enter the strict D1 leaderboard, 9 transcribed /
repository / context tasks enter Replay with their completeness annotated.

Usage:
    python3 scripts/build_manifest.py --source /path/to/cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 14 corpus tags -> 8 reporting domains (reporting only; never used as strata)
DOMAIN_MAP = {
    "code2frontend": "frontend", "code2html": "frontend", "code2css": "frontend",
    "code23d": "3d", "code2world": "3d", "code2shader": "3d", "code2blender": "3d",
    "code2viz": "visualization", "code2canvas": "visualization",
    "code2svg": "svg-art", "code2game": "game", "code2audio": "audio",
    "code2video": "animation-video", "code2deck": "composite",
}


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def runnable_html(row: dict) -> bool:
    return (row.get("demoUrl") or "").endswith(".html")


def admissible(row: dict) -> bool:
    return bool(row.get("prompt")) and runnable_html(row) and bool(row.get("xUrl")) \
        and bool(row.get("publishedAt"))


def build(rows: list[dict]) -> dict:
    with_prompt = [r for r in rows if r.get("prompt")]
    with_demo = [r for r in with_prompt if runnable_html(r)]
    tasks = [r for r in with_demo if admissible(r)]

    domain_counts: Counter = Counter()
    tag_counts: Counter = Counter()
    status_counts: Counter = Counter()
    enriched = []
    for r in tasks:
        tags = r.get("code2Tags") or []
        tag_counts.update(tags)
        domains = sorted({DOMAIN_MAP.get(t, "composite") for t in tags}) or ["composite"]
        domain_counts.update(domains)
        status = r.get("promptStatus") or "unknown"
        status_counts[status] += 1
        enriched.append({
            "task_id": r.get("id"),
            "title": r.get("title") or "",
            "model_label": r.get("modelLabel"),
            "code2_tags": tags,
            "domains": domains,
            "prompt_status": status,
            "evidence_level": "A" if status == "full" else "B",
            "prompt_chars": len(r.get("prompt") or ""),
            "published_at": r.get("publishedAt"),
            "demo_url": r.get("demoUrl"),
            "source_post_url": r.get("xUrl"),
            "author": r.get("author"),
            "license": r.get("license"),
            "failed": bool(r.get("failed")),
            "related_case_ids": r.get("relatedCaseIds") or [],
            "contamination_split": None,  # computed per model from its training cutoff
        })

    return {
        "schema_version": "1.0",
        "source": "momozi1996/Code-Everything",
        "task_count": len(tasks),
        "funnel": {
            "main_library": len(rows),
            "with_prompt_text": len(with_prompt),
            "with_runnable_html": len(with_demo),
            "admissible_full_measurement": len(tasks),
            "rejected": {
                "no_prompt_text": len(rows) - len(with_prompt),
                "no_runnable_html": len(with_prompt) - len(with_demo),
                "no_post_or_timestamp": len(with_demo) - len(tasks),
            },
        },
        "prompt_status_distribution": dict(status_counts),
        "strict_d1_tasks": status_counts.get("full", 0),
        "replay_annotated_tasks": len(tasks) - status_counts.get("full", 0),
        "code2_tag_counts": dict(tag_counts.most_common()),
        "domain_counts": dict(domain_counts.most_common()),
        "single_source_warning": {
            "note": "100/111 tasks point to one Opus collection; results must be stratified by source.",
            "collection": "miaai-lab.github.io/Claude-Opus-5.5-100-HTML-Files",
        },
        "tasks": enriched,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "data" / "corpus" / "cases.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "tasks" / "manifest.json"))
    ap.add_argument("--leaderboard-out", default=str(ROOT / "leaderboard" / "data" / "tasks.json"))
    args = ap.parse_args()
    src = Path(args.source)
    if not src.is_file():
        print(f"ERROR: corpus not found at {src}. Run scripts/sync_corpus.py first.")
        return 2
    manifest = build(load_rows(src))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lb = Path(args.leaderboard_out)
    lb.parent.mkdir(parents=True, exist_ok=True)
    lb.write_text(json.dumps({
        "task_count": manifest["task_count"],
        "domains": manifest["domain_counts"],
        "tasks": [{k: t[k] for k in ("task_id", "title", "domains", "code2_tags",
                                     "prompt_status", "published_at", "prompt_chars")}
                  for t in manifest["tasks"]],
        "results_state": "PLACEHOLDER",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    f = manifest["funnel"]
    print(f"funnel: {f['main_library']} -> {f['with_prompt_text']} -> "
          f"{f['with_runnable_html']} -> {f['admissible_full_measurement']}")
    print(f"promptStatus: {manifest['prompt_status_distribution']}")
    print(f"wrote {out} and {lb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
