"""Command line entry point.

    python3 -m cebench.cli selftest
    python3 -m cebench.cli verify <artifact.html> [--task <task-dir>]
    python3 -m cebench.cli contract
    python3 -m cebench.cli report            # refuses to run on PLACEHOLDER data

Zero-dependency by design: a fresh clone can validate the whole artifact before
installing any optional packages.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __title__, __version__
from .config import CORPUS_COMMIT, GATE_RULES, L0_IDS, ROOT
from .io import task_dirs
from .runner import contract, playwright_available, verify_artifact
from .scoring import assert_verifiability_budget, deterministic_mass


def cmd_selftest() -> int:
    errors: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    checks.append(("8 L0 rules declared", len(L0_IDS) == 8, f"{len(L0_IDS)} rules"))
    checks.append(("5 Gate vetoes declared", len(GATE_RULES) == 5, f"{len(GATE_RULES)} rules"))
    checks.append(("deterministic mass >= 0.75", assert_verifiability_budget(),
                   f"{deterministic_mass():.2f} (F+R+E)"))

    from .assertions.global_suite import run_global_suite
    actual = [r.id for r in run_global_suite("")]
    checks.append(("L0 implementation matches declared IDs", actual == list(L0_IDS),
                   ", ".join(actual)))

    fixtures = ROOT / "tests" / "fixtures" / "minimal_pass.html"
    checks.append(("pass fixture present", fixtures.is_file(), str(fixtures.name)))
    if fixtures.is_file():
        s = verify_artifact(fixtures, use_browser=False)["l0_summary"]
        checks.append(("pass fixture has no static L0 failures", s["failed"] == 0,
                       f"{s['passed']} PASS / {s['failed']} FAIL / "
                       f"{s['skipped']} SKIP / {s['na']} NA"))
        checks.append(("runtime rules honestly SKIP without browser",
                       s["skipped"] == 2, f"{s['skipped']} SKIP"))

    dirs = task_dirs()
    checks.append(("at least one task pack", len(dirs) >= 1, f"{len(dirs)} packs"))
    for d in dirs:
        for rel in ("task.json", "prompt.md", "budget.json",
                    "assertions/task.json", "mutations.json", "reference/SOURCE.md"):
            checks.append((f"{d.name}/{rel}", (d / rel).is_file(), ""))

    manifest = ROOT / "tasks" / "manifest.json"
    if manifest.is_file():
        from .io import read_json
        m = read_json(manifest)
        checks.append(("manifest carries 111 tasks", m.get("task_count") == 111,
                       str(m.get("task_count"))))

    for name, ok, detail in checks:
        if not ok:
            errors.append(name)
        print(f"  [{'OK' if ok else '!!'}] {name}" + (f"  — {detail}" if detail else ""))

    print()
    print(f"  {__title__}")
    print(f"  version {__version__} · corpus {CORPUS_COMMIT} · "
          f"browser={'available' if playwright_available() else 'not installed (static mode)'}")
    if errors:
        print(f"\n  SELFTEST FAILED: {len(errors)} issue(s): {', '.join(errors)}")
        return 1
    print("  SELFTEST PASSED — contract consistent, no fabricated results.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    out: dict[str, Any] = verify_artifact(args.artifact, args.task)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["l0_summary"]["failed"] == 0 else 2


def cmd_contract() -> int:
    print(json.dumps(contract(), ensure_ascii=False, indent=2))
    return 0


def cmd_report() -> int:
    csv_path = ROOT / "leaderboard" / "data" / "results.csv"
    text = csv_path.read_text(encoding="utf-8") if csv_path.is_file() else ""
    if "PLACEHOLDER" in text or not text.strip():
        print("REFUSING TO GENERATE A REPORT: leaderboard/data/results.csv contains "
              "no evaluated runs.\nPublishing a table from placeholder data would be an "
              "unverified claim — the exact failure mode this benchmark measures.\n"
              "Run the evaluation first, then: python3 scripts/reproduce_main_table.py")
        return 3
    print("Report generation requires results/ traces; see scripts/reproduce_main_table.py")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cebench", description=__title__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest", help="validate the benchmark contract and fixtures")
    sub.add_parser("contract", help="print the L2 interface contract")
    sub.add_parser("report", help="generate the leaderboard (refuses placeholder data)")
    v = sub.add_parser("verify", help="score one artifact's assertions")
    v.add_argument("artifact")
    v.add_argument("--task", default=None)
    args = parser.parse_args(argv)
    return {
        "selftest": lambda: cmd_selftest(),
        "contract": lambda: cmd_contract(),
        "report": lambda: cmd_report(),
        "verify": lambda: cmd_verify(args),
    }[args.command]()


if __name__ == "__main__":
    sys.exit(main())
