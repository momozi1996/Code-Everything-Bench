#!/usr/bin/env python3
"""Main entry point for a real model evaluation run.

    # 1. after copying the templates, validate the config (no API call)
    python3 scripts/run_evaluation.py --check

    # 2. rehearse the whole pipeline offline (no network, no results written)
    python3 scripts/run_evaluation.py --dry-run

    # 3. one real task (ids come from tasks/manifest.json)
    python3 scripts/run_evaluation.py --task case-001 --limit 1

    # 4. the full batch
    python3 scripts/run_evaluation.py

Credentials come from environment variables named by `api_key_env` in
config/models.json. Nothing here asks you to paste a key into a tracked file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cebench.config import ROOT as PKG_ROOT  # noqa: E402
from cebench.evaluation import (RunPlan, TaskSpec, load_prompts,  # noqa: E402
                                run_evaluation)
from cebench.providers import (ConfigError, MissingCredentialError,  # noqa: E402
                               load_model_configs, validate_configs)
from cebench.runner import playwright_available  # noqa: E402

SYNTHETIC_PROMPT = (
    "[DRY-RUN ONLY — synthetic input, not a real community task] "
    "Build a single-file interactive zen garden with a rakeable sand surface."
)


def print_config_report(configs, report, *, strict: bool) -> int:
    print(f"  model configurations : {len(configs)}")
    for c in configs:
        key = "set" if not any(m["id"] == c.id for m in report["missing_keys"]) else "MISSING"
        print(f"    - {c.id:28s} {c.protocol:18s} {c.model:24s} "
              f"key({c.api_key_env})={key}")
    print(f"  browser (pinned)     : {'available' if playwright_available() else 'NOT installed — runtime assertions will SKIP'}")
    if report["missing_keys"]:
        print("\n  Environment variables not set:")
        for m in report["missing_keys"]:
            print(f"    {m['env_var']}  (for {m['id']})")
        print("  Fill .env, then:  set -a; source .env; set +a")
        if strict:
            return 3
    else:
        print("  All credentials present (values are never printed).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a CE-Bench evaluation")
    ap.add_argument("--models", default=str(ROOT / "config" / "models.json"))
    ap.add_argument("--run", default=str(ROOT / "config" / "run.json"))
    ap.add_argument("--corpus", default=str(ROOT / "data" / "corpus" / "cases.jsonl"))
    ap.add_argument("--check", action="store_true", help="validate config only; no API call")
    ap.add_argument("--require-keys", action="store_true", help="exit non-zero if a key is missing")
    ap.add_argument("--dry-run", action="store_true", help="rehearse offline; never writes results")
    ap.add_argument("--task", help="run only this task id")
    ap.add_argument("--limit", type=int, default=None, help="cap the number of tasks")
    ap.add_argument("--repetitions", type=int, default=None)
    args = ap.parse_args(argv)

    print("Code-Everything Bench · evaluation runner")
    print("=" * 62)
    # Fresh clones have only the templates. Falling back to them makes --check
    # and --dry-run usable immediately, without pretending they are real configs.
    models_path = Path(args.models)
    if not models_path.is_file():
        example = ROOT / "config" / "models.example.json"
        if example.is_file():
            print("  NOTE: using config/models.example.json (no local config yet).")
            print("        cp config/models.example.json config/models.json to customise.")
            models_path = example
    run_path = Path(args.run)
    if not run_path.is_file():
        example_run = ROOT / "config" / "run.example.json"
        if example_run.is_file():
            run_path = example_run
    try:
        configs = load_model_configs(models_path)
    except ConfigError as exc:
        print(f"  CONFIG ERROR: {exc}")
        print("  Start with: cp config/models.example.json config/models.json")
        return 2
    try:
        plan = RunPlan.load(run_path)
    except (ValueError, OSError) as exc:
        print(f"  RUN PLAN ERROR: {exc}")
        print("  Start with: cp config/run.example.json config/run.json")
        return 2

    report = validate_configs(configs, require_keys=False)
    rc = print_config_report(configs, report, strict=args.require_keys)
    print(f"  run plan             : {plan.run_id} · {plan.track} · {plan.split} · "
          f"{plan.repetitions} reps · seed {plan.seed}")
    if args.check:
        print("\n  CHECK COMPLETE — no API was called, no result was written.")
        return rc

    if not args.dry_run and report["missing_keys"]:
        print("\n  REFUSING TO RUN: credentials are missing. Use --check or fill .env.")
        return 3

    if args.repetitions:
        plan.repetitions = args.repetitions
    if args.task:
        plan.task_ids = [args.task]
        plan.task_set = "explicit"
    if args.limit:
        plan.limit = args.limit

    if args.dry_run:
        # A rehearsal must not require the corpus, and must not create a
        # scoreable artifact. The input is explicitly synthetic.
        tasks = [TaskSpec(task_id="dry-run-synthetic", prompt=SYNTHETIC_PROMPT,
                          split=plan.split)]
        plan.repetitions = 1
        print("\n  DRY RUN — offline stub client, synthetic prompt, nothing written.")
        rows = run_evaluation(configs, plan, tasks, dry_run=True, verbose=True)
        n_target = len([c for c in configs if getattr(c, "role", "target") == "target"])
        expected = n_target * len(tasks) * plan.repetitions
        scoreable = [r for r in rows
                     if r.get("pass_at_budget") not in ("", None, False)
                     or r.get("final_score") not in ("", None)]
        print(f"\n  rehearsed {len(rows)}/{expected} (task, configuration, repetition) loops")
        if len(rows) != expected:
            print("  DRY RUN FAILED — the pipeline did not exercise every loop.")
            return 1
        if scoreable:
            print("  DRY RUN FAILED — a rehearsal produced scoreable output.")
            return 1
        print("  DRY RUN COMPLETE — 0 scoreable results (by design).")
        print("  To validate the scoring path itself, run:")
        print("    PYTHONPATH=. python3 -m cebench.cli verify tests/fixtures/minimal_pass.html")
        return 0

    try:
        # Load the whole census; POST/PRE is computed per (task, configuration)
        # inside run_evaluation, so no task is silently dropped at load time.
        tasks = load_prompts(args.corpus, plan.task_ids or None,
                             split="all", cutoff=None)
    except FileNotFoundError as exc:
        print(f"\n  {exc}")
        return 2
    if plan.task_ids:
        tasks = [t for t in tasks if t.task_id in plan.task_ids]
    if not tasks and plan.task_ids:
        # The example task pack is not in the raw corpus under that slug;
        # allow an explicit local prompt source in a later release.
        print("  No matching corpus record for the requested task id.")
        return 2
    if plan.limit:
        tasks = tasks[:plan.limit]
    print(f"\n  tasks selected       : {len(tasks)}")
    n_target = len([c for c in configs if getattr(c, "role", "target") == "target"])
    print(f"  total generations    : {len(tasks) * n_target * plan.repetitions}")
    print("  starting...\n")
    rows = run_evaluation(configs, plan, tasks, dry_run=False, verbose=True)
    print(f"\n  Completed {len(rows)} rows -> results/{plan.run_id}/")
    print("  Next: python3 scripts/reproduce_main_table.py --run " + plan.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
