#!/usr/bin/env python3
"""Build a self-contained per-task results dashboard for CE-Bench.

Reads every `results/<run_id>/` directory that contains `outcomes.csv`, joins it
with the task packs (`tasks/<id>/task.json`, `prompt.md`, `assertions/`), the
taxonomy, judge verdicts, delivery notes and traces, and emits one standalone
HTML file with the generated artifacts embedded (so previews work offline and
under GitHub Pages, with no fetch / no server).

Usage
-----
    python3 scripts/build_results_dashboard.py
    python3 scripts/build_results_dashboard.py --results results --out docs/results-dashboard.html
    python3 scripts/build_results_dashboard.py --no-embed-artifacts   # link-only mode

The output is a single file: no CDN, no fonts, no JS dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Artifacts larger than this stay external (linked) to keep the board loadable.
EMBED_LIMIT_BYTES = 800_000
# Long prompts are truncated in the board; the full text stays in the pack.
PROMPT_LIMIT_CHARS = 2_000

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_OTHER = "other"


# ---------------------------------------------------------------- helpers


def read_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def strip_prompt_comment(text: str) -> str:
    return re.sub(r"^\s*<!--.*?-->\s*", "", text, count=1, flags=re.S).strip()


def collapse(text: str, limit: int) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def as_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


# ---------------------------------------------------------------- loading


def load_taxonomy(root: pathlib.Path) -> dict:
    return read_json(root / "tasks" / "taxonomy.json") or {}


def load_task_meta(root: pathlib.Path, task_id: str, taxonomy: dict) -> dict | None:
    pack = root / "tasks" / task_id
    spec = read_json(pack / "task.json")
    if spec is None and task_id not in (taxonomy.get("tasks") or {}):
        return None
    spec = spec or {"task_id": task_id}
    tax = (taxonomy.get("tasks") or {}).get(task_id, {})

    prompt_path = pack / "prompt.md"
    prompt = ""
    if prompt_path.exists():
        prompt = strip_prompt_comment(prompt_path.read_text(encoding="utf-8", errors="replace"))

    assertions = []
    apath = pack / "assertions" / "task.json"
    if apath.exists():
        raw = read_json(apath) or {}
        for a in raw.get("assertions") or []:
            assertions.append({
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "kind": a.get("kind", ""),
                "dimension": a.get("dimension", "F"),
                "pattern": a.get("pattern", "") or a.get("selector", "") or "",
            })

    meta_test = read_json(pack / "assertions" / "meta_test.json") or {}
    mt_status = (meta_test.get("meta_test") or {}).get("status") or meta_test.get("status")

    return {
        "id": task_id,
        "title": spec.get("title") or task_id,
        "set": tax.get("set") or spec.get("set") or "",
        "set_label": tax.get("set_label") or ("Core-111" if spec.get("set") == "core" else "Extended"),
        "primary": tax.get("primary") or "",
        "primary_track": tax.get("primary_track") or spec.get("domains", [""])[0] if spec.get("domains") else tax.get("primary_track") or "",
        "tracks": tax.get("tracks") or spec.get("domains") or [],
        "tech": tax.get("tech") or [],
        "reference_kind": tax.get("reference_kind") or spec.get("reference_kind") or "",
        "has_reference_oracle": bool(tax.get("reference_kind") == "runnable-html" or spec.get("has_reference_oracle")),
        "meta_test": mt_status or "",
        "prompt_chars": len(prompt) or as_int(spec.get("prompt_chars")),
        "prompt_excerpt": collapse(prompt, 260),
        "prompt": prompt,
        "assertion_target": as_int(spec.get("assertion_target"), len(assertions)),
        "assertions": assertions,
        "reference_url": spec.get("reference_url") or "",
        "source_post_url": spec.get("source_post_url") or "",
        "creator": (spec.get("attribution") or {}).get("creator") or "",
        "budget": read_json(pack / "budget.json") or {},
    }


def load_run(root: pathlib.Path, run_dir: pathlib.Path) -> dict:
    cfg = read_json(run_dir / "config.json") or {}
    configs = {c.get("id"): c for c in cfg.get("configurations") or []}
    judge_cfg = next((c for c in cfg.get("configurations") or [] if c.get("role") == "judge"), {})
    target_cfgs = [c for c in cfg.get("configurations") or [] if c.get("role", "target") == "target"]

    # Derived companion produced by scripts/rescore_artifacts.py. It is NOT a
    # replacement of outcomes.csv: the original row is kept as old_* for audit.
    rescore: dict[tuple, dict] = {}
    rpath = run_dir / "rescored.csv"
    if rpath.exists():
        with rpath.open(encoding="utf-8", newline="") as fh:
            for rr in csv.DictReader(fh):
                rescore[(rr.get("config_id", ""), rr.get("task_id", ""),
                         as_int(rr.get("repetition"), 1))] = rr

    judges: dict[str, list] = {}
    jpath = run_dir / "judge.csv"
    if jpath.exists():
        with jpath.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                artifact = row.get("artifact") or ""
                judges.setdefault(artifact, []).append({
                    "assertion_id": row.get("assertion_id", ""),
                    "assertion_name": row.get("assertion_name", ""),
                    "verdict": (row.get("verdict") or "").upper(),
                    "reason": row.get("reason", ""),
                    "judge_model": row.get("judge_model", ""),
                    "judge_tokens": as_int(row.get("judge_tokens")),
                })

    notes: dict[str, dict] = {}
    notes_dir = run_dir / "delivery_notes"
    if notes_dir.exists():
        for p in sorted(notes_dir.glob("*.md")):
            data = read_json(p)
            if isinstance(data, dict):
                notes[p.stem] = data

    traces: dict[str, list] = {}
    trace_dir = run_dir / "traces"
    if trace_dir.exists():
        for p in sorted(trace_dir.glob("*.jsonl")):
            events = []
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                events.append({
                    "step": ev.get("step", ""),
                    "action": ev.get("action", ""),
                    "target": ev.get("target", ""),
                    "observation": ev.get("observation", ""),
                })
            traces[p.stem] = events

    artifacts_dir = run_dir / "artifacts"
    results = []
    opath = run_dir / "outcomes.csv"
    if opath.exists():
        with opath.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                task_id = row.get("task_id") or ""
                cfg_id = row.get("config_id") or ""
                rep = as_int(row.get("repetition"), 1)
                art_name = f"{cfg_id}__{task_id}__r{rep}.html"
                art_path = artifacts_dir / art_name
                if not art_path.exists():
                    candidates = sorted(artifacts_dir.glob(f"{cfg_id}__{task_id}__r*.*")) if artifacts_dir.exists() else []
                    if candidates:
                        art_path = candidates[0]
                        art_name = candidates[0].name

                passed = as_bool(row.get("pass_at_budget"))
                error = (row.get("error") or "").strip()
                if passed:
                    status = STATUS_PASS
                elif error:
                    status = STATUS_OTHER
                else:
                    status = STATUS_FAIL

                cfg_entry = configs.get(cfg_id, {})
                rs = rescore.get((cfg_id, task_id, rep))
                rec = {
                    "run_id": run_dir.name,
                    "run_config": cfg,
                    "task_id": task_id,
                    "config_id": cfg_id,
                    "model": row.get("model") or cfg_entry.get("model", ""),
                    "harness": row.get("harness") or cfg_entry.get("harness", ""),
                    "harness_impl": row.get("harness_impl") or cfg_entry.get("harness_impl", "") or row.get("harness") or cfg_entry.get("harness", ""),
                    "harness_version": row.get("harness_version") or cfg_entry.get("harness_version", ""),
                    "protocol": cfg_entry.get("protocol", ""),
                    "base_url": cfg_entry.get("base_url", ""),
                    "params": cfg_entry.get("params", {}),
                    "judge_model": row.get("judge_model") or judge_cfg.get("model", ""),
                    "split": row.get("split", ""),
                    "track": row.get("track", ""),
                    "repetition": rep,
                    "status": status,
                    "pass_at_budget": passed,
                    "final_score": as_float(row.get("final_score")),
                    "F": as_float(row.get("F")),
                    "R": as_float(row.get("R")),
                    "V": as_float(row.get("V")),
                    "E": as_float(row.get("E")),
                    "quality_given_pass": as_float(row.get("quality_given_pass")),
                    "self_assessed_completion": as_float(row.get("self_assessed_completion")),
                    "unverified_claims": as_int(row.get("unverified_claims")),
                    "claimed_checks": as_int(row.get("claimed_checks")),
                    "trace_verified_checks": as_int(row.get("trace_verified_checks")),
                    "l0_pass": as_int(row.get("l0_pass")),
                    "l0_fail": as_int(row.get("l0_fail")),
                    "l0_skip": as_int(row.get("l0_skip")),
                    "l1_pass": as_int(row.get("l1_pass")),
                    "l1_fail": as_int(row.get("l1_fail")),
                    "tokens_out": as_int(row.get("tokens_out")),
                    "evaluation_ready": as_bool(row.get("evaluation_ready")),
                    "dry_run": as_bool(row.get("dry_run")),
                    "error": error,
                    "notes": row.get("notes", ""),
                    "artifact": art_name,
                    "artifact_path": str(art_path.relative_to(root)) if art_path.exists() else "",
                    "artifact_bytes": art_path.stat().st_size if art_path.exists() else 0,
                    "judge": judges.get(art_name, []),
                    "delivery": notes.get(pathlib.Path(art_name).stem, {}),
                    "trace": traces.get(pathlib.Path(art_name).stem, []),
                    "rescored": bool(rs),
                    "old_pass": (rs or {}).get("old_pass", ""),
                    "old_score": (rs or {}).get("old_score", ""),
                    "old_notes": (rs or {}).get("old_notes", ""),
                    "truncated": as_bool((rs or {}).get("truncated")),
                }
                if rs:
                    npass = as_bool(rs.get("new_pass"))
                    rec.update({
                        "pass_at_budget": npass,
                        "status": STATUS_PASS if npass else (STATUS_OTHER if error else STATUS_FAIL),
                        "final_score": as_float(rs.get("new_score")),
                        "F": as_float(rs.get("F")), "R": as_float(rs.get("R")),
                        "V": as_float(rs.get("V")), "E": as_float(rs.get("E")),
                        "quality_given_pass": as_float(rs.get("new_score")),
                        "l0_pass": as_int(rs.get("l0_pass")), "l0_fail": as_int(rs.get("l0_fail")),
                        "l0_skip": as_int(rs.get("l0_skip")),
                        "l1_pass": as_int(rs.get("l1_pass")), "l1_fail": as_int(rs.get("l1_fail")),
                        "notes": rs.get("new_notes", ""),
                    })
                results.append(rec)

    return {
        "run_id": run_dir.name,
        "date": datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds"),
        "track": cfg.get("track", ""),
        "mode": cfg.get("mode", ""),
        "split": cfg.get("split", ""),
        "repetitions": cfg.get("repetitions", 1),
        "budget": cfg.get("budget", {}),
        "measurements": cfg.get("measurements", []),
        "task_count": cfg.get("task_count", 0),
        "judge_model": judge_cfg.get("model", ""),
        "targets": [{"id": c.get("id"), "model": c.get("model"), "harness": c.get("harness")} for c in target_cfgs],
        "results": results,
    }


def load_runs(root: pathlib.Path, results_dir: pathlib.Path) -> list[dict]:
    runs = []
    for d in sorted(results_dir.iterdir() if results_dir.exists() else [], reverse=True):
        if d.is_dir() and (d / "outcomes.csv").exists():
            runs.append(load_run(root, d))
    return runs


# ---------------------------------------------------------------- template


def build_payload(root: pathlib.Path, results_dir: pathlib.Path, embed_artifacts: bool) -> dict:
    taxonomy = load_taxonomy(root)
    runs = load_runs(root, results_dir)

    all_results = [r for run in runs for r in run["results"]]
    rescored_count = sum(1 for r in all_results if r.get("rescored"))
    seen = {r["task_id"] for r in all_results}
    known = set((taxonomy.get("tasks") or {}).keys())
    for run in runs:
        for r in run["results"]:
            known.add(r["task_id"])

    tasks = {}
    for tid in sorted(known):
        meta = load_task_meta(root, tid, taxonomy)
        if not meta:
            continue
        prompt = meta.get("prompt") or ""
        if tid not in seen:
            # Only tasks that actually ran carry the full text; the rest keep an
            # excerpt so the board stays small (full text lives in the pack).
            meta["prompt"] = ""
            meta["assertion_target"] = len(meta.get("assertions") or []) or meta.get("assertion_target", 0)
            meta["assertions"] = []
        elif len(prompt) > PROMPT_LIMIT_CHARS:
            meta["prompt"] = prompt[:PROMPT_LIMIT_CHARS].rstrip() + "\n\n[… 原文过长，已截断；完整 prompt 见 tasks/%s/prompt.md]" % tid
            meta["prompt_truncated"] = True
        tasks[tid] = meta

    artifacts = {}
    for run in runs:
        for r in run["results"]:
            name = r["artifact"]
            if not name or name in artifacts:
                continue
            path = root / r["artifact_path"] if r["artifact_path"] else None
            entry = {"bytes": r["artifact_bytes"], "embedded": False, "html": "", "reason": ""}
            if path and path.exists():
                if embed_artifacts and path.stat().st_size <= EMBED_LIMIT_BYTES:
                    entry["html"] = path.read_text(encoding="utf-8", errors="replace")
                    entry["embedded"] = True
                else:
                    entry["reason"] = "artifact exceeds embed limit" if embed_artifacts else "embedding disabled"
            else:
                entry["reason"] = "artifact file missing"
            entry["path"] = r["artifact_path"]
            artifacts[name] = entry

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "repo": "momozi1996/Code-Everything-Bench",
        "task_total": len(tasks),
        "rescored_count": rescored_count,
        "runs": [{k: v for k, v in run.items() if k != "results"} for run in runs],
        "tasks": tasks,
        "results": all_results,
        "artifacts": artifacts,
        "axes": {
            "primary": sorted((taxonomy.get("axes") or {}).get("primary", {}).keys()),
            "tech": sorted((taxonomy.get("axes") or {}).get("tech", {}).keys()),
        },
    }


def emit(payload: dict, out_path: pathlib.Path) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html_doc = TEMPLATE.replace("@@GENERATED@@", payload["generated_at"]).replace("@@DATA@@", data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the CE-Bench results dashboard.")
    ap.add_argument("--results", default="results", help="results directory to scan")
    ap.add_argument("--out", default="docs/results-dashboard.html", help="output html path")
    ap.add_argument("--no-embed-artifacts", dest="embed", action="store_false", help="link artifacts instead of embedding")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    results_dir = (ROOT / args.results).resolve() if not pathlib.Path(args.results).is_absolute() else pathlib.Path(args.results)
    out_path = (ROOT / args.out).resolve() if not pathlib.Path(args.out).is_absolute() else pathlib.Path(args.out)

    payload = build_payload(ROOT, results_dir, args.embed)
    emit(payload, out_path)

    if not args.quiet:
        n_runs = len(payload["runs"])
        n_res = len(payload["results"])
        n_pass = sum(1 for r in payload["results"] if r["status"] == STATUS_PASS)
        embedded = sum(1 for a in payload["artifacts"].values() if a["embedded"])
        size_kb = out_path.stat().st_size / 1024
        print(f"runs={n_runs} results={n_res} pass={n_pass} tasks={payload['task_total']} "
              f"artifacts_embedded={embedded}/{len(payload['artifacts'])}")
        print(f"wrote {out_path.relative_to(ROOT)}  ({size_kb:.1f} KB)")
    return 0


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CE-Bench · 评测结果看板</title>
<style>
  :root{
    --bg:#f5f4f1; --panel:#ffffff; --panel-2:#faf9f7;
    --ink:#15171c; --ink-2:#454b55; --muted:#8b9099;
    --line:#e4e1da; --line-2:#efedE8;
    --accent:#2b46f0; --accent-soft:#eef1ff;
    --pass:#0f7a52; --pass-soft:#e8f5ee;
    --fail:#bd2a1d; --fail-soft:#fbecea;
    --warn:#996200; --warn-soft:#fdf3e0;
    --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,"Cascadia Mono",monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:13.5px;line-height:1.5;-webkit-font-smoothing:antialiased}
  button{font-family:inherit;cursor:pointer}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .mono{font-family:var(--mono);font-variant-numeric:tabular-nums}

  /* ---------- header ---------- */
  header{position:sticky;top:0;z-index:40;background:rgba(245,244,241,.86);backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line)}
  .hrow{max-width:1560px;margin:0 auto;padding:14px 24px 12px;display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap}
  .brand{display:flex;flex-direction:column;gap:2px;min-width:210px}
  .brand h1{margin:0;font-size:17px;font-weight:700;letter-spacing:-.015em;display:flex;align-items:center;gap:8px}
  .brand h1 .dot{width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
  .brand .sub{font-size:11.5px;color:var(--muted);letter-spacing:.01em}
  .hmeta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-left:auto}
  .chip{display:inline-flex;align-items:center;gap:5px;height:24px;padding:0 9px;border-radius:6px;background:var(--panel);border:1px solid var(--line);font-size:11.5px;color:var(--ink-2);white-space:nowrap}
  .chip b{font-weight:600;color:var(--ink)}
  .chip .k{color:var(--muted)}
  select.ctl{height:28px;border:1px solid var(--line);border-radius:6px;background:var(--panel);padding:0 8px;font-size:12px;color:var(--ink);font-family:inherit;outline:none}
  select.ctl:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}

  /* ---------- kpi ---------- */
  .kpis{max-width:1560px;margin:0 auto;padding:0 24px 14px;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}
  @media(max-width:1100px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
  @media(max-width:620px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr));padding:0 14px 12px}}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px 11px;display:flex;flex-direction:column;gap:3px;min-width:0}
  .kpi .lab{font-size:11px;color:var(--muted);letter-spacing:.03em;text-transform:uppercase}
  .kpi .val{font-family:var(--mono);font-size:21px;font-weight:600;letter-spacing:-.02em;line-height:1.15}
  .kpi .val small{font-size:12px;color:var(--muted);font-weight:500;margin-left:2px}
  .kpi .aux{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .kpi.bar{position:relative;overflow:hidden}
  .kpi .spark{position:absolute;left:0;bottom:0;height:2px;background:var(--accent);opacity:.55}

  /* ---------- toolbar ---------- */
  .toolbar{max-width:1560px;margin:0 auto;padding:0 24px 10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .segs{display:inline-flex;background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:2px;gap:2px}
  .segs button{border:0;background:transparent;border-radius:5px;height:24px;padding:0 10px;font-size:12px;color:var(--ink-2);display:inline-flex;align-items:center;gap:5px}
  .segs button .n{font-family:var(--mono);font-size:10.5px;color:var(--muted)}
  .segs button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .segs button[aria-pressed="true"] .n{color:rgba(255,255,255,.65)}
  .search{position:relative;flex:1;min-width:180px;max-width:320px}
  .search input{width:100%;height:30px;border:1px solid var(--line);border-radius:7px;background:var(--panel);padding:0 10px 0 28px;font-size:12.5px;font-family:inherit;color:var(--ink);outline:none}
  .search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
  .search .ico{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:12px}
  .spacer{flex:1}
  .ghost{height:28px;border:1px solid var(--line);background:var(--panel);border-radius:6px;padding:0 10px;font-size:12px;color:var(--ink-2)}
  .ghost:hover{border-color:#cfcbc2;color:var(--ink)}

  /* ---------- table ---------- */
  .wrap{max-width:1560px;margin:0 auto;padding:0 24px 60px}
  .board{background:var(--panel);border:1px solid var(--line);border-radius:11px;overflow:clip}
  table{width:100%;border-collapse:collapse;table-layout:fixed}
  thead th{position:sticky;top:var(--sticky,73px);z-index:20;background:var(--panel-2);border-bottom:1px solid var(--line);font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;text-align:left;padding:8px 12px;white-space:nowrap}
  tbody td{border-bottom:1px solid var(--line-2);padding:9px 12px;vertical-align:middle}
  tbody tr:last-child td{border-bottom:0}
  tbody tr.row{cursor:pointer;transition:background .12s}
  tbody tr.row:hover{background:#fbfaf8}
  tbody tr.row.open{background:var(--accent-soft);box-shadow:inset 3px 0 0 var(--accent)}
  th.c-status{width:88px} th.c-task{width:auto} th.c-model{width:266px}
  th.c-score{width:152px} th.c-assert{width:146px} th.c-tok{width:82px} th.c-art{width:88px}
  .imodel{display:none;font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .imodel.on{display:block}
  @media(max-width:620px){ .kpis{grid-template-columns:1fr 1fr} .hmeta{margin-left:0} .hrow{padding:12px 14px 10px} .wrap,.toolbar,.kpis{padding-left:14px;padding-right:14px} }
  .badge{display:inline-flex;align-items:center;gap:5px;height:21px;padding:0 8px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:.02em}
  .badge.pass{background:var(--pass-soft);color:var(--pass)}
  .badge.fail{background:var(--fail-soft);color:var(--fail)}
  .badge.other{background:var(--warn-soft);color:var(--warn)}
  .badge.idle{background:#f1f0ec;color:var(--muted);font-weight:500}
  .badge i{width:5px;height:5px;border-radius:50%;background:currentColor;display:block}
  .tname{display:flex;flex-direction:column;gap:2px;min-width:0}
  .tname .ttl{font-size:13px;font-weight:550;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .tname .meta{display:flex;gap:6px;align-items:center;font-size:11px;color:var(--muted);flex-wrap:wrap}
  .tag{display:inline-block;padding:0 5px;height:16px;line-height:16px;border-radius:4px;background:#f3f2ee;color:var(--ink-2);font-size:10.5px;font-family:var(--mono)}
  .tag.core{background:#eef1ff;color:#2b3bb5}
  .tag.ext{background:#f6efe6;color:#8a5a12}
  .mcell{display:flex;flex-direction:column;gap:1px;min-width:0}
  .mcell .m1{font-size:11.5px;font-family:var(--mono);color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mcell .m2{font-size:10.5px;font-family:var(--mono);color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .score{display:flex;flex-direction:column;gap:4px}
  .score .top{display:flex;align-items:baseline;gap:6px}
  .score .n{font-family:var(--mono);font-size:14px;font-weight:600;letter-spacing:-.01em}
  .score .frv{font-size:10px;color:var(--muted);font-family:var(--mono);white-space:nowrap;letter-spacing:-.02em}
  .track{height:3px;border-radius:2px;background:#efeee9;overflow:hidden}
  .track > i{display:block;height:100%;border-radius:2px;background:var(--ink)}
  .track.pass > i{background:var(--pass)}
  .track.fail > i{background:var(--fail)}
  .asserts{font-family:var(--mono);font-size:11px;display:flex;gap:11px;white-space:nowrap;letter-spacing:-.02em}
  .asserts span.grp{display:inline-flex;align-items:center;gap:1px}
  .asserts .lab{color:var(--muted);margin-right:3px;font-family:var(--sans);font-size:10px;letter-spacing:.02em}
  .asserts .ok{color:var(--pass);font-weight:600} .asserts .no{color:var(--fail);font-weight:600} .asserts .sk{color:#a8adb5}
  .asserts .sep{color:#cfd3d8}
  .btn-res{border:1px solid var(--line);background:var(--panel);border-radius:5px;height:23px;padding:0 8px;font-size:11px;color:var(--ink-2);display:inline-flex;align-items:center;gap:4px}
  .btn-res:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
  .btn-res[disabled]{opacity:.4;cursor:not-allowed}
  .grouprow td{background:var(--panel-2);padding:0}
  .groupbtn{width:100%;border:0;background:transparent;padding:9px 12px;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-2);text-align:left}
  .groupbtn:hover{color:var(--ink)}
  .groupbtn .g{font-family:var(--mono);font-size:10.5px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:0 6px;height:17px;line-height:16px}
  .empty{padding:56px 24px;text-align:center;color:var(--muted);font-size:13px}

  /* ---------- detail overlay ---------- */
  .scrim{position:fixed;inset:0;background:rgba(20,22,26,.32);opacity:0;pointer-events:none;transition:opacity .18s;z-index:60}
  .scrim.on{opacity:1;pointer-events:auto}
  .sheet{position:fixed;top:0;right:0;bottom:0;width:min(1240px,97vw);background:var(--bg);z-index:61;display:flex;flex-direction:column;transform:translateX(100%);transition:transform .22s cubic-bezier(.32,.72,0,1);box-shadow:-24px 0 60px rgba(20,22,26,.16)}
  .sheet.on{transform:translateX(0)}
  .sheet-head{background:var(--panel);border-bottom:1px solid var(--line);padding:14px 20px 0;flex:0 0 auto}
  .sheet-top{display:flex;align-items:flex-start;gap:14px}
  .sheet-id{font-family:var(--mono);font-size:11.5px;color:var(--muted);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .sheet-title{font-size:17px;font-weight:650;letter-spacing:-.015em;margin:2px 0 0;line-height:1.35}
  .xbtn{margin-left:auto;border:1px solid var(--line);background:var(--panel);width:28px;height:28px;border-radius:7px;font-size:14px;color:var(--muted);display:grid;place-items:center;flex:0 0 auto}
  .xbtn:hover{color:var(--ink);border-color:#cfcbc2}
  .tabs{display:flex;gap:2px;margin-top:12px}
  .tabs button{border:0;background:transparent;padding:8px 11px 9px;font-size:12.5px;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px}
  .tabs button:hover{color:var(--ink-2)}
  .tabs button[aria-selected="true"]{color:var(--ink);font-weight:600;border-bottom-color:var(--ink)}
  .sheet-body{flex:1;overflow:auto;padding:16px 20px 40px}
  .pane{display:none} .pane.on{display:block}

  .grid2{display:grid;grid-template-columns:1.05fr .95fr;gap:14px;align-items:start}
  @media(max-width:1000px){.grid2{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px 14px}
  .card h3{margin:0 0 10px;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;display:flex;align-items:center;gap:7px}
  .card h3 .rule{flex:1;height:1px;background:var(--line-2)}
  .kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:12.5px}
  .kv dt{color:var(--muted);white-space:nowrap}
  .kv dd{margin:0;font-family:var(--mono);font-size:12px;color:var(--ink);word-break:break-all}
  .metric{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
  .metric > div{background:var(--panel-2);border:1px solid var(--line-2);border-radius:8px;padding:8px 9px}
  .metric .k{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  .metric .v{font-family:var(--mono);font-size:16px;font-weight:600;margin-top:1px}
  .barline{display:flex;align-items:center;gap:8px;margin-top:7px}
  .barline .b{flex:1;height:6px;border-radius:3px;background:#efeee9;overflow:hidden}
  .barline .b > i{display:block;height:100%;background:var(--ink)}
  .barline .b.p > i{background:var(--pass)} .barline .b.f > i{background:var(--fail)}
  ul.clean{margin:0;padding-left:16px;font-size:12.5px;color:var(--ink-2)}
  ul.clean li{margin:3px 0}
  .pill{display:inline-flex;align-items:center;gap:5px;padding:1px 7px;border-radius:999px;font-size:10.5px;font-family:var(--mono);background:#f3f2ee;color:var(--ink-2)}
  .pill.p{background:var(--pass-soft);color:var(--pass)} .pill.f{background:var(--fail-soft);color:var(--fail)} .pill.s{background:#f1f0ec;color:var(--muted)}
  pre.code{margin:0;background:#1b1d22;color:#e8e6e1;border-radius:8px;padding:10px 12px;font-family:var(--mono);font-size:11.5px;line-height:1.6;overflow:auto;white-space:pre-wrap;word-break:break-word}

  /* preview */
  .pv-bar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:10px}
  .pv-wrap{background:#e9e7e1;border:1px solid var(--line);border-radius:10px;padding:10px;display:flex;justify-content:center;min-height:60vh}
  .pv-wrap iframe{background:#fff;border:0;border-radius:6px;width:100%;height:72vh;box-shadow:0 2px 14px rgba(20,22,26,.10)}
  .pv-wrap.dev iframe{box-shadow:0 8px 30px rgba(20,22,26,.18)}
  .no-pv{padding:40px 20px;text-align:center;color:var(--muted);font-size:13px;background:var(--panel);border:1px dashed var(--line);border-radius:10px;width:100%}

  /* judge / trace */
  .jitem{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--line-2);font-size:12.5px}
  .jitem:last-child{border-bottom:0}
  .jitem .jt{flex:0 0 auto;font-family:var(--mono);font-size:11px;color:var(--muted)}
  .jitem > .pill{flex:0 0 auto;align-self:flex-start;white-space:nowrap;min-width:44px;justify-content:center;margin-top:1px}
  .jitem .jr{margin-top:2px;color:var(--ink-2);font-size:12px}
  .trace{font-family:var(--mono);font-size:11.5px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .trow{display:grid;grid-template-columns:34px 130px 1fr;gap:0;border-bottom:1px solid var(--line-2)}
  .trow:last-child{border-bottom:0}
  .trow > div{padding:6px 9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .trow .s{color:var(--muted);text-align:right;padding-right:2px}
  .trow .a{color:var(--accent);font-weight:500}
  .trow .o{color:var(--ink-2);font-family:var(--sans);font-size:12px;white-space:normal}
  .promptbox{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;font-size:13px;line-height:1.7;white-space:pre-wrap;color:var(--ink-2);max-height:62vh;overflow:auto}
  .legend{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;margin-top:14px;padding:14px 16px;background:var(--panel);border:1px solid var(--line);border-radius:10px}
  @media(max-width:1100px){.legend{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:640px){.legend{grid-template-columns:1fr}}
  .legend h4{margin:0 0 5px;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
  .legend p{margin:0;font-size:11.5px;line-height:1.6;color:var(--ink-2)}
  .legend code{font-family:var(--mono);font-size:10.5px;background:#f2f1ec;padding:1px 4px;border-radius:3px}
  .rnotice{max-width:1560px;margin:0 auto 12px;padding:10px 14px;border:1px solid #c9b98e;background:#fbf7e8;border-radius:9px;font-size:12px;line-height:1.6;color:#5c512f}
  .rnotice b{color:#3d3520}
  .rnotice code{font-family:var(--mono);font-size:10.5px;background:#f0ead4;padding:1px 4px;border-radius:3px}
  .rv{display:inline-block;font-family:var(--mono);font-size:9.5px;color:#8a6d1f;background:#fbf3d9;border:1px solid #e5d7a6;border-radius:3px;padding:0 4px;margin-left:5px;vertical-align:1px}
  .foot{max-width:1560px;margin:0 auto;padding:0 24px 40px;color:var(--muted);font-size:11.5px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
  .foot code{font-family:var(--mono);background:#ecebe6;padding:1px 5px;border-radius:4px;color:var(--ink-2)}
</style>
</head>
<body>

<header>
  <div class="hrow">
    <div class="brand">
      <h1><span class="dot"></span>CE-Bench 评测结果看板</h1>
      <div class="sub">Code-Everything Bench · per-task evidence board</div>
    </div>
    <div class="hmeta" id="hmeta"></div>
  </div>
  <div class="kpis" id="kpis"></div>
  <div class="toolbar">
    <div class="segs" id="statusSegs"></div>
    <div class="search"><span class="ico">⌕</span><input id="q" placeholder="搜索题号 / 标题 / 标签  ( / 聚焦 )" autocomplete="off"></div>
    <select class="ctl" id="fRun"></select>
    <select class="ctl" id="fSet"></select>
    <select class="ctl" id="fPrimary"></select>
    <div class="spacer"></div>
    <select class="ctl" id="fSort">
      <option value="score">按得分</option>
      <option value="id">按题号</option>
      <option value="tokens">按 tokens</option>
    </select>
    <button class="ghost" id="btnExpand">展开未跑</button>
  </div>
</header>

<div class="wrap">
  <div class="rnotice" id="rnotice" style="display:none"></div>
  <div class="board">
    <table>
      <thead id="thead"></thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="empty" id="empty" style="display:none">没有匹配的记录。</div>
  </div>
  <div class="legend">
    <div><h4>结果状态</h4><p><b>PASS</b> = Gate 5 项否决全过且有效断言全通过；<b>FAIL</b> = 有效断言未全过；<b>未跑</b> = 该批次无记录，<strong>不是 0 分</strong>。</p></div>
    <div><h4>断言</h4><p><b>L0</b> 每题 8 条通用合约（<code>通过·失败·跳过</code>）；<b>L1</b> 题目专属约 9 条（<code>通过·失败</code>，无 Chromium 记 SKIP）。</p></div>
    <div><h4>得分</h4><p><code>final_score</code> 0–1；F 功能 / R 约束 / V 视觉，V 由固定 <code>deepseek-v4.1-flash-1017</code> 多模态判定。</p></div>
    <div><h4>产物</h4><p>点行内「预览」即在沙箱 iframe 渲染模型交付的 HTML——产物即证据，不做二次美化。</p></div>
  </div>
</div>

<div class="foot" id="foot"></div>

<div class="scrim" id="scrim"></div>
<aside class="sheet" id="sheet" role="dialog" aria-modal="true" aria-label="题目详情">
  <div class="sheet-head">
    <div class="sheet-top">
      <div style="min-width:0">
        <div class="sheet-id" id="sId"></div>
        <h2 class="sheet-title" id="sTitle"></h2>
      </div>
      <button class="xbtn" id="btnClose" aria-label="关闭">✕</button>
    </div>
    <div class="tabs" id="tabs"></div>
  </div>
  <div class="sheet-body" id="sBody"></div>
</aside>

<script id="db" type="application/json">@@DATA@@</script>
<script>
(function(){
  const DB = JSON.parse(document.getElementById('db').textContent);
  const TASKS = DB.tasks || {}, RESULTS = DB.results || [], RUNS = DB.runs || [], ART = DB.artifacts || {};
  const $ = s => document.querySelector(s);
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = v => (v==null||isNaN(v)) ? '—' : (v*100).toFixed(1);
  const num = (v,d=2) => (v==null||isNaN(v)) ? '—' : Number(v).toFixed(d);
  const sampling = p => Object.keys(p||{}).length ? Object.entries(p).map(([k,v])=>`${k}=${v}`).join(' · ') : '默认';
  const bytes = n => n>1024*1024 ? (n/1048576).toFixed(1)+' MB' : n>1024 ? Math.round(n/1024)+' KB' : (n||0)+' B';

  const state = {status:'all', q:'', run:'all', set:'all', primary:'all', sort:'score', expanded:false, open:null, tab:'preview', device:'fit'};

  // ---------- rows ----------
  const rows = RESULTS.map(r => {
    const t = TASKS[r.task_id] || {};
    return Object.assign({}, r, {title:t.title||r.task_id, set:t.set||'', set_label:t.set_label||'', primary:t.primary||'', tech:t.tech||[], tracks:t.tracks||[], meta:t});
  });
  const ranIds = new Set(rows.map(r=>r.task_id));
  const unran = Object.keys(TASKS).filter(id=>!ranIds.has(id)).map(id=>Object.assign({task_id:id, unrun:true}, TASKS[id]));

  function filtered(){
    let list = rows.slice();
    if(state.run!=='all') list = list.filter(r=>r.run_id===state.run);
    if(state.status==='pass') list = list.filter(r=>r.status==='pass');
    if(state.status==='fail') list = list.filter(r=>r.status!=='pass');
    if(state.set!=='all') list = list.filter(r=>r.set===state.set);
    if(state.primary!=='all') list = list.filter(r=>r.primary===state.primary);
    if(state.q){
      const q = state.q.toLowerCase();
      list = list.filter(r => [r.task_id,r.title,r.model,r.harness,(r.tech||[]).join(' '),(r.tracks||[]).join(' ')].join(' ').toLowerCase().includes(q));
    }
    const key = state.sort;
    list.sort((a,b)=>{
      if(key==='score'){
        const d = (b.final_score??-1)-(a.final_score??-1);
        return d!==0?d:a.task_id.localeCompare(b.task_id);
      }
      if(key==='tokens') return (b.tokens_out||0)-(a.tokens_out||0);
      return a.task_id.localeCompare(b.task_id);
    });
    return list;
  }
  function filteredUnran(){
    let list = unran.slice();
    if(state.set!=='all') list = list.filter(r=>r.set===state.set);
    if(state.primary!=='all') list = list.filter(r=>r.primary===state.primary);
    if(state.q){
      const q = state.q.toLowerCase();
      list = list.filter(r => [r.id,r.title,r.primary,(r.tech||[]).join(' ')].join(' ').toLowerCase().includes(q));
    }
    return list;
  }

  // ---------- header ----------
  const runDates = RUNS.map(r=>r.run_id);
  const judge = (RUNS.find(r=>r.judge_model)||{}).judge_model || '—';
  const nets = [...new Set(RUNS.map(r=>(r.budget||{}).network).filter(Boolean))];
  $('#hmeta').innerHTML = [
    `<span class="chip"><span class="k">批次</span><b>${RUNS.length}</b></span>`,
    `<span class="chip"><span class="k">题库</span><b>${DB.task_total}</b></span>`,
    `<span class="chip"><span class="k">judge</span><b>${esc(judge)}</b></span>`,
    nets.length?`<span class="chip"><span class="k">network</span><b>${esc(nets.join('/'))}</b></span>`:'',
    `<span class="chip"><span class="k">生成</span><b class="mono">${esc((DB.generated_at||'').replace('T',' ').slice(0,16))}</b></span>`
  ].join('');

  // ---------- kpis ----------
  const nRun = rows.length, nPass = rows.filter(r=>r.status==='pass').length;
  const avg = nRun? rows.reduce((s,r)=>s+(r.final_score||0),0)/nRun : null;
  const tok = rows.reduce((s,r)=>s+(r.tokens_out||0),0);
  const jfail = rows.reduce((s,r)=>s+(r.judge||[]).filter(j=>j.verdict==='FAIL').length,0);
  const cover = DB.task_total ? nRun/DB.task_total : 0;
  const kp = (lab,val,aux,spark)=>`<div class="kpi"><div class="lab">${lab}</div><div class="val">${val}</div><div class="aux">${aux||''}</div>${spark!=null?`<div class="spark" style="width:${Math.max(2,Math.min(100,spark*100))}%"></div>`:''}</div>`;
  $('#kpis').innerHTML = [
    kp('已跑题目', `${nRun}<small>/ ${DB.task_total}</small>`, `覆盖 ${(cover*100).toFixed(1)}% · ${RUNS.length} 个批次`, cover),
    kp('通过', `${nPass}<small>/${nRun}</small>`, nRun?`通过率 ${(nPass/nRun*100).toFixed(0)}%`:'—', nRun?nPass/nRun:0),
    kp('平均 final_score', avg==null?'—':num(avg), '满分 1.000'),
    kp('输出 tokens', tok.toLocaleString(), '所有目标模型合计'),
    kp('judge FAIL', jfail, '多模态判定未通过条目'),
    kp('产物文件', `${Object.keys(ART).length}`, `已嵌入预览 ${Object.values(ART).filter(a=>a.embedded).length}`)
  ].join('');

  // ---------- controls ----------
  const segs = [['all','全部',rows.length],['pass','通过',nPass],['fail','未通过',nRun-nPass]];
  $('#statusSegs').innerHTML = segs.map(([k,l,n])=>`<button data-k="${k}" aria-pressed="${state.status===k}">${l}<span class="n">${n}</span></button>`).join('');
  $('#statusSegs').addEventListener('click', e=>{
    const b = e.target.closest('button'); if(!b) return;
    state.status = b.dataset.k;
    [...$('#statusSegs').children].forEach(x=>x.setAttribute('aria-pressed', x.dataset.k===state.status));
    render();
  });

  $('#fRun').innerHTML = `<option value="all">全部批次 (${RUNS.length})</option>` + RUNS.map(r=>`<option value="${esc(r.run_id)}">${esc(r.run_id)}</option>`).join('');
  const sets = [...new Set(Object.values(TASKS).map(t=>t.set).filter(Boolean))];
  $('#fSet').innerHTML = `<option value="all">全部层级</option>` + sets.map(s=>`<option value="${esc(s)}">${s==='core'?'Core-111':'Extended-69'}</option>`).join('');
  const prims = [...new Set(Object.values(TASKS).map(t=>t.primary).filter(Boolean))].sort();
  $('#fPrimary').innerHTML = `<option value="all">全部主类</option>` + prims.map(p=>`<option value="${esc(p)}">${esc(p)}</option>`).join('');

  ['fRun','fSet','fPrimary','fSort'].forEach(id=>$('#'+id).addEventListener('change', e=>{
    state[({fRun:'run',fSet:'set',fPrimary:'primary',fSort:'sort'})[id]] = e.target.value; render();
  }));
  $('#q').addEventListener('input', e=>{ state.q = e.target.value.trim(); render(); });
  $('#btnExpand').addEventListener('click', ()=>{ state.expanded = !state.expanded; $('#btnExpand').textContent = state.expanded?'收起未跑':'展开未跑'; render(); });

  // ---------- table render ----------
  function badge(r){
    if(r.unrun) return `<span class="badge idle"><i></i>未跑</span>`;
    if(r.status==='pass') return `<span class="badge pass"><i></i>PASS</span>`;
    if(r.status==='other') return `<span class="badge other"><i></i>ERROR</span>`;
    return `<span class="badge fail"><i></i>FAIL</span>`;
  }
  function taskCell(r, showModel){
    const id = r.task_id || r.id;
    const title = r.title || id;
    const setTag = r.set==='core' ? `<span class="tag core">CORE</span>` : r.set ? `<span class="tag ext">EXT</span>` : '';
    const tech = (r.tech||[]).slice(0,2).map(t=>`<span class="tag">${esc(t.replace(/^code2/,''))}</span>`).join('');
    return `<div class="tname"><div class="ttl">${esc(title)}${r.rescored?'<span class="rv">↻ v0.6 重评分</span>':''}</div>
      <div class="meta"><span class="mono">${esc(id)}</span>${setTag}${r.primary?`<span>${esc(r.primary)}</span>`:''}${tech}</div>
      ${showModel && r.model?`<div class="imodel on">${esc(r.model)}${r.harness?' · '+esc(r.harness):''}</div>`:''}</div>`;
  }
  function scoreCell(r){
    if(r.unrun) return `<span style="color:var(--muted)">—</span>`;
    const v = r.final_score;
    const cls = r.status==='pass'?'pass':'fail';
    return `<div class="score"><div class="top"><span class="n">${v==null?'—':num(v,3)}</span></div>
      <div class="frv">F ${num(r.F,2)} · R ${num(r.R,2)}</div>
      <div class="track ${cls}"><i style="width:${Math.max(1.5,(v||0)*100)}%"></i></div></div>`;
  }
  function assertCell(r){
    if(r.unrun) return `<span style="color:var(--muted)">—</span>`;
    const g = (lab,pass,fail,skip)=>`<span class="grp"><span class="lab">${lab}</span><span class="ok">${pass}</span><span class="sep">·</span><span class="no">${fail}</span>${skip!=null?`<span class="sep">·</span><span class="sk">${skip}</span>`:''}</span>`;
    return `<span class="asserts" title="L0 通过·失败·跳过 / L1 通过·失败">${g('L0',r.l0_pass,r.l0_fail,r.l0_skip)}${g('L1',r.l1_pass,r.l1_fail,null)}</span>`;
  }
  function artCell(r){
    if(r.unrun) return `<span style="color:var(--muted);font-size:11px">无</span>`;
    const a = ART[r.artifact]||{};
    return `<button class="btn-res" data-act="preview" data-task="${esc(r.task_id)}" data-run="${esc(r.run_id)}" ${a.embedded?'':'disabled title="产物未嵌入"'}>预览 ↗</button>`;
  }

  const COLS = [
    {k:'status', label:'结果',  w:88,  minW:0,   cell:r=>badge(r)},
    {k:'task',   label:'题目',  w:null,minW:0,   cell:(r,m)=>taskCell(r,m)},
    {k:'model',  label:'模型 / harness', w:266, minW:1040,
      cell:r=>`<div class="mcell">${r.unrun
        ? '<span class="m2">暂无运行记录</span>'
        : `<span class="m1">${esc(r.model||'—')}</span><span class="m2">${esc(r.harness||'—')}${r.split?' · '+esc(r.split):''}${r.harness_version?' · v'+esc(r.harness_version):''}</span>`}</div>`},
    {k:'score',  label:'得分',  w:152, minW:0,   cell:r=>scoreCell(r)},
    {k:'assert', label:'L0 · L1', w:146, minW:780, cell:r=>assertCell(r)},
    {k:'tok',    label:'tokens', w:82, minW:1220, right:true,
      cell:r=>`<span class="mono" style="font-size:11.5px;color:${r.unrun?'var(--muted)':'var(--ink-2)'}">${r.unrun?'—':(r.tokens_out||0).toLocaleString()}</span>`},
    {k:'art',    label:'产物',  w:88,  minW:0,   cell:r=>artCell(r)}
  ];
  function visibleCols(){ const w = window.innerWidth; return COLS.filter(c=>w >= c.minW); }

  function render(){
    const cols = visibleCols();
    const showModel = !cols.some(c=>c.k==='model');
    $('#thead').innerHTML = '<tr>' + cols.map(c=>
      `<th class="c-${c.k}" style="width:${c.w?c.w+'px':'auto'}${c.right?';text-align:right;padding-right:16px':''}">${c.label}</th>`
    ).join('') + '</tr>';

    const list = filtered();
    const body = $('#tbody');
    const cells = r => cols.map(c=>
      `<td class="c-${c.k}${c.right?' mono':''}"${c.right?' style="text-align:right;padding-right:16px"':''}>${c.cell(r, showModel)}</td>`
    ).join('');

    const html = list.map(r=>`
      <tr class="row ${state.open && state.open.task_id===r.task_id && state.open.run_id===r.run_id ? 'open':''}" data-task="${esc(r.task_id)}" data-run="${esc(r.run_id)}">
        ${cells(r)}
      </tr>`).join('');

    const ul = filteredUnran();
    let group = '';
    if(state.expanded && ul.length){
      group = `<tr class="grouprow"><td colspan="${cols.length}" style="padding:0"><button class="groupbtn" disabled>未跑题目 · 共 ${ul.length} 题（点击行查看题目定义）</button></td></tr>` +
        ul.map(t=>`<tr class="row" data-task="${esc(t.task_id)}" data-run="">${cells(t)}</tr>`).join('');
    } else if(ul.length){
      group = `<tr class="grouprow"><td colspan="${cols.length}" style="padding:0"><button class="groupbtn" id="grpUnran">
        未跑题目 <span class="g">${ul.length}</span> <span style="color:var(--muted);font-size:11.5px">点此展开（当前筛选条件下）</span></button></td></tr>`;
    }

    body.innerHTML = html + group;
    $('#empty').style.display = list.length? 'none':'block';
    const gb = document.getElementById('grpUnran');
    if(gb) gb.addEventListener('click', ()=>{ state.expanded=true; document.querySelector('#btnExpand').textContent='收起未跑'; render(); });
    body.querySelectorAll('tr.row').forEach(tr=>{
      tr.addEventListener('click', e=>{
        if(e.target.closest('[data-act="preview"]')){
          const t = e.target.closest('[data-act]');
          openDetail(t.dataset.task, t.dataset.run, 'preview');
        } else {
          openDetail(tr.dataset.task, tr.dataset.run, 'overview');
        }
      });
    });
  }

  // ---------- detail ----------
  const TABS = [['overview','概览'],['preview','产物预览'],['assert','断言与评分'],['judge','Judge / 交付自述'],['trace','Trace'],['prompt','题目原文']];
  $('#tabs').innerHTML = TABS.map(([k,l])=>`<button data-tab="${k}" aria-selected="false">${l}</button>`).join('');
  $('#tabs').addEventListener('click', e=>{ const b=e.target.closest('button'); if(b){ state.tab=b.dataset.tab; paintDetail(); }});
  $('#btnClose').addEventListener('click', closeDetail);
  $('#scrim').addEventListener('click', closeDetail);
  document.addEventListener('keydown', e=>{
    if(e.key==='Escape') closeDetail();
    if(e.key==='/' && document.activeElement!==$('#q')){ e.preventDefault(); $('#q').focus(); }
  });

  function openDetail(taskId, runId, tab){
    state.open = {task_id:taskId, run_id:runId||''};
    state.tab = tab || 'overview';
    $('#sheet').classList.add('on'); $('#scrim').classList.add('on');
    render(); paintDetail();
  }
  function closeDetail(){
    state.open=null; state.device='fit';
    $('#sheet').classList.remove('on'); $('#scrim').classList.remove('on');
    render();
  }

  function currentRow(){
    if(!state.open) return null;
    const t = Object.assign({task_id:state.open.task_id}, TASKS[state.open.task_id]||{});
    const r = RESULTS.find(x=>x.task_id===state.open.task_id && (state.open.run_id? x.run_id===state.open.run_id : true));
    return r ? Object.assign({}, t, r) : Object.assign({unrun:true}, t);
  }

  function paintDetail(){
    const r = currentRow(); if(!r) return;
    const T = TASKS[state.open.task_id] || {};
    $('#sId').innerHTML = `<span>${esc(r.task_id)}</span>` +
      (r.set==='core'?'<span class="tag core">CORE-111</span>':r.set?'<span class="tag ext">EXTENDED</span>':'') +
      (r.unrun?'<span class="badge idle"><i></i>未跑</span>':r.status==='pass'?'<span class="badge pass"><i></i>PASS</span>':'<span class="badge fail"><i></i>FAIL</span>') +
      (r.run_id?`<span style="color:var(--muted)">· ${esc(r.run_id)}</span>`:'');
    $('#sTitle').textContent = r.title || r.task_id;
    [...$('#tabs').children].forEach(b=>b.setAttribute('aria-selected', b.dataset.tab===state.tab));

    const body = $('#sBody');
    if(state.tab==='overview') body.innerHTML = paneOverview(r, T);
    if(state.tab==='preview') body.innerHTML = panePreview(r);
    if(state.tab==='assert') body.innerHTML = paneAssert(r, T);
    if(state.tab==='judge') body.innerHTML = paneJudge(r);
    if(state.tab==='trace') body.innerHTML = paneTrace(r);
    if(state.tab==='prompt') body.innerHTML = panePrompt(r, T);

    if(state.tab==='preview') wirePreview(r);
  }

  function paneOverview(r, T){
    if(r.unrun){
      return `<div class="card" style="margin-bottom:14px">
        <h3>题目定义<span class="rule"></span></h3>
        <div class="kv">
          <dt>层级</dt><dd>${esc(T.set_label||'—')}</dd>
          <dt>主类</dt><dd>${esc(T.primary||'—')}</dd>
          <dt>技术标签</dt><dd>${(T.tech||[]).map(t=>esc(t)).join(' · ')||'—'}</dd>
          <dt>赛道</dt><dd>${(T.tracks||[]).map(t=>esc(t)).join(' · ')||'—'}</dd>
          <dt>参考产物</dt><dd>${T.has_reference_oracle?'runnable-html · oracle 可用':(T.reference_kind==='post-only'?'无（post-only）':'—')}</dd>
          <dt>断言数</dt><dd>${T.assertion_target||(T.assertions||[]).length||'—'}</dd>
          <dt>Prompt</dt><dd>${T.prompt_chars||0} chars</dd>
        </div></div>
      <div class="card"><h3>本题尚无运行记录<span class="rule"></span></h3>
        <p style="margin:0 0 8px;color:var(--ink-2);font-size:12.5px">跑一次即可在看板出现：</p>
        <pre class="code">python3 scripts/run_evaluation.py --models config/models.harness.example.json --task ${esc(r.task_id)} --limit 1</pre>
        <div style="margin-top:10px;font-size:12px;color:var(--muted)">跑完后执行 <code style="font-family:var(--mono)">python3 scripts/build_results_dashboard.py</code> 重新生成本看板。</div>
      </div>`;
    }
    const a = ART[r.artifact]||{};
    const mc = [['final_score',num(r.final_score,4)],['F 功能',num(r.F)],['R 约束',num(r.R)],['V 视觉',num(r.V)]];
    return `<div class="grid2">
      <div>
        <div class="card" style="margin-bottom:14px">
          <h3>运行结论<span class="rule"></span></h3>
          <div class="metric">${mc.map(([k,v])=>`<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}</div>
          <div class="barline"><span style="font-size:11px;color:var(--muted);width:64px">final</span><span class="b ${r.status==='pass'?'p':'f'}"><i style="width:${Math.max(1.5,(r.final_score||0)*100)}%"></i></span><span class="mono" style="font-size:11.5px">${num(r.final_score,3)}</span></div>
          ${r.quality_given_pass==null?'':`<div class="barline"><span style="font-size:11px;color:var(--muted);width:64px">quality</span><span class="b"><i style="width:${Math.max(1.5,r.quality_given_pass*100)}%"></i></span><span class="mono" style="font-size:11.5px">${num(r.quality_given_pass,3)}</span></div>`}
          ${r.notes?`<div style="margin-top:10px"><span class="pill">note</span> <span style="font-size:12px;color:var(--ink-2)">${esc(r.notes)}</span></div>`:''}
          ${r.rescored?`<div style="margin-top:10px;padding:9px 11px;background:var(--panel-2);border:1px solid var(--line);border-radius:7px;font-size:11.5px;line-height:1.6;color:var(--ink-2)"><span class="pill">v0.6 重评分</span> 原始 <b>${r.old_pass==='True'?'PASS':'FAIL'} / ${esc(r.old_score)}</b> → 当前 <b>${r.status==='pass'?'PASS':'FAIL'} / ${num(r.final_score,4)}</b><br><span style="color:var(--muted)">同一份产物按修订口径重算，原始 <code style="font-family:var(--mono)">outcomes.csv</code> 保留未改。依据 <code style="font-family:var(--mono)">docs/assertion-review.md</code>、<code style="font-family:var(--mono)">docs/rescore-report.md</code>。</span></div>`:''}
          ${r.error?`<div style="margin-top:8px"><span class="pill f">error</span> <span style="font-size:12px;color:var(--fail)">${esc(r.error)}</span></div>`:''}
        </div>
        <div class="card">
          <h3>被测系统<span class="rule"></span></h3>
          <div class="kv">
            <dt>model</dt><dd>${esc(r.model)}</dd>
            <dt>harness</dt><dd>${esc(r.harness)}</dd>
            <dt>impl / ver</dt><dd>${esc(r.harness_impl||'—')}${r.harness_version?' / '+esc(r.harness_version):''}</dd>
            <dt>protocol</dt><dd>${esc(r.protocol||'—')}</dd>
            <dt>sampling</dt><dd style="font-size:11.5px">${esc(sampling(r.params||{}))}</dd>
            <dt>split</dt><dd>${esc(r.split||'—')} · rep ${r.repetition}</dd>
            <dt>judge</dt><dd>${esc(r.judge_model||'—')}</dd>
            <dt>tokens</dt><dd>${(r.tokens_out||0).toLocaleString()} out</dd>
            <dt>产物</dt><dd>${esc(a.path||'—')} · ${bytes(a.bytes||0)}</dd>
          </div>
        </div>
      </div>
      <div>
        <div class="card" style="margin-bottom:14px">
          <h3>题目<span class="rule"></span></h3>
          <div class="kv">
            <dt>层级</dt><dd>${esc(T.set_label||'—')}</dd>
            <dt>主类</dt><dd>${esc(T.primary||'—')}</dd>
            <dt>技术标签</dt><dd>${(T.tech||[]).map(t=>esc(t)).join(' · ')||'—'}</dd>
            <dt>参考产物</dt><dd>${T.reference_url?`<a href="${esc(T.reference_url)}" target="_blank" rel="noopener">打开第三方 reference ↗</a>`:(T.reference_kind==='post-only'?'无（post-only，仅逐字 Prompt）':esc(T.reference_kind||'无'))}</dd>
            <dt>Prompt</dt><dd>${T.prompt_chars||0} chars</dd>
          </div>
          <div style="margin-top:10px;font-size:12.5px;color:var(--ink-2);line-height:1.65">${esc(T.prompt_excerpt||'')}</div>
        </div>
        <div class="card">
          <h3>复现命令<span class="rule"></span></h3>
          <pre class="code">python3 scripts/run_evaluation.py \\
  --models config/models.harness.example.json \\
  --task ${esc(r.task_id)} --limit 1</pre>
          <div style="margin-top:9px;font-size:11.5px;color:var(--muted)">artifact 命名：<span class="mono">${esc(r.config_id)}__${esc(r.task_id)}__r${r.repetition}.html</span></div>
        </div>
      </div>
    </div>`;
  }

  function panePreview(r){
    if(r.unrun) return `<div class="no-pv">本题尚未运行，没有可预览的产物。</div>`;
    const a = ART[r.artifact]||{};
    if(!a.embedded){
      return `<div class="no-pv">产物未嵌入：${esc(a.reason||'未找到文件')}<br><br>
        <span class="mono" style="font-size:11.5px">${esc(a.path||'')}</span><br><br>
        本地打开：<span class="mono" style="font-size:11.5px">${esc(r.artifact_path||'')}</span></div>`;
    }
    return `<div class="pv-bar">
        <div class="segs" id="devSegs">
          ${[['fit','自适应'],['1440','1440'],['768','768'],['390','390']].map(([k,l])=>`<button data-dev="${k}" aria-pressed="${state.device===k}">${l}</button>`).join('')}
        </div>
        <button class="ghost" id="btnReload">↻ 重载</button>
        <button class="ghost" id="btnNew">在新窗口打开</button>
        <button class="ghost" id="btnFull">全屏预览</button>
        <div class="spacer"></div>
        <span class="chip"><span class="k">size</span><b>${bytes(a.bytes)}</b></span>
        <span class="chip"><span class="k">file</span><b>${esc(r.artifact)}</b></span>
      </div>
      <div class="pv-wrap" id="pvWrap"><iframe id="pvFrame" sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-pointer-lock" title="artifact preview"></iframe></div>
      <div style="margin-top:10px;font-size:11.5px;color:var(--muted)">
        产物在沙箱 iframe 中运行（脚本可执行，禁止顶层跳转）。若页面依赖 CDN，离线环境会自动降级；这正是 L0-01 断言要拦的情况。
      </div>`;
  }

  function wirePreview(r){
    const a = ART[r.artifact]||{}; if(!a.embedded) return;
    const frame = $('#pvFrame'), wrap = $('#pvWrap');
    const apply = ()=>{
      frame.srcdoc = a.html;
      const d = state.device;
      if(d==='fit'){ frame.style.width='100%'; wrap.classList.remove('dev'); }
      else { frame.style.width = Math.min(parseInt(d,10), wrap.clientWidth-20)+'px'; wrap.classList.add('dev'); }
    };
    apply();
    $('#devSegs').addEventListener('click', e=>{
      const b = e.target.closest('button'); if(!b) return;
      state.device = b.dataset.dev;
      [...$('#devSegs').children].forEach(x=>x.setAttribute('aria-pressed', x.dataset.dev===state.device));
      apply();
    });
    $('#btnReload').addEventListener('click', apply);
    $('#btnNew').addEventListener('click', ()=>{
      const blob = new Blob([a.html], {type:'text/html'});
      window.open(URL.createObjectURL(blob), '_blank');
    });
    $('#btnFull').addEventListener('click', ()=>{
      const f = frame;
      if(f.requestFullscreen) f.requestFullscreen();
    });
  }

  function paneAssert(r, T){
    if(r.unrun) return `<div class="no-pv">尚未运行。</div>`;
    const l0t = r.l0_pass+r.l0_fail+ (r.l0_skip||0), l1t = r.l1_pass+r.l1_fail;
    const unit = (p,f,s,label)=>`<div class="card"><h3>${label}<span class="rule"></span></h3>
      <div class="metric" style="grid-template-columns:repeat(3,1fr)">
        <div><div class="k">pass</div><div class="v" style="color:var(--pass)">${p}</div></div>
        <div><div class="k">fail</div><div class="v" style="color:var(--fail)">${f}</div></div>
        <div><div class="k">${label==='L0 全局合约'?'skip':'total'}</div><div class="v" style="color:var(--muted)">${s}</div></div>
      </div></div>`;
    const rows = (T.assertions||[]).map(a=>`<tr>
      <td class="mono" style="font-size:11px;color:var(--muted)">${esc(a.id)}</td>
      <td style="font-size:12.5px">${esc(a.name)}</td>
      <td><span class="pill">${esc(a.dimension)}</span></td>
      <td class="mono" style="font-size:11px;color:var(--muted)">${esc(a.kind)}</td>
      <td class="mono" style="font-size:10.5px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(a.pattern)}</td>
    </tr>`).join('');
    return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
        ${unit(r.l0_pass,r.l0_fail,r.l0_skip,'L0 全局合约')}
        ${unit(r.l1_pass,r.l1_fail,l1t,'L1 任务断言')}
      </div>
      <div class="card" style="margin-bottom:14px">
        <h3>评分构成<span class="rule"></span></h3>
        <div class="kv" style="grid-template-columns:auto 1fr auto 1fr">
          <dt>final_score</dt><dd>${num(r.final_score,4)}</dd>
          <dt>quality_given_pass</dt><dd>${num(r.quality_given_pass,4)}</dd>
          <dt>F</dt><dd>${num(r.F,4)}</dd>
          <dt>R</dt><dd>${num(r.R,4)}</dd>
          <dt>V</dt><dd>${num(r.V,4)}</dd>
          <dt>E</dt><dd>${num(r.E,4)}</dd>
          <dt>claimed_checks</dt><dd>${r.claimed_checks}</dd>
          <dt>trace_verified</dt><dd>${r.trace_verified_checks||'—'}</dd>
          <dt>unverified_claims</dt><dd>${r.unverified_claims}</dd>
          <dt>self_assessed</dt><dd>${num(r.self_assessed_completion,2)}</dd>
        </div>
      </div>
      <div class="card">
        <h3>断言清单 · ${(T.assertions||[]).length} 条<span class="rule"></span></h3>
        <div style="font-size:11.5px;color:var(--muted);margin-bottom:8px">本次运行只落盘了 L0/L1 聚合计数，逐条判定由前端列出断言定义，便于对照失败计数定位。</div>
        <table style="table-layout:auto"><thead><tr><th>ID</th><th>断言</th><th>维度</th><th>类型</th><th>pattern / selector</th></tr></thead><tbody>${rows||'<tr><td colspan="5" style="color:var(--muted)">该题未生成断言包</td></tr>'}</tbody></table>
      </div>`;
  }

  function paneJudge(r){
    if(r.unrun) return `<div class="no-pv">尚未运行。</div>`;
    const js = r.judge||[];
    const d = r.delivery||{};
    const jhtml = js.length ? js.map(j=>`<div class="jitem">
        <span class="pill ${j.verdict==='PASS'?'p':'f'}">${esc(j.verdict)}</span>
        <div style="min-width:0"><div><span class="mono" style="font-size:11px;color:var(--muted)">${esc(j.assertion_id)}</span> · <b style="font-weight:600">${esc(j.assertion_name)}</b></div>
        <div class="jr">${esc(j.reason)}</div>
        <div class="jt" style="margin-top:3px">${esc(j.judge_model)} · ${j.judge_tokens} tok</div></div>
      </div>`).join('') : `<div style="color:var(--muted);font-size:12.5px">该批次无 judge 记录（或该题未触发 L2 多模态判定）。</div>`;

    const claims = (d.claimed_checks||[]);
    const weak = (d.weak_points||[]);
    return `<div class="grid2">
      <div class="card"><h3>Judge 判定 · ${js.length} 条<span class="rule"></span></h3>${jhtml}</div>
      <div>
        <div class="card" style="margin-bottom:14px"><h3>模型交付自述<span class="rule"></span></h3>
          <div class="kv" style="margin-bottom:8px"><dt>自评完成度</dt><dd>${num(d.self_assessed_completion,2)}</dd>
          <dt>声明检查项</dt><dd>${claims.length}</dd></div>
          ${claims.length?`<ul class="clean">${claims.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>`:'<div style="color:var(--muted);font-size:12.5px">无</div>'}
        </div>
        <div class="card"><h3>自陈弱点<span class="rule"></span></h3>
          ${weak.length?`<ul class="clean">${weak.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>`:'<div style="color:var(--muted);font-size:12.5px">无</div>'}
        </div>
      </div>
    </div>`;
  }

  function paneTrace(r){
    if(r.unrun) return `<div class="no-pv">尚未运行。</div>`;
    const ev = r.trace||[];
    if(!ev.length) return `<div class="no-pv">该题没有 trace 记录。</div>`;
    return `<div class="card"><h3>执行轨迹 · ${ev.length} 步<span class="rule"></span></h3>
      <div class="trace">${ev.map(e=>`<div class="trow">
        <div class="s">${esc(e.step)}</div><div class="a">${esc(e.action)}</div>
        <div class="o"><span style="color:var(--muted)">${esc(e.target)}</span> — ${esc(e.observation)}</div></div>`).join('')}</div></div>`;
  }

  function panePrompt(r, T){
    const p = T.prompt || '';
    if(!p){
      return `<div class="card"><h3>题目摘要<span class="rule"></span></h3>
        <div style="font-size:12.5px;color:var(--muted);margin-bottom:10px">本题未运行，看板只内联摘要（控制体积）。完整逐字原文见 <span class="mono">tasks/${esc(r.task_id)}/prompt.md</span>，或
        <a href="../catalog/" target="_blank" rel="noopener">题库目录页 ↗</a>。</div>
        <div class="promptbox">${esc(T.prompt_excerpt||'—')}</div></div>`;
    }
    return `<div class="card" style="margin-bottom:12px"><h3>Prompt · ${p.length} chars<span class="rule"></span></h3>
      <div style="font-size:12.5px;color:var(--muted);margin-bottom:10px">逐字原文，未经改写。${T.creator?'作者：'+esc(T.creator):''}</div>
      <div class="promptbox">${esc(p)}</div></div>`;
  }

  // ---------- boot ----------
  function syncSticky(){
    const h = document.querySelector('header').offsetHeight;
    document.documentElement.style.setProperty('--sticky', (h+1)+'px');
  }
  if(DB.rescored_count){
    const el = $('#rnotice'); el.style.display='block';
    el.innerHTML = `<b>↻ v0.6 重评分生效</b> — ${DB.rescored_count} 条记录已按修订后的评分口径对<strong>同一份已提交产物</strong>重新计算：Gate 只由运行时交互探针触发，静态断言失败改由 F/R/E 扣分，截断归因为交付物不完整。原始 <code>results/*/outcomes.csv</code> 保留未改，逐题新旧对比见 <code>docs/rescore-report.md</code>。`;
  }
  syncSticky(); window.addEventListener('resize', syncSticky);
  let rzTimer = null;
  window.addEventListener('resize', ()=>{ clearTimeout(rzTimer); rzTimer = setTimeout(()=>{ if(!state.open) render(); }, 120); });
  $('#foot').innerHTML = `<span>数据源 <code>results/*/outcomes.csv</code> · <code>rescored.csv</code> · <code>judge.csv</code> · <code>traces/</code> · <code>tasks/*</code></span>
    <span>生成于 ${esc(DB.generated_at)}</span>
    <span>重新生成 <code>python3 scripts/build_results_dashboard.py</code></span>
    <span>${esc(DB.repo)}</span>`;
  render();
  if(location.hash.startsWith('#task=')){
    const id = location.hash.slice(6);
    if(TASKS[id]) openDetail(id, '', 'overview');
  }
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
