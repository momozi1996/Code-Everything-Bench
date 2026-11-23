#!/usr/bin/env python3
"""L2 visual judge: closed questions over a delivered artifact.

The judge is a *fixed* configuration (role="judge" in config/models.json). It
never builds the artifact; it only answers the task's closed visual questions so
the V dimension is filled with evidence instead of being silently zero.

    python3 scripts/judge_run.py --run 2026-11-23-smoke-glm53flash
    python3 scripts/judge_run.py --run <id> --model-config judge-deepseek-v41-flash

Outputs `results/<run-id>/judge.csv` and updates nothing else. A judge that
cannot reach a verdict records `SKIP`, never a fabricated PASS.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cebench.providers import (MissingCredentialError, build_client,  # noqa: E402
                               load_model_configs)

JUDGE_SYSTEM = (
    "You are a strict, evidence-bound evaluator for a front-end artifact benchmark. "
    "You must judge ONLY from the artifact source provided. You must not assume "
    "anything that the source does not show. If the evidence is insufficient, "
    'answer FAIL with reason "insufficient evidence". '
    'Reply with a single JSON object: {"verdict": "PASS" or "FAIL", "reason": "<20 words max>"}'
)

MAX_SRC = 16000


def digest(source: str) -> str:
    """Keep structure, drop payload bulk: long base64/data URIs and huge literals."""
    s = re.sub(r"(data:[a-z]+/[a-z0-9.+-]+;base64,)[A-Za-z0-9+/=\s]{200,}", r"\1<len>", source)
    s = re.sub(r"\s{4,}", "\n", s)
    if len(s) <= MAX_SRC:
        return s
    head, tail = s[: MAX_SRC - 2000], s[-1800:]
    return head + "\n/* … truncated … */\n" + tail


def parse_verdict(text: str) -> tuple[str, str]:
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            v = str(d.get("verdict", "")).upper()
            if v in ("PASS", "FAIL"):
                return v, str(d.get("reason", ""))[:200]
        except Exception:
            pass
    up = text.upper()
    if '"PASS"' in up or up.strip().startswith("PASS"):
        return "PASS", text.strip()[:120]
    if '"FAIL"' in up or up.strip().startswith("FAIL"):
        return "FAIL", text.strip()[:120]
    return "SKIP", f"unparseable judge output: {text.strip()[:100]}"


def find_task_artifact(name: str) -> str:
    # cfg__<task_id>__r<rep>.html
    parts = name[:-5].split("__")
    return parts[1] if len(parts) >= 3 else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--models", default=str(ROOT / "config" / "models.json"))
    ap.add_argument("--model-config", default=None, help="judge config id")
    args = ap.parse_args()

    run_dir = ROOT / "results" / args.run
    art_dir = run_dir / "artifacts"
    if not art_dir.is_dir():
        print(f"no artifacts at {art_dir}", file=sys.stderr)
        return 2

    configs = load_model_configs(args.models)
    judges = [c for c in configs if getattr(c, "role", "target") == "judge"]
    if args.model_config:
        judges = [c for c in judges if c.id == args.model_config] or judges
    if not judges:
        print("no role=judge configuration in %s" % args.models, file=sys.stderr)
        return 2
    jcfg = judges[0]
    try:
        client = build_client(jcfg, dry_run=False)
    except MissingCredentialError as exc:
        print(f"judge credential missing: {exc}", file=sys.stderr)
        return 3

    rows: list[dict[str, Any]] = []
    for art in sorted(art_dir.glob("*.html")):
        tid = find_task_artifact(art.name)
        tdir = ROOT / "tasks" / tid
        if not tdir.is_dir():
            print(f"skip {art.name}: no task pack for {tid!r}")
            continue
        prompt = (tdir / "prompt.md").read_text(encoding="utf-8")
        specs = json.loads((tdir / "assertions" / "task.json").read_text(encoding="utf-8"))
        visual = [a for a in specs.get("assertions", []) if a.get("kind") == "visual_review"]
        if not visual:
            continue
        source = art.read_text(encoding="utf-8", errors="ignore")
        for spec in visual:
            question = spec.get("rubric") or spec.get("name") or "visual fidelity"
            user = (
                f"TASK REQUIREMENT (verbatim, may be Chinese):\n{prompt[:2500]}\n\n"
                f"CLOSED QUESTION:\n{spec.get('name')}: {question}\n\n"
                f"ARTIFACT SOURCE:\n{digest(source)}\n\n"
                "Does the artifact satisfy the closed question? Answer with JSON only."
            )
            try:
                resp = client.chat([
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": user},
                ])
                verdict, reason = parse_verdict(resp.content)
                usage = resp.usage
            except Exception as exc:
                verdict, reason, usage = "SKIP", f"judge_error: {type(exc).__name__}: {exc}"[:200], {}
            rows.append({
                "run_id": args.run, "artifact": art.name, "task_id": tid,
                "assertion_id": spec.get("id"), "assertion_name": spec.get("name"),
                "judge_model": jcfg.model, "verdict": verdict, "reason": reason,
                "judge_tokens": (usage or {}).get("completion_tokens", ""),
            })
            print(f"  [{verdict:4s}] {tid} {spec.get('id')} {spec.get('name')} :: {reason[:70]}")

    out = run_dir / "judge.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else
                           ["run_id", "artifact", "task_id", "assertion_id",
                            "assertion_name", "judge_model", "verdict", "reason", "judge_tokens"])
        w.writeheader()
        w.writerows(rows)
    passed = sum(1 for r in rows if r["verdict"] == "PASS")
    print(f"\nwrote {out} ({len(rows)} verdicts, {passed} PASS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
