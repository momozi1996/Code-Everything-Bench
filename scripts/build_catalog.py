#!/usr/bin/env python3
"""Build the CE-Bench task catalogue: an interactive single-file HTML table,
a taxonomy page, a Markdown table, a CSV and a machine-readable taxonomy JSON.

Usage:
    python3 scripts/build_catalog.py

Inputs (all local, pinned):
    tasks/manifest.json              111 selected tasks (funnel 739 -> 305 -> 111)
    data/corpus/cases.jsonl          pinned upstream corpus (739 records)
    tasks/<id>/task.json             materialised pack metadata
    tasks/<id>/assertions/task.json per-task L1 assertions
    tasks/<id>/assertions/meta_test.json  reference-as-oracle check

Outputs:
    tasks/taxonomy.json             machine-readable 3-axis taxonomy + derived tags
    docs/task-catalog.html          interactive table + taxonomy tab (no deps)
    docs/task-catalog.csv           flat table
    docs/task-catalog.md            Markdown table
"""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TASKS = ROOT / "tasks"

# ---------------------------------------------------------------- taxonomy ---

TRACKS = {
    "visualization":   ("数据可视化",   "Frontend", "图表、物理模拟、数据映射与信息呈现"),
    "frontend":        ("前端 / 网页", "Frontend", "页面结构、UI 组件、布局与交互界面"),
    "svg-art":         ("SVG 生成艺术", "Frontend", "矢量程序化艺术、图形构成与几何美学"),
    "3d":              ("3D / WebGL",  "3D",       "三维场景、相机、光照、材质与实时渲染"),
    "audio":           ("音频",        "Animation", "声音合成、音频可视化与节奏驱动"),
    "animation-video": ("动画 / 视频", "Animation", "时间轴动效、过渡、镜头与逐帧输出"),
    "game":            ("游戏",        "Game",      "可玩规则、输入处理、状态机与胜负判定"),
    "composite":       ("复合任务",    "Overall",   "跨多类、需整体评定的复合交付物"),
}

PRIMARY = {
    "生成艺术": ("svg-art",         "程序化生成艺术为主"),
    "可视化":   ("visualization",   "数据/现象可视化为主"),
    "网页":     ("frontend",        "完整网页与站点"),
    "3D":       ("3d",              "三维场景"),
    "动画":     ("animation-video", "时间轴动效"),
    "工具":     ("frontend",        "实用工具与应用"),
    "前端":     ("frontend",        "前端组件与界面"),
    "游戏":     ("game",            "可玩游戏"),
}

TECH = {
    "code2frontend": ("frontend",        "HTML/CSS/JS 前端实现"),
    "code2viz":      ("visualization",   "可视化与数据映射"),
    "code2svg":      ("svg-art",         "SVG 矢量图形"),
    "code2canvas":   ("visualization",   "Canvas 2D 绘制"),
    "code23d":       ("3d",              "Three.js / WebGL / 三维"),
    "code2audio":    ("audio",           "Web Audio / 声音"),
    "code2video":    ("animation-video", "视频 / 镜头 / 帧输出"),
    "code2game":     ("game",            "游戏机制与交互规则"),
    "code2css":      ("frontend",        "CSS 样式与布局"),
    "code2world":    ("3d",              "世界 / 地形 / 场景生成"),
    "code2html":     ("frontend",        "HTML 结构"),
    "code2deck":     ("frontend",        "演示文稿 / 幻灯片"),
}

LANG_LABEL = {"zh": "中文", "en": "英文", "mixed": "中英混合"}
STATUS_LABEL = {
    "full": "完整原文", "transcribed": "转录", "repository": "仓库摘录",
    "context": "上下文推断",
}
BUCKET_LABEL = {
    "S": "短 (<400)", "M": "中 (400–1499)", "L": "长 (1500–2999)",
    "XL": "超长 (≥3000)",
}


def detect_lang(text: str) -> str:
    zh = len(re.findall(r"[\u4e00-\u9fff]", text))
    body = re.sub(r"\s", "", text) or " "
    ratio = zh / len(body)
    if ratio > 0.12:
        return "zh"
    return "en" if ratio < 0.02 else "mixed"


def bucket(n: int) -> str:
    if n < 400:
        return "S"
    if n < 1500:
        return "M"
    if n < 3000:
        return "L"
    return "XL"


def source_group(rec: dict) -> str:
    label = rec.get("modelLabel") or ""
    if label != "Claude Opus 5.5":
        return label.replace("GPT-6 ", "GPT-6 · ")
    demo = rec.get("demoUrl") or ""
    if rec.get("collection") or "Claude-Opus-5.5-100-HTML-Files" in demo:
        return "Opus-100 合辑"
    return "社区单帖"


def load() -> list[dict]:
    manifest = json.loads((TASKS / "manifest.json").read_text(encoding="utf-8"))
    meta = {t["task_id"]: t for t in manifest["tasks"]}
    corpus = {}
    for line in (ROOT / "data" / "corpus" / "cases.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            r = json.loads(line)
            corpus[r["id"]] = r

    out = []
    for tid in meta:
        rec = corpus[tid]
        m = meta[tid]
        pack_path = TASKS / tid / "task.json"
        pack = json.loads(pack_path.read_text(encoding="utf-8")) if pack_path.is_file() else {}
        apath = TASKS / tid / "assertions" / "task.json"
        assertions = json.loads(apath.read_text(encoding="utf-8"))["assertions"] \
            if apath.is_file() else []
        mpath = TASKS / tid / "assertions" / "meta_test.json"
        mtest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.is_file() else {}

        prompt = rec.get("prompt") or ""
        tracks = list(m.get("domains") or [])
        tech = list(m.get("code2_tags") or [])
        primary = rec.get("primaryCategory") or "未分类"
        related = rec.get("relatedCaseIds") or []

        out.append({
            "seq": 0,                      # filled after sorting
            "n": rec.get("number"),        # upstream corpus number (not 1..111)
            "corpus_number": rec.get("number"),
            "id": tid,
            "title": m.get("title") or rec.get("title") or "",
            "original_title": rec.get("originalTitle") or "",
            "primary": primary,
            "primary_track": PRIMARY.get(primary, ("composite", ""))[0],
            "categories": rec.get("categories") or [],
            "tracks": tracks,
            "track_count": len(tracks),
            "tech": tech,
            "lang": detect_lang(prompt),
            "prompt_chars": len(prompt),
            "prompt_bucket": bucket(len(prompt)),
            "prompt_status": rec.get("promptStatus") or "",
            "evidence": m.get("evidence_level") or "",
            "model_label": rec.get("modelLabel") or "",
            "author": rec.get("author") or "",
            "published_at": rec.get("publishedAt") or "",
            "date_display": rec.get("dateDisplay") or "",
            "source_group": source_group(rec),
            "collection_index": rec.get("collectionIndex"),
            "rank": (round(rec["rank"], 2) if isinstance(rec.get("rank"), (int, float)) else rec.get("rank")),
            "related": related,
            "replay": bool(related),
            "assertion_count": len(assertions),
            "assertion_kinds": sorted({a.get("kind", "") for a in assertions}),
            "meta_test": "pass" if mtest.get("assertions_ok") else "review",
            "l1_failed": [f["name"] for f in (mtest.get("l1_failed") or [])],
            "license": pack.get("license") or rec.get("contentLicense") or "",
            "demo_url": rec.get("demoUrl") or "",
            "source_post_url": rec.get("xUrl") or "",
            "reference_url": m.get("demo_url") or "",
            "signals": rec.get("code2Signals") or {},
            "note": rec.get("note") or "",
            "prompt": prompt,
            "prompt_excerpt": re.sub(r"\s+", " ", prompt)[:150],
            "mode": pack.get("mode") or "",
            "track_ce": pack.get("track") or "",
            "four_dimensions": pack.get("four_dimensions") or {},
        })
    out.sort(key=lambda x: (x["n"] if isinstance(x["n"], int) else 9999, x["id"]))
    for i, r in enumerate(out, 1):
        r["seq"] = i
    return out


def build_taxonomy(rows: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "task_count": len(rows),
        "description": (
            "CE-Bench 三轴分类标签体系。track 为多标签主赛道（与论文 §7 "
            "judge 维度对齐）；primary 为唯一主类；tech 为技术实现标签。"
            "派生标签用于分层统计，不改变评分口径。POST/PRE 污染切分仍由"
            "运行时按各配置 training_cutoff 计算，不静态写入。"
        ),
        "axes": {
            "track": {
                k: {"label_zh": v[0], "rubric_hint": v[1], "description": v[2]}
                for k, v in TRACKS.items()
            },
            "primary": {
                k: {"track_hint": v[0], "description": v[1]}
                for k, v in PRIMARY.items()
            },
            "tech": {
                k: {"track_hint": v[0], "description": v[1]}
                for k, v in TECH.items()
            },
        },
        "derived": {
            "lang": LANG_LABEL,
            "prompt_bucket": BUCKET_LABEL,
            "prompt_status": STATUS_LABEL,
            "source_group": "Opus-100 合辑 / 社区单帖 / GPT-6 · Astra / Sol / Luna",
            "meta_test": {"pass": "reference 通过全部断言", "review": "断言偏严或 reference 未通过，待人工复核"},
            "replay": "relatedCaseIds 非空，可做 Replay 对照",
            "track_count": "该题命中的赛道数（复合度代理指标）",
        },
        "tasks": {
            r["id"]: {
                "primary": r["primary"],
                "primary_track": r["primary_track"],
                "tracks": r["tracks"],
                "tech": r["tech"],
                "categories": r["categories"],
                "lang": r["lang"],
                "prompt_bucket": r["prompt_bucket"],
                "source_group": r["source_group"],
                "track_count": r["track_count"],
                "replay": r["replay"],
                "meta_test": r["meta_test"],
                "assertion_count": r["assertion_count"],
            }
            for r in rows
        },
    }


# ------------------------------------------------------------------ outputs ---

COLS = [
    ("seq", "序号"), ("id", "任务 ID"), ("title", "题目"),
    ("primary", "主类"), ("tracks", "赛道标签"), ("tech", "技术标签"),
    ("lang", "语言"), ("prompt_chars", "Prompt 字数"),
    ("prompt_bucket", "长度档"), ("prompt_status", "Prompt 状态"),
    ("evidence", "证据级别"), ("source_group", "来源组"),
    ("model_label", "来源模型"), ("author", "作者"),
    ("date_display", "发布日期"), ("replay", "Replay"),
    ("assertion_count", "L1 断言"), ("meta_test", "参考自检"),
    ("license", "授权"), ("demo_url", "Demo"),
    ("source_post_url", "原帖"), ("prompt_excerpt", "Prompt 摘要"),
]


def write_csv(rows: list[dict]) -> None:
    if not DOCS.is_dir():
        DOCS.mkdir()
    p = DOCS / "task-catalog.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([c[1] for c in COLS])
        for r in rows:
            line = []
            for k, _ in COLS:
                v = r[k]
                if isinstance(v, list):
                    v = "|".join(map(str, v))
                elif isinstance(v, bool):
                    v = "Y" if v else ""
                elif v is None:
                    v = ""
                line.append(v)
            w.writerow(line)
    print(f"  {p.relative_to(ROOT)}  ({len(rows)} rows)")


def write_md(rows: list[dict], tax: dict) -> None:
    lines = [
        "# CE-Bench 111 题总表与分类标签",
        "",
        f"> 生成时间：{tax['generated_at']} ｜ 任务数：**{len(rows)}** ｜ "
        "数据源：`tasks/manifest.json` + pinned `data/corpus/cases.jsonl` + 111 个任务包",
        "",
        "## 一、分类标签体系（三轴）",
        "",
        "**轴 1 · 主赛道 `track`**（多标签，与论文 §7 judge 维度对齐）",
        "",
        "| 赛道 | 中文 | 题数 | 占比 | 建议评审维度 | 说明 |",
        "|---|---|---:|---:|---|---|",
    ]
    tc = Counter(t for r in rows for t in r["tracks"])
    for k, (zh, rub, desc) in TRACKS.items():
        n = tc[k]
        lines.append(f"| `{k}` | {zh} | {n} | {n/len(rows)*100:.1f}% | {rub} | {desc} |")
    lines += [
        "",
        "> 多标签，题数之和大于 111。`rubric_hint` 为建议映射，非强制评分口径。",
        "",
        "**轴 2 · 唯一主类 `primary`**（中文 8 类，来自上游语料）",
        "",
        "| 主类 | 题数 | 建议赛道 | 说明 |",
        "|---|---:|---|---|",
    ]
    pc = Counter(r["primary"] for r in rows)
    for k, (hint, desc) in PRIMARY.items():
        lines.append(f"| {k} | {pc[k]} | `{hint}` | {desc} |")
    lines += [
        "",
        "**轴 3 · 技术标签 `tech`**（12 个，来自 `code2Tags` 信号抽取）",
        "",
        "| 标签 | 题数 | 归属赛道 | 说明 |",
        "|---|---:|---|---|",
    ]
    cc = Counter(t for r in rows for t in r["tech"])
    for k, (hint, desc) in TECH.items():
        lines.append(f"| `{k}` | {cc[k]} | `{hint}` | {desc} |")
    lines += [
        "",
        "**派生标签**：语言（zh/en/mixed）、长度档（S/M/L/XL）、Prompt 状态、"
        "证据级别（A/B）、来源组、Replay、L1 断言数、参考自检（pass/review）、"
        "复合度（track_count）。POST/PRE 污染切分为运行时按 `training_cutoff` 计算，不静态写入。",
        "",
        "## 二、111 题详细总表",
        "",
        "| 序号 | ID | 题目 | 主类 | 赛道 | 技术标签 | 语言 | 字数 | 档 | Prompt | 证据 | 来源组 | 模型 | 作者 | 日期 | Replay | 断言 | 自检 | 授权 | Demo | 原帖 |",
        "|---:|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---|:---:|---:|---|---|---|---|",
    ]

    def esc(s):
        return str(s).replace("|", "\\|").replace("\n", " ")

    for r in rows:
        demo = f"[demo]({r['demo_url']})" if r["demo_url"] else ""
        post = f"[原帖]({r['source_post_url']})" if r["source_post_url"] else ""
        lines.append(
            f"| {r['seq']} | `{r['id']}` | {esc(r['title'])} | {r['primary']} "
            f"| {', '.join(f'`{x}`' for x in r['tracks'])} "
            f"| {', '.join(f'`{x}`' for x in r['tech'])} "
            f"| {LANG_LABEL[r['lang']]} | {r['prompt_chars']} | {r['prompt_bucket']} "
            f"| {STATUS_LABEL.get(r['prompt_status'], r['prompt_status'])} "
            f"| {r['evidence']} | {r['source_group']} | {esc(r['model_label'])} "
            f"| {esc(r['author'])} | {r['date_display']} "
            f"| {'Y' if r['replay'] else ''} | {r['assertion_count']} "
            f"| {'PASS' if r['meta_test'] == 'pass' else 'REVIEW'} "
            f"| {r['license']} | {demo} | {post} |"
        )
    lines += [
        "",
        "## 三、分层统计",
        "",
        f"- 语言：{dict(Counter(LANG_LABEL[r['lang']] for r in rows))}",
        f"- 长度档：{dict(Counter(BUCKET_LABEL[r['prompt_bucket']] for r in rows))}",
        f"- Prompt 状态：{dict(Counter(STATUS_LABEL.get(r['prompt_status'], r['prompt_status']) for r in rows))}",
        f"- 证据级别：{dict(Counter(r['evidence'] for r in rows))}",
        f"- 来源组：{dict(Counter(r['source_group'] for r in rows))}",
        f"- 参考自检：{dict(Counter(r['meta_test'] for r in rows))}",
        f"- 复合度（命中赛道数）：{dict(sorted(Counter(r['track_count'] for r in rows).items()))}",
        "",
        "> 机读版见 `tasks/taxonomy.json`；可筛选/可展开 Prompt 全文的交互版见 "
        "`docs/task-catalog.html`（另含「分类标签」页与交叉矩阵）。",
        "",
    ]
    p = DOCS / "task-catalog.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {p.relative_to(ROOT)}  ({len(lines)} lines)")


def write_html(rows: list[dict], tax: dict) -> None:
    payload = json.dumps({"rows": rows, "tax": tax, "labels": {
        "tracks": {k: list(v) for k, v in TRACKS.items()},
        "primary": {k: list(v) for k, v in PRIMARY.items()},
        "tech": {k: list(v) for k, v in TECH.items()},
        "lang": LANG_LABEL, "status": STATUS_LABEL, "bucket": BUCKET_LABEL,
    }}, ensure_ascii=False).replace("</", "<\\/")

    tpl = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CE-Bench · 111 题总表与分类标签</title>
<style>
:root{
  --bg:#f7f8fa; --panel:#fff; --ink:#1c2026; --muted:#6b7280; --line:#e5e7eb;
  --accent:#2f6feb; --accent-soft:#eaf1ff; --chip:#eef2f7; --chip-ink:#394150;
  --ok:#177245; --ok-bg:#e8f5ed; --warn:#a15c00; --warn-bg:#fff3df;
  --shadow:0 1px 3px rgba(16,24,40,.06),0 8px 24px rgba(16,24,40,.05);
}
@media (prefers-color-scheme:dark){
:root{--bg:#11151b;--panel:#191f27;--ink:#e8ecf2;--muted:#98a2b3;--line:#2a323d;
 --accent:#7aa7ff;--accent-soft:#1d2b45;--chip:#242c37;--chip-ink:#c9d2df;
 --ok:#6ddb9a;--ok-bg:#173526;--warn:#f0b45e;--warn-bg:#3a2a12;
 --shadow:0 1px 3px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.25);}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:1680px;margin:0 auto;padding:26px 22px 70px}
header h1{font-size:23px;margin:0 0 6px;letter-spacing:-.3px}
header p{margin:0;color:var(--muted);font-size:13px}
.tabs{display:flex;gap:6px;margin:22px 0 16px;border-bottom:1px solid var(--line)}
.tab{appearance:none;border:0;background:transparent;color:var(--muted);cursor:pointer;
 padding:10px 18px;font-size:14px;font-weight:600;border-bottom:2px solid transparent}
.tab:hover{color:var(--ink)}
.tab.on{color:var(--accent);border-bottom-color:var(--accent)}
.view{display:none}.view.on{display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.card .k{font-size:11px;color:var(--muted);letter-spacing:.4px;text-transform:uppercase}
.card .v{font-size:25px;font-weight:700;margin-top:3px;letter-spacing:-.5px}
.card .s{font-size:11px;color:var(--muted);margin-top:2px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;
 padding:16px 18px;box-shadow:var(--shadow);margin-bottom:16px}
.panel h2{font-size:15px;margin:0 0 12px}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
input[type=search],select{background:var(--panel);color:var(--ink);border:1px solid var(--line);
 border-radius:8px;padding:7px 10px;font-size:13px;outline:none}
input[type=search]{min-width:250px;flex:1}
input[type=search]:focus,select:focus{border-color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--chip-ink);
 border-radius:999px;padding:4px 11px;font-size:12px;cursor:pointer;user-select:none;white-space:nowrap}
.chip:hover{border-color:var(--accent)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.bar{height:6px;background:var(--chip);border-radius:4px;overflow:hidden;margin-top:5px}
.bar>i{display:block;height:100%;background:var(--accent);border-radius:4px}
.tiny{font-size:11px;color:var(--muted)}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;
 margin:14px 0 8px;flex-wrap:wrap}
.btn{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;
 padding:7px 13px;font-size:12px;cursor:pointer}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.tablebox{background:var(--panel);border:1px solid var(--line);border-radius:12px;
 overflow:auto;box-shadow:var(--shadow);max-height:78vh}
table{border-collapse:collapse;width:100%;font-size:12.5px;white-space:nowrap}
thead th{position:sticky;top:0;z-index:2;background:var(--panel);text-align:left;
 padding:9px 10px;border-bottom:2px solid var(--line);font-size:11.5px;color:var(--muted);
 font-weight:600;cursor:pointer;letter-spacing:.2px}
thead th:hover{color:var(--accent)}
td code.tid{display:inline-block;max-width:118px;overflow:hidden;text-overflow:ellipsis;
 white-space:nowrap;vertical-align:bottom}
span.au{display:inline-block;max-width:112px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}
tbody td{font-size:11.5px;padding:6px 8px;vertical-align:middle}
table td:nth-child(1){width:42px;color:var(--muted)}
table td:nth-child(3){min-width:132px;max-width:196px;white-space:normal;font-weight:600}
table td:nth-child(5),table td:nth-child(6){white-space:nowrap}
table td:nth-child(9),table td:nth-child(10),table td:nth-child(16){white-space:nowrap}
table td:nth-child(9){min-width:86px}
tbody td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr.main:hover{background:var(--accent-soft)}
tbody tr.detail{display:none;background:var(--bg)}
tbody tr.detail.open{display:table-row}
tbody tr.detail td{padding:14px 18px;white-space:normal}
.mini{display:inline-block;border-radius:5px;padding:1px 6px;font-size:11px;
 background:var(--chip);color:var(--chip-ink);margin:1px 3px 1px 0}
.mini.t{background:var(--accent-soft);color:var(--accent)}
.ok{color:var(--ok);background:var(--ok-bg);border-radius:5px;padding:1px 7px;font-size:11px}
.warn{color:var(--warn);background:var(--warn-bg);border-radius:5px;padding:1px 7px;font-size:11px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border:1px solid var(--line);
 border-radius:8px;padding:12px;font-size:12px;max-height:330px;overflow:auto;margin:8px 0}
.dl{display:grid;grid-template-columns:120px 1fr;gap:4px 12px;font-size:12px;margin-top:8px}
.dl dt{color:var(--muted)}.dl dd{margin:0;word-break:break-all}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.matrix{overflow:auto}table.matrix td,table.matrix th{text-align:center;font-size:11.5px}
table.matrix td.hi{background:var(--accent-soft);color:var(--accent);font-weight:700}
table.matrix tbody th{text-align:left;font-weight:500;color:var(--ink)}
.dist{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.dist h3{font-size:13px;margin:0 0 8px}
.row{display:flex;justify-content:space-between;font-size:12px;margin:5px 0}
tr.pick{cursor:pointer}
tr.pick:hover td,tr.pick:hover th{background:var(--accent-soft)}
.row.pick{cursor:pointer;border-radius:6px;padding:2px 4px;margin:4px -4px}
.row.pick:hover{background:var(--accent-soft);color:var(--accent)}
.foot{color:var(--muted);font-size:11.5px;margin-top:20px;text-align:center}
</style>
</head>
<body><div class="wrap">
<header>
  <h1>CE-Bench · 111 题总表与分类标签</h1>
  <p>数据源：<code>tasks/manifest.json</code> ＋ pinned 语料 <code>data/corpus/cases.jsonl</code> ＋ 111 个任务包 ｜
     生成：<span id="stamp"></span> ｜ 三轴标签：赛道 / 主类 / 技术标签</p>
</header>

<div class="tabs">
  <button class="tab on" data-v="v1">题目总表</button>
  <button class="tab" data-v="v2">分类标签页</button>
  <button class="tab" data-v="v3">分层统计</button>
</div>

<!-- ============================ VIEW 1 ============================ -->
<section class="view on" id="v1">
  <div class="cards" id="cards"></div>
  <div class="panel">
    <h2>筛选</h2>
    <div class="filters">
      <input type="search" id="q" placeholder="搜索 ID / 题目 / 原标题 / 作者 / Prompt 全文…"/>
      <select id="fPrimary"><option value="">全部主类</option></select>
      <select id="fTech"><option value="">全部技术标签</option></select>
      <select id="fSource"><option value="">全部来源组</option></select>
      <select id="fMeta"><option value="">全部自检状态</option><option value="pass">PASS</option><option value="review">REVIEW</option></select>
      <select id="fLang"><option value="">全部语言</option></select>
      <select id="fBucket"><option value="">全部长度档</option></select>
    </div>
    <div class="chips" id="trackChips"></div>
    <div class="tiny" style="margin-top:8px">赛道标签可多选（OR）；点击表头排序；点击任意行展开 Prompt 全文与断言明细。</div>
  </div>
  <div class="toolbar">
    <div class="tiny" id="count"></div>
    <div><button class="btn" id="reset">重置筛选</button> <button class="btn" id="csv">导出当前视图 CSV</button></div>
  </div>
  <div class="tablebox"><table id="tbl">
    <thead><tr>
      <th data-k="seq">序号</th><th data-k="id">任务 ID</th><th data-k="title">题目</th>
      <th data-k="primary">主类</th><th>赛道标签</th><th>技术标签</th>
      <th data-k="lang">语言</th><th data-k="prompt_chars">字数</th>
      <th data-k="prompt_status">Prompt</th><th data-k="evidence">证据</th>
      <th data-k="source_group">来源组</th>
      <th data-k="author">作者</th><th data-k="date_display">日期</th>
      <th data-k="replay">Replay</th><th data-k="assertion_count">断言</th>
      <th data-k="meta_test">参考自检</th><th>链接</th>
    </tr></thead><tbody id="tbody"></tbody>
  </table></div>
</section>

<!-- ============================ VIEW 2 ============================ -->
<section class="view" id="v2">
  <div class="panel">
    <h2>分类标签体系 · 三轴定义</h2>
    <div class="tiny" style="margin-bottom:12px">
      <b>track</b> 为多标签主赛道（与论文 §7 judge 维度对齐，rubric_hint 为建议映射）；
      <b>primary</b> 为唯一主类（上游语料标注）；<b>tech</b> 为技术实现标签（由 <code>code2Signals</code> 抽取）。
      机读版：<code>tasks/taxonomy.json</code>。
    </div>
    <div class="grid2">
      <div><h3 style="font-size:13px">轴 1 · 主赛道 track（多标签）</h3><div class="tablebox" style="max-height:none">
      <table class="matrix" id="axTrack" data-kind="track"><thead><tr><th>赛道</th><th>中文</th><th>题数</th><th>占比</th><th>评审维度</th><th>说明</th></tr></thead><tbody></tbody></table></div></div>
      <div><h3 style="font-size:13px">轴 2 · 唯一主类 primary</h3><div class="tablebox" style="max-height:none">
      <table class="matrix" id="axPrimary" data-kind="primary"><thead><tr><th>主类</th><th>题数</th><th>建议赛道</th><th>说明</th></tr></thead><tbody></tbody></table></div></div>
    </div>
    <h3 style="font-size:13px;margin:18px 0 8px">轴 3 · 技术标签 tech（12 个）</h3>
    <div class="tablebox" style="max-height:none"><table class="matrix" id="axTech" data-kind="tech">
      <thead><tr><th>标签</th><th>题数</th><th>占比</th><th>归属赛道</th><th>说明</th></tr></thead><tbody></tbody></table></div>
  </div>
  <div class="panel">
    <h2>交叉矩阵 · 主类 × 赛道</h2>
    <div class="tiny" style="margin-bottom:10px">单元格为该主类题目<b>命中该赛道的次数</b>；一题可命中多个赛道，故行合计 ≥ 该主类题数，
      列合计即赛道题数（32 列合计 = 304 题次）。高亮（≥5）表示该主类的主要赛道归属。</div>
    <div class="matrix"><table class="matrix" id="cross"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="panel">
    <h2>派生标签字典</h2>
    <div class="dist" id="derived"></div>
  </div>
</section>

<!-- ============================ VIEW 3 ============================ -->
<section class="view" id="v3">
  <div class="panel"><h2>分层统计</h2><div class="dist" id="dists"></div></div>
  <div class="panel"><h2>复合度：每题命中赛道数</h2><div class="dist" id="combo"></div></div>
</section>

<div class="foot">CE-Bench · 单文件离线页面，零外部依赖 · 由 <code>scripts/build_catalog.py</code> 生成</div>
</div>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
const R = D.rows, L = D.labels;
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = n => (n/R.length*100).toFixed(1)+'%';
$('#stamp').textContent = D.tax.generated_at;

/* ---------- tabs ---------- */
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on',v.id===b.dataset.v));
});

/* ---------- cards ---------- */
const stats=[
 ['任务总数', R.length, '漏斗 739 → 305 → 111'],
 ['主赛道', Object.keys(L.tracks).length, '多标签，题次合计 '+R.reduce((a,r)=>a+r.tracks.length,0)],
 ['技术标签', Object.keys(L.tech).length, 'code2Signals 抽取'],
 ['完整 Prompt', R.filter(r=>r.prompt_status==='full').length, pct(R.filter(r=>r.prompt_status==='full').length)+' 为 full'],
 ['Opus-100 合辑', R.filter(r=>r.source_group==='Opus-100 合辑').length, '需注意单源偏置'],
 ['参考自检 PASS', R.filter(r=>r.meta_test==='pass').length, pct(R.filter(r=>r.meta_test==='pass').length)],
 ['L1 断言总数', R.reduce((a,r)=>a+r.assertion_count,0), '每题 8–12 条自动断言'],
 ['Replay 题', R.filter(r=>r.replay).length, '可做对照实验'],
];
$('#cards').innerHTML = stats.map(([k,v,s])=>`<div class="card"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');

/* ---------- filter controls ---------- */
const uniq = k => [...new Set(R.map(r=>r[k]))].filter(Boolean).sort();
const fill=(sel,vals,fmt)=>vals.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=fmt?fmt(v):v;sel.appendChild(o)});
fill($('#fPrimary'), uniq('primary'));
[...new Set(R.flatMap(r=>r.tech))].sort().forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;$('#fTech').appendChild(o)});
fill($('#fSource'), uniq('source_group'));
fill($('#fLang'), uniq('lang'), v=>L.lang[v]);
fill($('#fBucket'), uniq('prompt_bucket').sort(), v=>L.bucket[v]);

const tc={}; R.forEach(r=>r.tracks.forEach(t=>tc[t]=(tc[t]||0)+1));
let active=new Set();
$('#trackChips').innerHTML = Object.keys(L.tracks).sort((a,b)=>tc[b]-tc[a]).map(k=>
  `<span class="chip" data-t="${k}">${L.tracks[k][0]} <b>${tc[k]}</b></span>`).join('');
$('#trackChips').onclick=e=>{const c=e.target.closest('.chip'); if(!c)return;
  const k=c.dataset.t; active.has(k)?active.delete(k):active.add(k);
  c.classList.toggle('on'); render();};

let sortK='seq', sortDir=1;
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{
  const k=th.dataset.k; sortDir = (sortK===k)? -sortDir : 1; sortK=k; render();
});

function current(){
  const q=$('#q').value.trim().toLowerCase();
  return R.filter(r=>{
    if(active.size && !r.tracks.some(t=>active.has(t))) return false;
    if($('#fPrimary').value && r.primary!==$('#fPrimary').value) return false;
    if($('#fTech').value && !r.tech.includes($('#fTech').value)) return false;
    if($('#fSource').value && r.source_group!==$('#fSource').value) return false;
    if($('#fMeta').value && r.meta_test!==$('#fMeta').value) return false;
    if($('#fLang').value && r.lang!==$('#fLang').value) return false;
    if($('#fBucket').value && r.prompt_bucket!==$('#fBucket').value) return false;
    if(q){
      const hay=[r.id,r.title,r.original_title,r.author,r.prompt_excerpt,r.primary,
                 r.source_group,r.model_label,L.status[r.prompt_status]||'',
                 r.tracks.map(t=>L.tracks[t]?.[0]||t).join(' '),
                 r.tech.join(' '),r.prompt].join(' ').toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  }).sort((a,b)=>{
    let x=a[sortK],y=b[sortK];
    if(typeof x==='boolean'){x=x?1:0;y=y?1:0;}
    if(typeof x==='number'&&typeof y==='number') return (x-y)*sortDir;
    return String(x).localeCompare(String(y),'zh')*sortDir;
  });
}

function rowHtml(r,i){
  const tracks=r.tracks.slice(0,2).map(t=>`<span class="mini t" title="${esc(L.tracks[t]?.[2]||'')}">${esc(L.tracks[t]?.[0]||t)}</span>`).join('')
    + (r.tracks.length>3?`<span class="mini" title="${esc(r.tracks.join(', '))}">+${r.tracks.length-2}</span>`:'');
  const shown=r.tech.slice(0,2).map(t=>`<span class="mini">${esc(t)}</span>`).join('')
    + (r.tech.length>4?`<span class="mini" title="${esc(r.tech.join(', '))}">+${r.tech.length-2}</span>`:'');
  const meta=r.meta_test==='pass'?'<span class="ok">PASS</span>':'<span class="warn">REVIEW</span>';
  const links=[r.demo_url?`<a href="${esc(r.demo_url)}" target="_blank" rel="noopener">demo</a>`:'',
               r.source_post_url?`<a href="${esc(r.source_post_url)}" target="_blank" rel="noopener">原帖</a>`:''].filter(Boolean).join(' · ');
  return `<tr class="main" data-i="${i}"><td>${r.seq}</td><td><code class="tid" title="${esc(r.id)}">${esc(r.id)}</code></td>
   <td><b>${esc(r.title)}</b></td><td>${esc(r.primary)}</td><td>${tracks}</td><td>${shown}</td>
   <td>${L.lang[r.lang]}</td><td>${r.prompt_chars} <span class="tiny">${r.prompt_bucket}</span></td>
   <td>${L.status[r.prompt_status]||r.prompt_status}</td><td>${r.evidence}</td>
   <td>${esc(r.source_group)}</td><td><span class="au" title="${esc(r.author)}">${esc(r.author)}</span></td>
   <td>${esc(r.date_display)}</td><td>${r.replay?'Y':''}</td><td>${r.assertion_count}</td>
   <td>${meta}</td><td>${links}</td></tr>
   <tr class="detail" data-d="${i}"><td colspan="17">
     <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
       <div><h3 style="margin:0 0 6px;font-size:13px">Prompt 全文 <span class="tiny">(${r.prompt_chars} 字符)</span></h3>
         <pre>${esc(r.prompt)}</pre></div>
       <div><h3 style="margin:0 0 6px;font-size:13px">元数据</h3>
         <dl class="dl">
           <dt>语料编号</dt><dd>#${r.corpus_number}（rank ${r.rank==null?'—':r.rank}）</dd>
           <dt>原标题</dt><dd>${esc(r.original_title)}</dd>
           <dt>分类</dt><dd>${esc(r.primary)} · ${r.categories.map(esc).join(' / ')}</dd>
           <dt>赛道</dt><dd>${r.tracks.map(esc).join(', ')}（复合度 ${r.track_count}）</dd>
           <dt>技术标签</dt><dd>${r.tech.map(esc).join(', ')}</dd>
           <dt>信号</dt><dd>${esc(JSON.stringify(r.signals))}</dd>
           <dt>模式 / 轨道</dt><dd>${esc(r.mode)} · ${esc(r.track_ce)}</dd>
           <dt>四维标注</dt><dd>${esc(JSON.stringify(r.four_dimensions))}</dd>
           <dt>断言种类</dt><dd>${r.assertion_kinds.map(esc).join(', ')}</dd>
           <dt>参考自检</dt><dd>${meta}${r.l1_failed.length?' · 未过断言：'+esc(r.l1_failed.join(' / ')):''}</dd>
           <dt>关联题</dt><dd>${r.related.length?esc(r.related.join(', ')):'—'}</dd>
           <dt>备注</dt><dd>${esc(r.note)||'—'}</dd>
           <dt>Demo</dt><dd>${r.demo_url?`<a href="${esc(r.demo_url)}" target="_blank">${esc(r.demo_url)}</a>`:'—'}</dd>
           <dt>原帖</dt><dd>${r.source_post_url?`<a href="${esc(r.source_post_url)}" target="_blank">${esc(r.source_post_url)}</a>`:'—'}</dd>
           <dt>发布时间</dt><dd>${esc(r.published_at)}</dd>
         </dl></div></div></td></tr>`;
}

function render(){
  const rows=current();
  $('#tbody').innerHTML=rows.map((r,i)=>rowHtml(r,i)).join('');
  $('#count').textContent=`显示 ${rows.length} / ${R.length} 题` + (active.size?` ｜ 赛道筛选：${[...active].join(' + ')}`:'');
  $('#tbody').onclick=e=>{
    const tr=e.target.closest('tr.main'); if(!tr)return;
    const d=document.querySelector(`tr.detail[data-d="${tr.dataset.i}"]`);
    if(d)d.classList.toggle('open');
  };
}
['q','fPrimary','fTech','fSource','fMeta','fLang','fBucket'].forEach(id=>
  $('#'+id).addEventListener('input',render));
$('#reset').onclick=()=>{active.clear();document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
 ['q','fPrimary','fTech','fSource','fMeta','fLang','fBucket'].forEach(id=>$('#'+id).value='');render();};
$('#csv').onclick=()=>{
  const cols=[['seq','序号'],['id','任务 ID'],['title','题目'],['primary','主类'],['tracks','赛道'],
   ['tech','技术标签'],['lang','语言'],['prompt_chars','字数'],['prompt_bucket','长度档'],
   ['prompt_status','Prompt 状态'],['evidence','证据'],['source_group','来源组'],
   ['model_label','来源模型'],['author','作者'],['date_display','日期'],['replay','Replay'],
   ['assertion_count','L1 断言'],['meta_test','参考自检'],['license','授权'],['demo_url','Demo'],
   ['source_post_url','原帖'],['prompt_excerpt','Prompt 摘要']];
  const q=v=>'"'+String(v==null?'':(Array.isArray(v)?v.join('|'):v)).replace(/"/g,'""')+'"';
  const txt='\ufeff'+[cols.map(c=>q(c[1])).join(',')].concat(current().map(r=>cols.map(c=>q(r[c[0]])).join(','))).join('\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([txt],{type:'text/csv;charset=utf-8'}));
  a.download='ce-bench-task-catalog-view.csv';a.click();URL.revokeObjectURL(a.href);
};
render();

/* ---------- taxonomy tab ---------- */
const bar=n=>`<div class="bar"><i style="width:${Math.min(100,n/R.length*100)}%"></i></div>`;
$('#axTrack tbody').innerHTML=Object.entries(L.tracks).sort((a,b)=>tc[b[0]]-tc[a[0]]).map(([k,v])=>
 `<tr class="pick" data-kind="track" data-val="${k}" title="点击查看该赛道的题目"><td><code>${k}</code></td><td>${v[0]}</td><td><b>${tc[k]||0}</b>${bar(tc[k]||0)}</td><td>${pct(tc[k]||0)}</td><td>${v[1]}</td><td style="text-align:left">${v[2]}</td></tr>`).join('');
const pc={};R.forEach(r=>pc[r.primary]=(pc[r.primary]||0)+1);
$('#axPrimary tbody').innerHTML=Object.entries(L.primary).sort((a,b)=>pc[b[0]]-pc[a[0]]).map(([k,v])=>
 `<tr class="pick" data-kind="primary" data-val="${k}" title="点击查看该主类的题目"><td>${k}</td><td><b>${pc[k]||0}</b>${bar(pc[k]||0)}</td><td><code>${v[0]}</code></td><td style="text-align:left">${v[1]}</td></tr>`).join('');
const cc={};R.forEach(r=>r.tech.forEach(t=>cc[t]=(cc[t]||0)+1));
$('#axTech tbody').innerHTML=Object.entries(L.tech).sort((a,b)=>cc[b[0]]-cc[a[0]]).map(([k,v])=>
 `<tr class="pick" data-kind="tech" data-val="${k}" title="点击查看含该技术标签的题目"><td><code>${k}</code></td><td><b>${cc[k]||0}</b></td><td>${pct(cc[k]||0)}${bar(cc[k]||0)}</td><td><code>${v[0]}</code></td><td style="text-align:left">${v[1]}</td></tr>`).join('');

const tracks=Object.keys(L.tracks), prims=Object.keys(L.primary);
let h='<tr><th>主类 \\ 赛道</th>'+tracks.map(t=>`<th>${L.tracks[t][0]}</th>`).join('')+'<th>合计</th></tr>';
$('#cross thead').innerHTML=h;
const mx={};R.forEach(r=>r.tracks.forEach(t=>{const k=r.primary+'\u0000'+t;mx[k]=(mx[k]||0)+1}));
$('#cross tbody').innerHTML=prims.map(p=>{
  let rowsum=0;const cells=tracks.map(t=>{const n=mx[p+'\u0000'+t]||0;rowsum+=n;
    return `<td class="${n>=5?'hi':''}">${n||'·'}</td>`}).join('');
  return `<tr><th>${p}</th>${cells}<td><b>${rowsum}</b></td></tr>`}).join('')+
  `<tr><th>合计</th>${tracks.map(t=>`<td><b>${tc[t]||0}</b></td>`).join('')}<td>—</td></tr>`;

const distBlock=(title,vals,fmt,kind)=>`<div><h3>${title}</h3>${vals.map(([k,n])=>
 `<div class="row${kind?' pick':''}" ${kind?`data-kind="${kind}" data-val="${esc(k)}"`:''} title="${kind?'点击筛选此类题目':''}"><span>${esc(fmt?fmt(k):k)}</span><b>${n}</b></div>${bar(n)}`).join('')}</div>`;
const cnt=k=>{const c={};R.forEach(r=>c[r[k]]=(c[r[k]]||0)+1);return Object.entries(c).sort((a,b)=>b[1]-a[1])};
$('#derived').innerHTML=[
 distBlock('语言 lang',cnt('lang'),k=>L.lang[k],'lang'),
 distBlock('长度档 prompt_bucket',cnt('prompt_bucket'),k=>L.bucket[k],'bucket'),
 distBlock('Prompt 状态',cnt('prompt_status'),k=>L.status[k],'prompt_status'),
 distBlock('证据级别 evidence',cnt('evidence')),
 distBlock('来源组 source_group',cnt('source_group'),null,'source_group'),
 distBlock('参考自检 meta_test',cnt('meta_test'),null,'meta_test'),
 distBlock('复合度 track_count',cnt('track_count').sort((a,b)=>a[0]-b[0])),
 distBlock('来源模型 model_label',cnt('model_label'),null,'model_label'),
].join('');
$('#dists').innerHTML=[
 distBlock('主类 primary',cnt('primary'),null,'primary'),
 distBlock('来源组',cnt('source_group'),null,'source_group'),
 distBlock('技术标签（多标签）',Object.entries(cc).sort((a,b)=>b[1]-a[1]),null,'tech'),
 distBlock('赛道（多标签）',Object.entries(tc).sort((a,b)=>b[1]-a[1]),k=>L.tracks[k]?.[0]||k,'track'),
 distBlock('语言',cnt('lang'),k=>L.lang[k],'lang'),
 distBlock('长度档',cnt('prompt_bucket'),k=>L.bucket[k],'bucket'),
 distBlock('Prompt 状态',cnt('prompt_status'),k=>L.status[k],'prompt_status'),
 distBlock('证据级别',cnt('evidence')),
].join('');
/* 分类页 → 总表联动 */
function gotoFilter(kind,val){
  document.querySelector('.tab[data-v="v1"]').click();
  active.clear(); document.querySelectorAll('#trackChips .chip').forEach(c=>c.classList.remove('on'));
  ['fPrimary','fTech','fSource','fMeta','fLang','fBucket'].forEach(id=>$('#'+id).value='');
  $('#q').value='';
  if(kind==='track'){active.add(val);const c=document.querySelector(`#trackChips .chip[data-t="${val}"]`);if(c)c.classList.add('on');}
  else if(kind==='primary') $('#fPrimary').value=val;
  else if(kind==='tech') $('#fTech').value=val;
  else if(kind==='lang') $('#fLang').value=val;
  else if(kind==='bucket') $('#fBucket').value=val;
  else if(kind==='source_group') $('#fSource').value=val;
  else if(kind==='meta_test') $('#fMeta').value=val;
  else if(kind==='prompt_status') $('#q').value = L.status[val]||val;
  else if(kind==='model_label')  $('#q').value = val;
  render();
  window.scrollTo({top:0,behavior:'smooth'});
}
document.addEventListener('click',e=>{
  const el=e.target.closest('.pick'); if(!el)return;
  gotoFilter(el.dataset.kind, el.dataset.val);
});

$('#combo').innerHTML=[
 distBlock('每题命中赛道数',cnt('track_count').sort((a,b)=>a[0]-b[0])),
 distBlock('每题技术标签数',(()=>{const c={};R.forEach(r=>c[r.tech.length]=(c[r.tech.length]||0)+1);return Object.entries(c).sort((a,b)=>a[0]-b[0])})()),
 distBlock('L1 断言数',cnt('assertion_count').sort((a,b)=>a[0]-b[0])),
].join('');
</script></body></html>"""
    p = DOCS / "task-catalog.html"
    p.write_text(tpl.replace("__PAYLOAD__", payload), encoding="utf-8")
    print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size/1024:.0f} KB, self-contained)")


def main() -> None:
    if not DOCS.is_dir():
        DOCS.mkdir()
    rows = load()
    assert len(rows) == 111, f"expected 111 tasks, got {len(rows)}"
    tax = build_taxonomy(rows)
    (TASKS / "taxonomy.json").write_text(
        json.dumps(tax, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  tasks/taxonomy.json  ({len(rows)} labelled)")
    write_csv(rows)
    write_md(rows, tax)
    write_html(rows, tax)
    print("\nSummary:")
    print("  tracks :", dict(Counter(t for r in rows for t in r["tracks"]).most_common()))
    print("  primary:", dict(Counter(r["primary"] for r in rows).most_common()))
    print("  lang   :", dict(Counter(r["lang"] for r in rows)))
    print("  meta   :", dict(Counter(r["meta_test"] for r in rows)))


if __name__ == "__main__":
    main()
