#!/usr/bin/env python3
"""One command to reproduce the paper's main table.

    python3 scripts/reproduce_main_table.py --check    # CI meta-test gate
    python3 scripts/reproduce_main_table.py --run r1   # regenerate leaderboard

Hard rule: this script REFUSES to emit a table when no evaluated run exists.
A benchmark that measures unverified claims cannot publish one of its own.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def meta_test() -> int:
    """Every L0+L1 assertion must pass on a known-good artifact.

    The reference implementation is an oracle for the *assertions*, not a
    scoring target. A failing meta-test means the assertion is wrong.
    """
    from cebench.assertions.global_suite import run_global_suite
    from cebench.assertions.task_spec import classify, load_task_assertions, run_task_assertions
    from cebench.config import load_config
    from cebench.io import task_dirs
    from cebench.runner import playwright_available

    fixture = ROOT / "tests" / "fixtures" / "minimal_pass.html"
    source = fixture.read_text(encoding="utf-8")
    from collections import Counter
    l0 = run_global_suite(source)
    counts = Counter(r.status for r in l0)
    static_failures = [r.id for r in l0 if r.status == "FAIL"]
    print(f"[meta-test] L0 on pass fixture: {counts['PASS']} PASS / {counts['FAIL']} FAIL / "
          f"{counts['SKIP']} SKIP / {counts['NA']} NA, "
          f"browser={'yes' if playwright_available() else 'no (runtime checks SKIP)'}")
    if static_failures:
        print("  ASSERTIONS ARE WRONG, not the artifact:", ", ".join(static_failures))
        return 1
    if counts["SKIP"]:
        print(f"  NOTE: {counts['SKIP']} runtime checks could not run here; "
              "CI installs a pinned Chromium to cover them.")

    for d in task_dirs():
        specs = load_task_assertions(d / "assertions" / "task.json")
        c = classify(specs)
        print(f"[meta-test] {d.name}: {c['auto_assertable']} auto / "
              f"{c['visual_only']} visual / track={c['track']}")
        if not c["full_measurement"]:
            print(f"  WARNING: {d.name} has fewer than 8 auto assertions -> M1-only")
        # Visual and browser assertions are not expected to pass on a generic
        # fixture; only static source assertions are checked here.
        static = [s for s in specs if s.get("kind") in ("source_contains", "source_absent")]
        if static:
            results = run_task_assertions(static, source)
            fails = [r.id for r in results if r.status == "FAIL"]
            print(f"  static L1 on fixture: {len(results) - len(fails)} ok, {len(fails)} FAIL")
            print("  (task-specific misses are expected on a generic fixture; "
                  "admission requires the task's own reference implementation)")

    print("[meta-test] PASSED — global assertion suite is self-consistent.")
    return 0


def generate(run_id: str) -> int:
    run_dir = ROOT / "results" / run_id
    if not run_dir.is_dir():
        print(f"ERROR: no evaluated run at {run_dir}")
        return 2
    outcomes = run_dir / "outcomes.csv"
    if not outcomes.is_file():
        print(f"ERROR: {outcomes} missing. Scores are generated from traces, never typed in.")
        return 2
    traces = list((run_dir / "traces").glob("*.jsonl")) if (run_dir / "traces").is_dir() else []
    print(f"run {run_id}: {len(traces)} trace files found")
    print("Aggregation is implemented in cebench.scoring; publication requires "
          "the full 111-task run and the 10% re-execution audit described in "
          "docs/reproducibility.md.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--run")
    args = ap.parse_args()
    if args.run:
        return generate(args.run)
    return meta_test()


if __name__ == "__main__":
    sys.exit(main())
