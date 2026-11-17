#!/usr/bin/env python3
"""Pull the pinned case-library snapshot and rebuild the task manifest.

Single source of truth: this repository vendors NO prompt text. It stores only
derived metadata plus a URL back to the case library.

    python3 scripts/sync_corpus.py --ref v556ab07

For a published run, `--ref` MUST be a commit hash (not `main`), so that the
corpus snapshot is immutable and the arXiv version is reproducible.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/momozi1996/Code-Everything/{ref}/data/cases.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="main",
                    help="commit hash for published runs; 'main' for development")
    ap.add_argument("--out", default=str(ROOT / "data" / "corpus" / "cases.jsonl"))
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    url = RAW.format(ref=args.ref)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"ERROR: could not fetch corpus: {exc}")
        return 2
    dest.write_bytes(data)
    print(f"wrote {dest} ({len(data):,} bytes, {data.count(b'\n'):,} lines)")

    if not args.no_build:
        from build_manifest import load_rows, build  # type: ignore
        import json
        m = build(load_rows(dest))
        (ROOT / "tasks" / "manifest.json").write_text(
            json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"manifest rebuilt: {m['task_count']} tasks")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main())
