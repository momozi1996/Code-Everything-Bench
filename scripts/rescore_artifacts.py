#!/usr/bin/env python3
"""Offline re-score of committed artifacts under the v0.6 scoring contract.

This does **not** call any model API and does **not** modify `outcomes.csv`.
Published run records stay immutable. For each existing outcome row it:

  1. locates the committed artifact HTML,
  2. re-runs L0/L1 assertions (pinned Chromium when available),
  3. rebuilds the Gate/Rubric observation with the current `build_observation`,
  4. writes a clearly-labelled `results/<run-id>/rescored.csv` companion,
  5. emits `docs/rescore-report.md` with an old-vs-new attribution table.

The claim-audit input (`unverified_claims`) is taken from the original row so
the comparison isolates exactly the v0.6 changes: document completeness,
runtime-only interaction veto, degraded Cap, shortcut evidence and the
reviewed assertion patterns.

Usage:  python3 scripts/rescore_artifacts.py [--out-dir results] [--no-browser]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from cebench.assertions.base import AssertionResult  # noqa: E402
from cebench.evaluation import build_observation  # noqa: E402
from cebench.runner import verify_artifact  # noqa: E402
from cebench.scoring import score_run  # noqa: E402

FIELDS = [
    "run_id", "config_id", "task_id", "repetition",
    "old_pass", "old_score", "old_notes",
    "new_pass", "new_score", "new_notes",
    "gate_vetoes", "cap", "F", "R", "V", "E",
    "l0_pass", "l0_fail", "l0_skip", "l1_pass", "l1_fail",
    "runtime_pass", "runtime_fail", "static_fails", "truncated",
    "artifact", "browser_available", "rescored_by",
]

RESCORED_BY = "v0.6 (docs/assertion-review.md)"

# The v0.6 smoke runs were actually executed with a 96k target cap. This
# offline re-score MUST keep that historical value to decide whether an
# artifact was truncated. It is deliberately NOT tied to the current
# cebench.config.TARGET_MAX_TOKENS (512k since v0.7): raising it here would
# silently reclassify the committed case-001 truncation as a clean stop.
HISTORICAL_TARGET_CAP = 96000


def _as_int(v, default=0):
    try:
        return int(float(str(v)))
    except (TypeError, ValueError):
        return default


def _as_bool(v):
    return str(v).strip().lower() in ("true", "1", "yes")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _artifact_for(run_dir: Path, cfg_id: str, task_id: str, rep: int) -> Path | None:
    d = run_dir / "artifacts"
    exact = d / f"{cfg_id}__{task_id}__r{rep}.html"
    if exact.is_file():
        return exact
    candidates = sorted(d.glob(f"{cfg_id}__{task_id}__r*.*")) if d.is_dir() else []
    return candidates[0] if candidates else None


def _trace_events(run_dir: Path, stem: str) -> list[dict]:
    p = run_dir / "traces" / f"{stem}.jsonl"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        out.append({"step": ev.get("step", 0), "action": ev.get("action", ""),
                    "observation": ev.get("observation", ""),
                    "target": ev.get("target", "")})
    return out


def _claimed_checks(run_dir: Path, stem: str) -> list[str]:
    d = _load_json(run_dir / "delivery_notes" / f"{stem}.md")
    return [str(x) for x in (d.get("claimed_checks") or [])] if isinstance(d, dict) else []


def _notes(obs: dict, s) -> str:
    notes = ";".join(s.gate.vetoes) if s.gate.vetoes else "delivered"
    if obs.get("artifact_truncated"):
        notes += " | output_truncated_at_token_cap"
    if obs.get("core_interaction_degraded"):
        notes += " | runtime_interaction_degraded(cap=0.5)"
    if obs.get("static_assertion_failures"):
        notes += " | static_assertions_failed:" + ",".join(obs["static_assertion_failures"])
    return notes


def rescore_run(run_dir: Path, use_browser: bool | None) -> list[dict]:
    cfg = _load_json(run_dir / "config.json")
    caps = {c.get("id"): _as_int((c.get("params") or {}).get("max_tokens"), HISTORICAL_TARGET_CAP)
            for c in (cfg.get("configurations") or [])}
    rows: list[dict] = []
    opath = run_dir / "outcomes.csv"
    with opath.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            task_id = row.get("task_id", "")
            cfg_id = row.get("config_id", "")
            rep = _as_int(row.get("repetition"), 1)
            art = _artifact_for(run_dir, cfg_id, task_id, rep)
            stem = f"{cfg_id}__{task_id}__r{rep}"
            base = {
                "run_id": run_dir.name, "config_id": cfg_id, "task_id": task_id,
                "repetition": rep,
                "old_pass": row.get("pass_at_budget", ""),
                "old_score": row.get("final_score", ""),
                "old_notes": row.get("notes", ""),
                "artifact": art.name if art else "",
                "rescored_by": RESCORED_BY,
            }
            if art is None or not art.is_file():
                base.update({"new_pass": "", "new_score": "",
                             "new_notes": "artifact missing: cannot rescore",
                             "gate_vetoes": "", "cap": "", "truncated": ""})
                rows.append(base)
                continue

            source = art.read_text(encoding="utf-8", errors="replace")
            tokens = _as_int(row.get("tokens_out"))
            cap = caps.get(cfg_id, HISTORICAL_TARGET_CAP)
            truncated = tokens >= cap > 0 or not bool(re.search(r"</(?:html|body)\s*>", source, re.I))
            gen = SimpleNamespace(
                artifact_html=source, config_id=cfg_id, task_id=task_id,
                usage={"completion_tokens": tokens},
                trace_events=_trace_events(run_dir, stem),
                delivery_note=SimpleNamespace(claimed_checks=_claimed_checks(run_dir, stem)),
                truncated=truncated,
            )
            task_dir = ROOT / "tasks" / task_id
            v = verify_artifact(art, task_dir if task_dir.is_dir() else None,
                                use_browser=use_browser)
            obs, ready = build_observation(gen, v)
            # Keep the original claim-audit evidence: only the v0.6 scoring
            # semantics are under test here.
            obs["unverified_claims"] = _as_int(row.get("unverified_claims"))
            results = [AssertionResult(id=r["id"], name=r["name"], tier=r["tier"],
                                       status=r["status"], dimension=r.get("dimension", "F"))
                       for r in v["l0"] + v["l1"]]
            s = score_run(task_id, cfg_id, obs, results)
            dims = s.quality_score.dimensions
            fmt = lambda x: "" if x is None else round(float(x), 6)  # noqa: E731
            ev = obs["runtime_interaction_evidence"]
            base.update({
                "new_pass": s.pass_at_budget if ready else "",
                "new_score": round(s.final_score, 4) if ready else "",
                "new_notes": _notes(obs, s) if ready else "not evaluation_ready",
                "gate_vetoes": ";".join(s.gate.vetoes),
                "cap": s.quality_score.cap,
                "F": fmt(dims["F"]), "R": fmt(dims["R"]),
                "V": fmt(dims["V"]), "E": fmt(dims["E"]),
                "l0_pass": v["l0_summary"]["passed"], "l0_fail": v["l0_summary"]["failed"],
                "l0_skip": v["l0_summary"]["skipped"],
                "l1_pass": v["l1_summary"].get("passed", 0),
                "l1_fail": v["l1_summary"].get("failed", 0),
                "runtime_pass": ev["pass"], "runtime_fail": ev["fail"],
                "static_fails": ",".join(obs["static_assertion_failures"]),
                "truncated": bool(obs.get("artifact_truncated")),
                "browser_available": bool(v.get("browser_available")),
            })
            rows.append(base)
    return rows


def write_report(all_rows: list[dict], out: Path) -> None:
    lines = [
        "# Offline re-score report (v0.6)",
        "",
        "Generated by `scripts/rescore_artifacts.py` — **no model API was called**.",
        "",
        "> **Immutability:** the original `results/<run-id>/outcomes.csv` files are",
        "> untouched. `rescored.csv` is a derived companion. The v0.6 numbers are",
        "> the ones the current scoring code would produce for the *same committed",
        "> artifacts*; they are not a new measurement of the model.",
        "",
        "Changes under test: (1) token cap fixed at the historical 96,000 actually",
        "used by these committed runs (the live contract is 512,000 since v0.7;",
        "it does not retroactively change these artifacts), (2) Gate[0] now",
        "requires a complete document, (3) Gate[1] is driven only by runtime",
        "interaction probes, (4) a partly failing probe set is capped at 0.5",
        "instead of zeroed, (5) 14 reviewed assertion patterns/selectors,",
        "(6) real `0.0` dimensions are no longer serialised as blank.",
        "See `docs/assertion-review.md`.",
        "",
        "## Old vs new",
        "",
        "| run | task | old | old score | new | new score | Gate vetoes | Cap | F / R / E |",
        "|---|---|---|---:|---|---:|---|---:|---|",
    ]
    for r in all_rows:
        fr = "/".join(str(r.get(k)) if r.get(k) not in (None, "") else "—"
                      for k in ("F", "R", "E"))
        lines.append(
            f"| `{r['run_id']}` | `{r['task_id']}` | {r['old_pass']} | {r['old_score']} "
            f"| {r['new_pass']} | {r['new_score']} | {r.get('gate_vetoes') or '—'} "
            f"| {r.get('cap', '')} | {fr} |")

    lines += ["", "## Per-task attribution", ""]
    for r in all_rows:
        lines += [
            f"### `{r['task_id']}` · `{r['run_id']}`",
            "",
            f"- **Before:** `{r['old_pass']}` / score `{r['old_score']}` — notes: `{r['old_notes']}`",
            f"- **After:** `{r['new_pass']}` / score `{r['new_score']}` — notes: `{r['new_notes']}`",
            f"- L0 `{r.get('l0_pass')}/{r.get('l0_fail')}/{r.get('l0_skip')}` (pass/fail/skip), "
            f"L1 `{r.get('l1_pass')}/{r.get('l1_fail')}`, "
            f"runtime probes `{r.get('runtime_pass')} pass / {r.get('runtime_fail')} fail`, "
            f"static failures: `{r.get('static_fails') or 'none'}`.",
            f"- Artifact `{r.get('artifact') or 'missing'}`, truncated: `{r.get('truncated')}`, "
            f"pinned browser: `{r.get('browser_available')}`.",
            "",
        ]
    lines += [
        "## Reading the result",
        "",
        "- A v0.6 `PASS` with `final_score < 1` means the Gate passed and the",
        "  remaining deductions are genuine quality signals (failed L0/L1",
        "  assertions in F/R/E), not a whole-run veto.",
        "- A v0.6 `FAIL` with `artifact_does_not_load` and `truncated=True` is a",
        "  **budget/deliverable** failure: the model's output was cut off at the",
        "  old 16k cap. It is not evidence about model capability.",
        "- `runtime_interaction_degraded(cap=0.5)` means some interaction probes",
        "  passed and some failed: usable, but capped.",
        "- V is still empty: `visual_review` assertions are routed to the L2",
        "  judge, which writes only `judge.csv` and does not feed `outcomes.csv`.",
        "  This is the next evaluation-side gap, not fixed in v0.6.",
        "",
        "Reproduce: `python3 scripts/rescore_artifacts.py` then",
        "`python3 scripts/build_results_dashboard.py`.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--report", default="docs/rescore-report.md")
    ap.add_argument("--no-browser", action="store_true",
                    help="static assertions only (runtime probes SKIP; not comparable)")
    args = ap.parse_args()
    results_dir = ROOT / args.out_dir
    use_browser = False if args.no_browser else None
    all_rows: list[dict] = []
    for run_dir in sorted(p for p in results_dir.iterdir()
                          if p.is_dir() and (p / "outcomes.csv").is_file()):
        rows = rescore_run(run_dir, use_browser)
        if not rows:
            continue
        with (run_dir / "rescored.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"{run_dir.name}: {len(rows)} rows -> rescored.csv")
        all_rows.extend(rows)
    write_report(all_rows, ROOT / args.report)
    print(f"wrote {args.report} ({len(all_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
