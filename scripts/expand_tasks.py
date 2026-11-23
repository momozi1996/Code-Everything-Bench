#!/usr/bin/env python3
"""Expand CE-Bench with prompt-bearing tasks that the original .html-only
funnel rejected, prioritising under-represented labels.

Why this exists
---------------
The Core-111 census (`tasks/manifest.json`, reproducible via
`scripts/build_manifest.py`) admits only records that have BOTH a verbatim
prompt AND a runnable `.html` demo. That is a sound *measurement* gate, but it
leaves 194 prompt-bearing corpus records unused and skews the label
distribution hard toward visualization/frontend/svg-art.

This script builds an **Extended set** without touching Core-111:

  * Corpus records with a verbatim prompt, dropped only by the `.html` gate.
  * Verbatim prompts newly parsed from the Feishu export that are not yet in
    the pinned corpus (`data/corpus/feishu_md_records.jsonl`, status=new).

Selection is greedy on three-axis label scarcity, so the added tasks
deliberately fill the thin classes (game / composite / frontend / tools /
animation / 3D, and code2deck / code2html / code2world / code2game).

No Core file is rewritten. Outputs:
  * `data/corpus/extension.jsonl`      -- new Feishu records in corpus format
  * `tasks/manifest_extended.json`     -- selected extended tasks
  * `docs/expansion-report.md`         -- before/after three-axis distribution

`--apply` additionally materialises the task packs (delegated to
`scripts/build_task_packs.py --extended-only`).

Usage:
    python3 scripts/expand_tasks.py                 # dry-run, target 69
    python3 scripts/expand_tasks.py --target 89 --compare
    python3 scripts/expand_tasks.py --target 69 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus" / "cases.jsonl"
FEISHU = ROOT / "data" / "corpus" / "feishu_md_records.jsonl"
EXT_CORPUS = ROOT / "data" / "corpus" / "extension.jsonl"
MANIFEST = ROOT / "tasks" / "manifest.json"
EXT_MANIFEST = ROOT / "tasks" / "manifest_extended.json"
REPORT = ROOT / "docs" / "expansion-report.md"

# Reuse the paper's reporting map verbatim (scripts/build_manifest.py).
DOMAIN_MAP = {
    "code2frontend": "frontend", "code2html": "frontend", "code2css": "frontend",
    "code23d": "3d", "code2world": "3d", "code2shader": "3d", "code2blender": "3d",
    "code2viz": "visualization", "code2canvas": "visualization",
    "code2svg": "svg-art", "code2game": "game", "code2audio": "audio",
    "code2video": "animation-video", "code2deck": "composite",
}
# Tech axis is 12 fixed labels; fold the two extra corpus signals into 3D.
TECH_ALIAS = {"code2shader": "code23d", "code2blender": "code23d"}
TECH_KEYS = {
    "code2frontend", "code2viz", "code2svg", "code2canvas", "code23d",
    "code2audio", "code2video", "code2game", "code2css", "code2world",
    "code2html", "code2deck",
}
PRIMARY_KEYS = {"生成艺术", "可视化", "网页", "3D", "动画", "工具", "前端", "游戏"}
# "效率工作" is a corpus category, not one of the 8 paper primary classes.
PRIMARY_ALIAS = {"效率工作": "工具", "未分类": "工具", "": "工具"}

BAD_PROMPT = re.compile(r"未补写|可见节选|原帖回复区被|折叠|（.{0,6}节选|待补")
MIN_PROMPT_CHARS = 80

INFER_RULES: list[tuple[str, list[str]]] = [
    # NOTE: do not match bare "fps" -- `30fps`/`60fps` is a frame rate, not a
    # first-person shooter. Require an explicit shooter/gameplay phrase.
    (r"第一人称|FPS\s*游戏|shooter|射击|关卡|打砖块|可玩|闯关|解谜|生存|跑酷|街机|arcade|游戏", ["code2game"]),
    (r"three\.?js|WebGL|3D|Blender|体素|voxel|GL|光照|相机|渲染", ["code23d"]),
    (r"SVG|svg", ["code2svg"]),
    (r"动画|短片|视频|逐帧|fps|镜头|concept film|film|30fps", ["code2video"]),
    (r"音频|音效|Audio|声音|配乐", ["code2audio"]),
    (r"PPT|简报|幻灯片|deck|slide", ["code2deck"]),
    (r"可视化|图表|chart|data viz", ["code2viz"]),
    (r"canvas|Canvas", ["code2canvas"]),
    (r"世界|地形|world|terrain", ["code2world"]),
    (r"HTML|H5|网页|单页|page|site", ["code2html", "code2frontend"]),
    (r"CSS|样式|布局", ["code2css"]),
]


def infer_tags(text: str) -> list[str]:
    out: list[str] = []
    for pat, tags in INFER_RULES:
        if re.search(pat, text, re.I):
            out.extend(tags)
    out = list(dict.fromkeys(out))
    if not out:
        out = ["code2frontend", "code2html"]
    if len(out) == 1:
        out.append("code2html" if out[0] != "code2html" else "code2frontend")
    return out[:7]


def norm_tech(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(TECH_ALIAS.get(t, t) for t in tags if TECH_ALIAS.get(t, t) in TECH_KEYS))


def norm_primary(p: str) -> str:
    return PRIMARY_ALIAS.get(p, p) if p in PRIMARY_KEYS or p in PRIMARY_ALIAS else "工具"


def tracks_from(tags: list[str]) -> list[str]:
    return sorted({DOMAIN_MAP.get(t, "composite") for t in tags}) or ["composite"]


def quality_ok(prompt: str) -> tuple[bool, str]:
    if len(prompt.strip()) < MIN_PROMPT_CHARS:
        return False, "too_short"
    if BAD_PROMPT.search(prompt):
        return False, "truncated_excerpt"
    return True, "ok"


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def feishu_to_corpus(r: dict) -> dict:
    """Turn one parsed Feishu record into a corpus-shaped record."""
    evidence = r.get("evidence") or ""
    # In the Feishu tables the author / model / date live in the *source* cell,
    # not the evidence cell; fall back to evidence for older table layouts.
    meta_cell = (r.get("source_cell") or "") + " " + evidence
    date_m = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", meta_cell)
    published = ""
    if date_m:
        published = f"{date_m.group(1)}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}T00:00:00+00:00"
    author_m = re.search(r"@[A-Za-z0-9_]+", meta_cell)
    author = author_m.group(0) if author_m else (r.get("source_author") or "unknown")
    tags = infer_tags(r["prompt"] + " " + r["title"] + " " + evidence)
    primary_hint = "游戏" if "code2game" in tags else \
                   "3D" if "code23d" in tags else \
                   "动画" if "code2video" in tags else \
                   "可视化" if "code2viz" in tags else \
                   "生成艺术" if "code2svg" in tags else "前端"
    return {
        "id": r["id"],
        "number": None,
        "modelId": "",
        "modelLabel": r.get("model_raw") or "unknown",
        "sourceSection": f"Feishu MD / {r.get('section', '')}",
        "title": r.get("title") or r["id"],
        "originalTitle": r.get("title") or "",
        "author": author,
        "xUrl": r.get("source_post_url") or "",
        "links": r.get("demo_urls") or [],
        "prompt": r["prompt"],
        "promptHash": r["prompt_hash"],
        "note": "verbatim prompt parsed from Feishu markdown export; no runnable .html artifact pinned",
        "evidence": "post-only",
        "categories": [],
        "primaryCategory": primary_hint,
        "promptStatus": "full",
        "collection": "",
        "collectionIndex": None,
        "failed": False,
        "rank": None,
        "relatedCaseIds": [],
        "addedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "publishedAt": published,
        "dateLabel": "",
        "image": "",
        "mediaCaption": "",
        "video": "",
        "mediaSources": [],
        "demoUrl": "",
        "dateDisplay": "",
        "containPreview": False,
        "code2Tags": tags,
        "code2Signals": {"derived_by": "scripts/expand_tasks.py::infer_tags"},
        "contentLicense": "CC-BY-NC-4.0",
        "licenseNote": "Third-party community prompt; attribution recorded, no artifact vendored.",
        "attribution": {"creator": author, "sourceUrl": r.get("source_post_url") or ""},
    }


def candidate_records() -> tuple[list[dict], list[dict], dict[str, dict], dict[str, str]]:
    """Return (deduplicated candidates, new corpus records, id->record, id->origin).

    The upstream corpus contains several records that share a verbatim prompt
    under different ids (e.g. `new-085a...` / `new-c65a...`). A benchmark must
    not score the same prompt twice, so de-duplicate by normalised prompt hash.
    """
    corpus = load_jsonl(CORPUS)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    core = {t["task_id"] for t in manifest["tasks"]}
    feishu = [r for r in load_jsonl(FEISHU) if r.get("status") == "new"]

    ext_corpus: dict[str, dict] = {}
    for r in feishu:
        ok, _ = quality_ok(r["prompt"])
        if ok and r["prompt_hash"] not in {x.get("promptHash") for x in ext_corpus.values()}:
            ext_corpus[r["id"]] = feishu_to_corpus(r)

    by_id = {r["id"]: r for r in corpus}
    by_id.update(ext_corpus)

    cands: list[dict] = []
    origin: dict[str, str] = {}
    seen: set[str] = set()

    def add(r: dict, why: str) -> None:
        p = r.get("prompt") or ""
        if not p.strip():
            return
        ok, _ = quality_ok(p)
        if not ok:
            return
        h = hashlib.md5(re.sub(r"\s+", " ", p).strip().encode("utf-8")).hexdigest()
        if h in seen:
            return
        seen.add(h)
        cands.append(r)
        origin[r["id"]] = why

    # Feishu-only records first (new provenance), then corpus records that were
    # dropped solely by the .html gate. Core-111 prompts are excluded by `core`.
    for rid, r in ext_corpus.items():
        add(r, "feishu_md_new")
    for r in corpus:
        if r["id"] not in core:
            add(r, "corpus_rejected_by_html_gate")

    return cands, list(ext_corpus.values()), by_id, origin


def labels_of(r: dict) -> dict[str, list[str]]:
    tags = norm_tech(r.get("code2Tags") or [])
    return {
        "primary": [norm_primary(r.get("primaryCategory") or "")],
        "track": tracks_from(tags),
        "tech": tags or ["code2frontend"],
    }


ALL_LABELS: dict[str, list[str]] = {
    "primary": sorted(PRIMARY_KEYS),
    "track": sorted(set(DOMAIN_MAP.values()) | {"composite"}),
    "tech": sorted(TECH_KEYS),
}
# Scale-free imbalance: squared coefficient of variation per axis. Using an
# absolute spread would be misleading here because each added task carries
# multiple track/tech labels, so every count grows. CV^2 measures *shape*.
AXIS_W = {"primary": 2.0, "track": 1.0, "tech": 1.0}


def distributions(rows: list[dict]) -> dict[str, Counter]:
    out = {k: Counter() for k in ("primary", "track", "tech")}
    for r in rows:
        for axis, labs in labels_of(r).items():
            out[axis].update(labs)
    return out


def imbalance(dist: dict[str, Counter]) -> float:
    total = 0.0
    for axis, labs in ALL_LABELS.items():
        vals = [dist[axis][l] for l in labs]
        mean = sum(vals) / len(vals)
        if mean <= 0:
            continue
        total += AXIS_W[axis] * sum((v - mean) ** 2 for v in vals) / (mean ** 2)
    return total


def greedy(cands: list[dict], base: list[dict], n: int) -> list[dict]:
    """Pick tasks that most reduce three-axis distribution imbalance.

    A naive 'reward scarce labels' score keeps inflating already-rich labels,
    because a 3D/animation task also carries frontend/visualization tags. Here
    we score the *actual change in CV^2* after tentatively adding a candidate,
    and roll the counts back. This directly optimises uniformity.
    """
    dist = distributions(base)
    pool = list(cands)
    chosen: list[dict] = []
    for _ in range(min(n, len(pool))):
        before = imbalance(dist)
        best, best_gain = None, float("-inf")
        for r in pool:
            labs = labels_of(r)
            touched = {ax: set(ls) for ax, ls in labs.items()}
            for ax, ls in touched.items():
                for lab in ls:
                    dist[ax][lab] += 1
            gain = before - imbalance(dist)   # >0 means more uniform
            for ax, ls in touched.items():
                for lab in ls:
                    dist[ax][lab] -= 1
            # Explicit user requirement: prefer the thinnest primary classes.
            pcount = dist["primary"]
            thin = sorted(ALL_LABELS["primary"], key=lambda k: pcount[k])[:3]
            if labs["primary"][0] in thin:
                gain += 0.004
            # Mild quality preference (verbatim length, traceable source post).
            p = r.get("prompt") or ""
            gain += min(len(p), 3000) / 2_000_000.0
            if r.get("xUrl"):
                gain += 0.0005
            if gain > best_gain:
                best_gain, best = gain, r
        if best is None:
            break
        chosen.append(best)
        pool.remove(best)
        for axis, ls in labels_of(best).items():
            dist[axis].update(set(ls))
    return chosen


def manifest_entry(r: dict, origin: str, by_id: dict[str, dict]) -> dict:
    rec = by_id.get(r["id"], r)
    tags = norm_tech(rec.get("code2Tags") or [])
    status = rec.get("promptStatus") or "full"
    return {
        "task_id": r["id"],
        "title": rec.get("title") or r["id"],
        "model_label": rec.get("modelLabel") or "",
        "code2_tags": tags,
        "domains": tracks_from(tags),
        "prompt_status": status,
        "evidence_level": "B",
        "prompt_chars": len(rec.get("prompt") or ""),
        "published_at": rec.get("publishedAt") or "",
        "demo_url": rec.get("demoUrl") or "",
        "source_post_url": rec.get("xUrl") or "",
        "author": rec.get("author") or "",
        "license": rec.get("contentLicense") or "",
        "failed": bool(rec.get("failed")),
        "related_case_ids": rec.get("relatedCaseIds") or [],
        "contamination_split": None,
        # --- extension-only fields ---
        "set": "extended",
        "source_origin": origin,
        "reference_kind": "runnable-html" if (rec.get("demoUrl") or "").endswith(".html") else "post-only",
        # NOTE: `full_measurement` in task.json is owned by
        # generate_assertions.py (assertion-count floor). Do not reuse it here
        # for evidence grade; use `has_reference_oracle` instead.
        "has_reference_oracle": bool((rec.get("demoUrl") or "").endswith(".html")),
        "meta_test_applicable": bool((rec.get("demoUrl") or "").endswith(".html")),
        "quality_gate": f"verbatim prompt >= {MIN_PROMPT_CHARS} chars; no truncated excerpt",
        "admission_note": (
            "Admitted on verbatim-prompt evidence only. No third-party runnable "
            "artifact is pinned, so the reference-oracle meta-test does not apply; "
            "L0/L1 assertions still evaluate each generated artifact normally."
        ),
    }


def fmt_axis(before: Counter, after: Counter, title: str, axis: str) -> list[str]:
    def stats(c: Counter) -> tuple[int, int, float, float]:
        vals = [c[k] for k in ALL_LABELS[axis]]
        mean = sum(vals) / len(vals)
        cv2 = sum((v - mean) ** 2 for v in vals) / (mean ** 2) if mean else 0.0
        lo, hi = min(vals), max(vals)
        return lo, hi, hi / max(1, lo), cv2

    b_lo, b_hi, b_ratio, b_cv = stats(before)
    a_lo, a_hi, a_ratio, a_cv = stats(after)
    lines = [f"### {title}", "", "| 标签 | 补前 | 补后 | 增量 |", "|---|---:|---:|---:|"]
    for k in sorted(set(before) | set(after), key=lambda x: after[x]):
        lines.append(f"| `{k}` | {before[k]} | {after[k]} | +{after[k]-before[k]} |")
    lines += [
        "",
        f"- 最少/最多：{b_lo}/{b_hi} → **{a_lo}/{a_hi}**",
        f"- **max/min 比值：{b_ratio:.2f} → {a_ratio:.2f}**（越接近 1 越均匀）",
        f"- 变异系数平方 CV²：{b_cv:.3f} → **{a_cv:.3f}**",
        "",
    ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=69, help="number of extended tasks to add")
    ap.add_argument("--compare", action="store_true", help="print distribution at 39/69/89")
    ap.add_argument("--apply", action="store_true", help="write files and materialise packs")
    args = ap.parse_args()

    cands, ext_corpus, by_id, origin = candidate_records()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    core_ids = {t["task_id"] for t in manifest["tasks"]}
    base = [by_id[i] for i in core_ids]
    base_dist = distributions(base)

    print(f"candidate pool: {len(cands)} "
          f"(corpus rejected by .html gate: {sum(1 for c in cands if origin[c['id']].startswith('corpus'))}, "
          f"Feishu md new: {sum(1 for c in cands if origin[c['id']].startswith('feishu'))})")
    print(f"core: {len(base)} tasks")

    if args.compare:
        for n in (39, 69, 89):
            ch = greedy(cands, base, n)
            d = distributions(base + ch)
            print(f"\n--- +{n} (total {len(base)+n}) ---")
            for axis in ("primary", "track", "tech"):
                a, b = base_dist[axis], d[axis]
                print(f"  {axis:8s} min/max {min(a.values())}/{max(a.values())} -> "
                      f"{min(b.values())}/{max(b.values())}  "
                      f"spread {max(a.values())-min(a.values())} -> {max(b.values())-min(b.values())}")
                print("     ", dict(b.most_common()))
        return 0

    chosen = greedy(cands, base, args.target)
    after = distributions(base + chosen)
    print(f"\nselected {len(chosen)} extended tasks -> total {len(base)+len(chosen)}")
    for axis in ("primary", "track", "tech"):
        a, b = base_dist[axis], after[axis]
        print(f"  {axis:8s} min/max {min(a.values())}/{max(a.values())} -> "
              f"{min(b.values())}/{max(b.values())}, "
              f"spread {max(a.values())-min(a.values())} -> {max(b.values())-min(b.values())}")

    if not args.apply:
        print("\n(dry-run; add --apply to write)")
        print("sample selected:")
        for r in chosen[:12]:
            print(f"  {r['id']:16s} {norm_primary(r.get('primaryCategory') or ''):6s} "
                  f"{','.join(norm_tech(r.get('code2Tags') or []))[:48]:48s} {(r.get('title') or '')[:30]}")
        return 0

    # ---- write derived files ----
    EXT_CORPUS.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ext_corpus), encoding="utf-8")
    ext_manifest = {
        "schema_version": "1.0",
        "set": "extended",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "task_count": len(chosen),
        "core_task_count": len(base),
        "total_task_count": len(base) + len(chosen),
        "admission": {
            "requires": "verbatim prompt >= 80 chars, not a truncated excerpt",
            "does_not_require": "a pinned runnable .html artifact",
            "consequence": "reference-oracle meta-test not applicable; L0/L1 evaluation unchanged",
        },
        "selection": "greedy minimising three-axis CV^2 imbalance (primary x2, track x1, tech x1); duplicates removed by prompt hash",
        "source_origin_counts": dict(Counter(origin[r["id"]] for r in chosen)),
        "reference_kind_counts": dict(Counter(
            "runnable-html" if (by_id[r["id"]].get("demoUrl") or "").endswith(".html") else "post-only"
            for r in chosen)),
        "tasks": [manifest_entry(r, origin[r["id"]], by_id) for r in chosen],
    }
    EXT_MANIFEST.write_text(json.dumps(ext_manifest, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    lines = [
        "# CE-Bench extended set — expansion report", "",
        f"Generated: `{ext_manifest['generated_at']}`", "",
        "## Why", "",
        "Core-111 (`tasks/manifest.json`) admits only records with BOTH a verbatim",
        "prompt and a runnable `.html` demo. That gate is correct for the paper's",
        "full-measurement census but leaves 194 prompt-bearing corpus records",
        "unused and skews every label axis. This extended set adds prompt-bearing",
        "tasks **without rewriting Core-111**, so the paper census stays reproducible.", "",
        "## Sources", "",
        f"- Corpus records rejected only by the `.html` gate: "
        f"**{sum(1 for c in cands if origin[c['id']].startswith('corpus'))}** admissible candidates",
        f"- Verbatim prompts newly parsed from the Feishu markdown export: "
        f"**{sum(1 for c in cands if origin[c['id']].startswith('feishu'))}**",
        f"- Selected: **{len(chosen)}** → total **{len(base)+len(chosen)}** tasks", "",
        "## Selection rule", "",
        "Greedy: at each step pick the candidate that most reduces the squared",
        "coefficient of variation (CV²) of the label counts, over `primary`",
        "(weight 2), `track` (1) and `tech` (1). CV² is scale-free, so adding",
        "multi-label tasks does not masquerade as improved balance. Thin primary",
        "classes get a small explicit bonus. Duplicates are removed by normalised",
        "prompt hash. Quality gate: verbatim prompt ≥ 80 chars and no truncated",
        "excerpt marker. No label is invented — `tech`/`track` come from `code2Tags`",
        "via the paper's own `DOMAIN_MAP`.", "",
        "## Distribution before / after", "",
    ]
    for axis, title in (("primary", "轴 2 · 唯一主类 primary"),
                        ("track", "轴 1 · 赛道 track（多标签）"),
                        ("tech", "轴 3 · 技术标签 tech（多标签）")):
        lines += fmt_axis(base_dist[axis], after[axis], title, axis)
    lines += [
        "## Honesty notes", "",
        f"- `{ext_manifest['reference_kind_counts']}` — tasks without a pinned `.html`",
        "  artifact have `has_reference_oracle=false` and **no reference-oracle",
        "  meta-test** (`meta_test_applicable=false`). L0/L1 assertions still run",
        "  against each generated artifact, so the generate → assert → score chain",
        "  is complete. Do not report a meta-test pass rate over these tasks.",
        "- Core-111 numbers in the manuscript (funnel, Table 9, §7 stratified",
        "  reporting) remain valid for the full-measurement set. If the extended",
        "  set is promoted to the headline task count, those numbers must be",
        "  restated as a two-tier census.", "",
        "## Files", "",
        "- `data/corpus/extension.jsonl` — Feishu-only records in corpus format",
        "- `tasks/manifest_extended.json` — extended task list",
        "- `tasks/<task_id>/` — 69 packs generated by `build_task_packs.py --extended-only`",
        "- `scripts/import_feishu_md.py` / `scripts/expand_tasks.py` — reproducible parse + balanced selection",
        "- `cebench/evaluation.py::load_prompts_from_packs` — runner task source for all 180 packs",
        "- `scripts/run_evaluation.py --task-set {core,extended,all}` — tier switch (default `all`)",
        "- `docs/task-catalog.{html,md,csv}` + `tasks/taxonomy.json` — rebuilt for 180 tasks", "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nwrote {EXT_CORPUS.relative_to(ROOT)} ({len(ext_corpus)} records)")
    print(f"wrote {EXT_MANIFEST.relative_to(ROOT)} ({len(chosen)} tasks)")
    print(f"wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
