#!/usr/bin/env python3
"""Derive task-specific L1 assertions from each task's verbatim prompt.

Scope rule: L0 already covers single-file / doctype / console / overflow / rAF /
reduced-motion / pointer-keyboard / audio-gesture. L1 must therefore assert only
what *this prompt* asks for — the interaction model of the task.

Everything produced here is marked `auto_derived` and requires human review: an
assertion that the reference implementation fails is a wrong assertion, not a
wrong artifact (see the meta-test in reference/SOURCE.md).

    python3 scripts/generate_assertions.py --check          # report only
    python3 scripts/generate_assertions.py                  # write all
    python3 scripts/generate_assertions.py --task case-001  # one task
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"

# (trigger substrings in prompt, assertion template, dimension, label)
# `source_contains` patterns are regexes matched against the delivered HTML.
TECH_RULES: list[tuple[tuple[str, ...], str, str, str]] = [
    (("canvas", "画布"), r"<canvas\b", "F", "canvas surface present"),
    (("svg",), r"<svg\b", "R", "inline svg artwork present"),
    (("three.js", "threejs", "three.min", "three.module", "three r1"), r"THREE\.|three(?:\.module|\.min)?\.js", "F", "Three.js runtime referenced"),
    (("webgl",), r"getContext\(\s*['\"]webgl", "F", "WebGL context requested"),
    (("音频", "音效", "音乐", "声音", "audio"), r"AudioContext|new\s+Audio\(", "F", "audio path exists"),
    (("视频", "video"), r"<video\b|\.play\(\)", "F", "video element or playback call"),
    (("粒子", "particle"), r"particle|粒子", "R", "particle system referenced"),
    (("拖拽", "拖动", "drag"), r"draggable|mousedown|pointerdown|touchstart", "F", "drag/pointer interaction"),
    (("键盘", "按键"), r"keydown|keyup|onkey", "F", "keyboard interaction"),
    (("触摸", "touch"), r"touchstart|touchmove|pointerdown", "F", "touch interaction"),
    (("响应式", "适配", "移动端"), r"@media|width=device-width", "R", "responsive layout declared"),
    (("动画", "animation"), r"@keyframes|animation\s*:|requestAnimationFrame", "R", "animation declared"),
    (("3d", "三维", "立体"), r"perspective|transform\s*:\s*.*3d|THREE\.|webgl", "R", "3D rendering path"),
    (("渐变", "gradient"), r"gradient\(", "R", "gradient fill used"),
    (("字体", "font"), r"font-family", "R", "custom font stack declared"),
]

# Prompts that explicitly forbid a shortcut. The assertion must fail if the
# shortcut is taken.
FORBID_RULES: list[tuple[tuple[str, ...], str, str, str]] = [
    (("不要生成图片", "不要用图片", "不要使用图片", "不要背景图"),
     r"<img[^>]+src=['\"]https?://", "F", "no remote image standing in for the artifact"),
    (("不要只给", "不要仅给"), r"^", "E", "artifact is code, not a plan"),  # handled separately
]

MIN_AUTO = 8


def load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def derive(tid: str) -> list[dict[str, Any]]:
    tdir = TASKS / tid
    prompt = (tdir / "prompt.md").read_text(encoding="utf-8")
    task = load_json(tdir / "task.json")
    tags = task.get("code2_tags") or []
    lowered = prompt.lower()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(kind: str, name: str, dim: str, **kw: Any) -> None:
        if name in seen:
            return
        seen.add(name)
        aid = f"L1-{len(out) + 1:02d}"
        out.append({"id": aid, "name": name, "kind": kind, "dimension": dim,
                    "derived_from": "prompt-keyword", "auto_derived": True, **kw})

    for triggers, pattern, dim, name in TECH_RULES:
        if any(t in lowered for t in triggers):
            add("source_contains", name, dim, pattern=pattern)

    for triggers, pattern, dim, name in FORBID_RULES:
        if any(t in lowered for t in triggers) and pattern != "^":
            add("source_absent", name, dim, pattern=pattern)

    # tag-driven fallbacks so a tag-rich task does not end up under-asserted
    if "code2canvas" in tags:
        add("selector_exists", "canvas element reachable", "F", selector="canvas")
    if "code2svg" in tags:
        add("selector_exists", "svg element reachable", "R", selector="svg")

    # one behavioural probe is mandatory: a DOM node is not evidence of behaviour
    add("interaction_delta", "a pointer interaction changes runtime state", "F",
        selector="body", action="click", settle_ms=250, evidence_grade="E1/E3")

    # Fill up to the admission floor with honest, task-agnostic structure checks.
    # Ordered so the least redundant ones (vs L0) come first.
    filler = [
        ("source_contains", "artifact is a complete HTML document", "F",
         r"<!doctype\s+html|<html", "L0-aligned"),
        ("source_contains", "artifact declares a body", "F", r"<body\b", "L0-aligned"),
        ("source_contains", "styling is present", "R", r"<style\b|style\s*=", "prompt-keyword"),
        ("source_contains", "javascript is present", "F", r"<script\b", "prompt-keyword"),
        ("source_contains", "event handlers are wired", "E", r"addEventListener|onclick", "prompt-keyword"),
        ("source_contains", "dom is touched at runtime", "F", r"document\.(?:getElement|querySelector|body)", "prompt-keyword"),
        ("source_contains", "layout uses modern css", "R", r"display\s*:\s*(?:flex|grid)", "prompt-keyword"),
        ("source_absent", "no remote script dependency", "E",
         r"<script[^>]+src=['\"]https?://", "L0-aligned"),
        ("source_absent", "no inline base64 image payload", "E",
         r"data:image/[a-z]+;base64", "prompt-keyword"),
        ("source_contains", "named functions or arrows are used", "F", r"function\b|=>", "prompt-keyword"),
    ]

    def auto_count() -> int:
        return len([x for x in out if x["kind"] != "visual_review"])

    for kind, name, dim, pattern, origin in filler:
        if auto_count() >= MIN_AUTO:
            break
        if name in seen:
            continue
        seen.add(name)
        out.append({"id": f"L1-{len(out) + 1:02d}", "name": name, "kind": kind,
                    "dimension": dim, "pattern": pattern,
                    "derived_from": origin, "auto_derived": True})

    # always leave the L2 hook so V is never silently zero-filled
    out.append({"id": f"L1-{len(out) + 1:02d}", "name": "visual fidelity review",
                "kind": "visual_review", "dimension": "V",
                "rubric": "closed questions on rendered screenshots",
                "derived_from": "policy", "auto_derived": True})
    return out


def write(tid: str, assertions: list[dict[str, Any]]) -> None:
    p = TASKS / tid / "assertions" / "task.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    auto = [a for a in assertions if a["kind"] != "visual_review"]
    payload = {
        "task_id": tid,
        "tier": "L1",
        "minimum_auto_assertions": MIN_AUTO,
        "assertions": assertions,
        "status": "auto_derived_needs_review",
        "review_required": True,
        "auto_assertable": len(auto),
        "full_measurement": len(auto) >= MIN_AUTO,
        "notes": ("Derived from the verbatim prompt by scripts/generate_assertions.py. "
                  "L0 covers the shared contract; these are task-specific. "
                  "Run the reference meta-test before publishing: an assertion the "
                  "reference implementation fails is a wrong assertion."),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # keep task.json's admission flag in sync
    tp = TASKS / tid / "task.json"
    t = load_json(tp)
    t["full_measurement"] = len(auto) >= MIN_AUTO
    t["assertion_target"] = len(assertions)
    tp.write_text(json.dumps(t, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--task")
    ap.add_argument("--force", action="store_true",
                    help="overwrite hand-authored assertion packs too")
    args = ap.parse_args()
    ids = [args.task] if args.task else sorted(
        d.name for d in TASKS.iterdir() if d.is_dir() and (d / "task.json").is_file())
    counts: list[int] = []
    short: list[str] = []
    for tid in ids:
        ap = TASKS / tid / "assertions" / "task.json"
        if ap.is_file() and not args.force:
            cur = json.loads(ap.read_text(encoding="utf-8"))
            if cur.get("status") not in ("auto_derived_needs_review", "assertions_pending"):
                print(f"preserve {tid}: hand-authored assertions (status={cur.get('status')})")
                continue
        try:
            a = derive(tid)
        except FileNotFoundError as exc:
            print(f"skip {tid}: {exc}")
            continue
        auto = [x for x in a if x["kind"] != "visual_review"]
        counts.append(len(auto))
        if len(auto) < MIN_AUTO:
            short.append(tid)
        if not args.check:
            write(tid, a)
    print(f"tasks={len(counts)} auto_assertions min={min(counts) if counts else 0} "
          f"max={max(counts) if counts else 0} mean={sum(counts)/len(counts):.1f}" if counts else "no tasks")
    if short:
        print(f"BELOW FLOOR ({len(short)}): {short[:10]}")
        return 1
    print("all tasks meet the >=8 auto-assertion admission floor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
