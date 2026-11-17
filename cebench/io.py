"""Filesystem helpers. All result files are JSON/CSV so results stay portable."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .config import ROOT


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    return p


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def task_dirs(root: str | Path | None = None) -> list[Path]:
    base = Path(root) if root else ROOT / "tasks"
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / "task.json").exists())


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})
    return p


def result_path(run_id: str, filename: str) -> Path:
    return ROOT / "results" / run_id / filename
