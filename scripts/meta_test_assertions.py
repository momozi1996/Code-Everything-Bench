#!/usr/bin/env python3
"""Meta-test every auto-derived assertion against its reference implementation.

Principle (from reference/SOURCE.md): the reference artifact is an *oracle for
testing the assertions*, not a scoring target. If the reference fails an
assertion, the assertion is wrong — or the L0 contract does not apply to that
task. Either way it must be recorded, not silently shipped.

    python3 scripts/meta_test_assertions.py --workers 8
    python3 scripts/meta_test_assertions.py --task case-001 --keep-html

Writes `tasks/<id>/assertions/meta_test.json` and a summary under
`docs/assertion-meta-test.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cebench.runner import verify_artifact  # noqa: E402

TASKS = ROOT / "tasks"
DOCS = ROOT / "docs"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def fetch(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def test_one(tid: str, keep_html: bool) -> dict[str, Any]:
    tdir = TASKS / tid
    out: dict[str, Any] = {"task_id": tid, "status": "ok"}
    try:
        task = json.loads((tdir / "task.json").read_text(encoding="utf-8"))
        url = task.get("reference_url") or ""
        # An explicit evidence flag beats a URL guess: extended post-only tasks
        # may carry a claude.ai / goodcase.ai demo link that is NOT a runnable
        # artifact, and fetching it would hang or produce a false oracle.
        if task.get("meta_test_applicable") is False or not url:
            # Extended post-only tasks have no pinned runnable artifact, so the
            # reference-oracle check is *not applicable* (not a failure). Record
            # that explicitly instead of leaving meta_test.json absent, which
            # downstream catalog code would otherwise render as "review".
            res = {
                **out,
                "status": "not_applicable_no_reference",
                "meta_test_applicable": False,
                "note": ("post-only evidence: verbatim prompt and source post are pinned, "
                         "but no runnable third-party artifact is available. L0/L1 "
                         "assertions still evaluate each generated artifact normally."),
            }
            if not (tdir / "assertions").is_dir():
                (tdir / "assertions").mkdir(parents=True)
            (tdir / "assertions" / "meta_test.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return res
        try:
            html = fetch(url)
        except Exception as exc:
            return {**out, "status": "fetch_failed", "error": f"{type(exc).__name__}: {exc}"[:200]}
        tmp = Path(tempfile.mkdtemp()) / f"{tid}.html"
        tmp.write_bytes(html)
        v = verify_artifact(tmp, tdir)
        l0f = [r for r in v.get("l0", []) if r.get("status") == "FAIL"]
        l1f = [r for r in v.get("l1", []) if r.get("status") == "FAIL"]
        out.update({
            "bytes": len(html),
            "l0_failed": [{"id": r["id"], "name": r["name"],
                           "evidence": (r.get("evidence") or "")[:160]} for r in l0f],
            "l1_failed": [{"id": r["id"], "name": r["name"],
                           "evidence": (r.get("evidence") or "")[:160]} for r in l1f],
            "l0_summary": v.get("l0_summary"),
            "l1_summary": v.get("l1_summary"),
            "assertions_ok": not l0f and not l1f,
        })
        (tdir / "assertions" / "meta_test.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if keep_html:
            (tdir / "reference" / "reference.html").write_bytes(html)
        return out
    except Exception as exc:  # pragma: no cover - defensive
        return {**out, "status": "error", "error": f"{type(exc).__name__}: {exc}"[:200]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--keep-html", action="store_true")
    ap.add_argument("--extended-only", action="store_true",
                    help="only process tasks/manifest_extended.json (no network fetches)")
    args = ap.parse_args()

    if args.extended_only:
        ext = json.loads((TASKS / "manifest_extended.json").read_text(encoding="utf-8"))
        ids = [t["task_id"] for t in ext["tasks"]]
    else:
        ids = [args.task] if args.task else sorted(
            d.name for d in TASKS.iterdir() if d.is_dir() and (d / "task.json").is_file())

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(test_one, t, args.keep_html): t for t in ids}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            results.append(r)
            flag = "OK " if r.get("assertions_ok") else r.get("status", "?").upper()[:3]
            print(f"[{i:3d}/{len(ids)}] {flag} {r['task_id']}"
                  f"  l0_fail={len(r.get('l0_failed') or [])} l1_fail={len(r.get('l1_failed') or [])}"
                  f" {r.get('error', '')}")

    ok = [r for r in results if r.get("assertions_ok")]
    l0_bad = [r for r in results if r.get("l0_failed")]
    l1_bad = [r for r in results if r.get("l1_failed")]
    failed = [r for r in results if r.get("status") in ("fetch_failed", "error", "no_reference_url")]
    na = [r for r in results if r.get("status") == "not_applicable_no_reference"]

    if not DOCS.exists():
        DOCS.mkdir(parents=True)
    report_name = "assertion-meta-test-extended.md" if args.extended_only else "assertion-meta-test.md"
    lines = ["# Assertion meta-test — reference as oracle", "",
             f"tasks tested: {len(results)} · reference passes every assertion: {len(ok)}",
             f"tasks failing at least one L0 rule: {len(l0_bad)}",
             f"tasks failing at least one L1 assertion: {len(l1_bad)}",
             f"tasks that could not be fetched/testing failed: {len(failed)}",
             f"tasks with no reference oracle (not applicable): {len(na)}", "",
             "> A reference that fails an assertion means the assertion is wrong, or the",
             "> shared L0 contract does not apply to that task. Fix before publishing scores.",
             ""]
    if l0_bad:
        lines += ["## L0 failures", "", "| task | rule | evidence |", "|---|---|---|"]
        for r in l0_bad[:200]:
            for f in r["l0_failed"]:
                lines.append(f"| {r['task_id']} | {f['id']} {f['name']} | {f['evidence']} |")
        lines.append("")
    if l1_bad:
        lines += ["## L1 failures", "", "| task | assertion | evidence |", "|---|---|---|"]
        for r in l1_bad[:200]:
            for f in r["l1_failed"]:
                lines.append(f"| {r['task_id']} | {f['id']} {f['name']} | {f['evidence']} |")
        lines.append("")
    if failed:
        lines += ["## Not testable", "", "| task | reason |", "|---|---|"]
        for r in failed[:200]:
            lines.append(f"| {r['task_id']} | {r.get('status')} {r.get('error','')} |")
        lines.append("")
    if na:
        lines += ["## Not applicable (post-only evidence)", "",
                  "These tasks pin a verbatim prompt and source post but no runnable",
                  "third-party artifact, so the oracle-based meta-test cannot run.",
                  "This is an evidence grade, not a failure: L0/L1 assertions still",
                  "evaluate each generated artifact. Do not include them in a",
                  "meta-test pass-rate denominator.", "",
                  "| task |", "|---|"]
        for r in na[:200]:
            lines.append(f"| {r['task_id']} |")
        lines.append("")
    (DOCS / report_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport -> {DOCS/report_name}")
    print(f"clean={len(ok)} l0_bad={len(l0_bad)} l1_bad={len(l1_bad)} "
          f"unavailable={len(failed)} not_applicable={len(na)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
