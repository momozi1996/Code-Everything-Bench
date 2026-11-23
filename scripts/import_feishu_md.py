#!/usr/bin/env python3
"""Parse the Feishu-exported prompt collection markdown into structured records.

The source markdown is a continuously-updated collection of X/Twitter prompts
and demo artifacts. Feishu's export flattens every table cell onto one line,
uses ``<br>`` for in-cell newlines, backslash-escapes markdown punctuation,
and wraps verbatim prompts in fenced code blocks (```` ```Markdown ````).

Only rows whose Prompt column contains a fenced code block are admissible:
a benchmark task needs the *verbatim* prompt, not a paraphrase or a title.
Rows that merely list a demo, a screenshot, or a "prompt status" are skipped.

Outputs (all derived, nothing is vendored):
  * ``data/corpus/feishu_md_records.jsonl`` -- one record per admissible row
  * ``docs/feishu-import-report.md``        -- coverage + de-dup report

Usage:
    python3 scripts/import_feishu_md.py
    python3 scripts/import_feishu_md.py --source /path/to/export.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus" / "cases.jsonl"
OUT_JSONL = ROOT / "data" / "corpus" / "feishu_md_records.jsonl"
OUT_REPORT = ROOT / "docs" / "feishu-import-report.md"

DEFAULT_SOURCE = Path(
    "/Users/jyxc-dz-0100378/Downloads/"
    "Opus 5.5 和 gpt6 astra，gpt6.1 _6.2 sol ,fable5.5 ，gemini4,k3.1-pro 提示词（X）.md"
)

# |c1|c2|c3|c4|c5|  -- the first four columns are metadata and contain no
# literal pipes (URLs are pipe-free); everything after the 4th separator is the
# Prompt cell, which may legitimately contain pipes (markdown tables in prompts).
ROW_RE = re.compile(
    r"^\|(?P<c1>[^|]*)\|(?P<c2>.*?)\|(?P<c3>.*?)\|(?P<c4>.*?)\|(?P<c5>.*)\|\s*$"
)
SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")
HEADER_FIRST = {"序号", "#", "资源", ""}
FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
X_URL_RE = re.compile(r"https?://(?:x|twitter)\.com/[^\s)|<\]()]+/status/(\d+)")
HTML_URL_RE = re.compile(r"https?://[^\s)|<\\>\]()]+\.html")
MODEL_RE = re.compile(r"模型[：:]\s*([^<\\|\n]+)")
ESCAPED_PUNCT_RE = re.compile(r"\\([.\-_~>+#*\[\](){}|!`])")


def unescape(text: str) -> str:
    """Undo Feishu markdown export escaping and restore in-cell newlines."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return ESCAPED_PUNCT_RE.sub(r"\1", text)


def clean_title(text: str) -> str:
    text = unescape(text)
    # first meaningful line of the evidence cell is usually a bolded summary
    for line in text.split("\n"):
        line = re.sub(r"^[\s*>*-]+", "", line).strip()
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = line.replace("**", "").strip()
        if line and not line.lower().startswith("http"):
            return line[:120]
    return ""


def norm_hash(prompt: str) -> str:
    norm = re.sub(r"\s+", " ", prompt).strip()
    return hashlib.md5(norm.encode("utf-8")).hexdigest()


def parse(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lines = source.read_text(encoding="utf-8").split("\n")
    section = ""
    table_line = 0
    records: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "total_lines": len(lines),
        "table_rows": 0,
        "with_fence": 0,
        "skipped_no_fence": 0,
        "sections": Counter(),
        "tables": Counter(),
    }

    for lineno, raw in enumerate(lines, 1):
        if raw.startswith("#"):
            section = unescape(raw.strip()).lstrip("#").strip()
            continue
        if SEP_RE.match(raw):
            table_line = lineno
            continue
        if not raw.startswith("|"):
            continue
        m = ROW_RE.match(raw)
        if not m:
            continue
        c1 = unescape(m.group("c1")).strip()
        if c1 in HEADER_FIRST or set(c1) <= {"-", ":", " "}:
            continue
        stats["table_rows"] += 1

        c5 = m.group("c5")
        if "```" not in c5:
            stats["skipped_no_fence"] += 1
            continue
        stats["with_fence"] += 1

        cell = unescape(c5)
        fm = FENCE_RE.search(cell)
        prompt = (fm.group(1) if fm else "").strip()
        if not prompt:
            stats["skipped_no_fence"] += 1
            stats["with_fence"] -= 1
            continue

        c2, c3, c4 = m.group("c2"), m.group("c3"), m.group("c4")
        c3u, c4u = unescape(c3), unescape(c4)
        xu = X_URL_RE.search(c3u)
        htmls = HTML_URL_RE.findall(c4u)
        model = MODEL_RE.search(unescape(c2))
        seq = re.sub(r"[^A-Za-z0-9._-]+", "-", c1).strip("-") or "x"
        rid = f"md-{table_line}-{seq}"

        rec = {
            "id": rid,
            "line": lineno,
            "table_line": table_line,
            "section": section,
            "seq": c1,
            "source_author": clean_title(c2) if not model else "",
            "source_cell": unescape(c2)[:600],
            "model_raw": (model.group(1).strip() if model else ""),
            "source_post_url": (xu.group(0) if xu else ""),
            "source_post_id": (xu.group(1) if xu else ""),
            "demo_urls": list(dict.fromkeys(htmls)),
            "title": clean_title(c4u),
            "evidence": c4u[:600],
            "prompt": prompt,
            "prompt_chars": len(prompt),
            "prompt_hash": norm_hash(prompt),
        }
        records.append(rec)
        stats["sections"][section] += 1
        stats["tables"][table_line] += 1
    return records, stats


def corpus_hashes(path: Path) -> set[str]:
    out: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            p = r.get("prompt") or ""
            if p.strip():
                out.add(norm_hash(p))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = ap.parse_args()
    if not args.source.is_file():
        print(f"source markdown not found: {args.source}", file=sys.stderr)
        return 2

    records, stats = parse(args.source)
    known = corpus_hashes(CORPUS) if CORPUS.is_file() else set()
    seen: set[str] = set()
    new = 0
    for r in records:
        if r["prompt_hash"] in seen:
            r["status"] = "duplicate_within_md"
        elif r["prompt_hash"] in known:
            r["status"] = "already_in_corpus"
        else:
            r["status"] = "new"
            new += 1
        seen.add(r["prompt_hash"])

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_status = Counter(r["status"] for r in records)
    new_by_section = Counter(r["section"] for r in records if r["status"] == "new")
    new_with_html = sum(1 for r in records if r["status"] == "new" and r["demo_urls"])

    lines = [
        "# Feishu markdown import report",
        "",
        f"Source: `{args.source.name}` ({stats['total_lines']} lines).",
        "",
        "## Parsing",
        "",
        f"- Table rows scanned: **{stats['table_rows']}**",
        f"- Rows with a verbatim fenced Prompt: **{stats['with_fence']}**",
        f"- Rows skipped (demo/screenshot/title only, no verbatim prompt): **{stats['skipped_no_fence']}**",
        "",
        "A row is admissible only when its Prompt column contains a fenced code",
        "block. Title-only rows (B-class demos, the 9x28 'candidate pool' tables)",
        "are deliberately excluded: a paraphrase is not a runnable task prompt.",
        "",
        "## De-duplication against pinned corpus",
        "",
        f"- Distinct prompt hashes already in `data/corpus/cases.jsonl`: **{len(known)}**",
        f"- `already_in_corpus`: **{by_status.get('already_in_corpus', 0)}**",
        f"- `duplicate_within_md`: **{by_status.get('duplicate_within_md', 0)}**",
        f"- `new` (verbatim prompt not present in the corpus): **{new}**",
        f"- of those, with a runnable `.html` demo link: **{new_with_html}**",
        "",
        "### New prompts by section",
        "",
    ]
    for sec, n in new_by_section.most_common():
        lines.append(f"- {n}: {sec}")
    lines += [
        "",
        "## Output",
        "",
        f"- `{OUT_JSONL.relative_to(ROOT)}` — {len(records)} records with verbatim prompts.",
        "",
        "Downstream: `scripts/expand_tasks.py` uses the `new` records plus",
        "prompt-bearing corpus records that were dropped by the original",
        "`.html`-only funnel, and selects tasks by label scarcity.",
        "",
    ]
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"parsed rows={stats['table_rows']} fence={stats['with_fence']} "
          f"admissible={len(records)}")
    print(f"status: {dict(by_status)}")
    print(f"new prompts: {new} (with .html demo: {new_with_html})")
    print("new by section:")
    for sec, n in new_by_section.most_common(15):
        print(f"  {n:3d}  {sec[:90]}")
    print(f"\nwrote {OUT_JSONL}")
    print(f"wrote {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
