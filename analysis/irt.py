#!/usr/bin/env python3
"""Item Response Theory (2PL) calibration for task selection (paper §4.1 S6).

The final leaderboard size is decided by data, not promised in advance:
after the pilot run, fit a two-parameter logistic model and remove tasks with
discrimination a < 0.5 or extreme difficulty. The remaining 80–95 tasks are
what the paper reports.

Pure-stdlib gradient ascent is provided so the interface is testable without
scipy; `pip install -r requirements.txt` enables a higher-precision fit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass
class ItemParameters:
    task_id: str
    a: float  # discrimination
    b: float  # difficulty
    p_correct: float

    def keep(self, min_a: float = 0.5, max_abs_b: float = 3.0) -> bool:
        return self.a >= min_a and abs(self.b) <= max_abs_b


def probability(theta: float, a: float, b: float) -> float:
    return 1.0 / (1.0 + math.exp(-1.7 * a * (theta - b)))


def fit_item(task_id: str, responses: Iterable[tuple[float, int]],
             iterations: int = 400, lr: float = 0.05) -> ItemParameters:
    """Fit (a, b) for one task given (ability, binary outcome) pairs."""
    data = list(responses)
    if not data:
        raise ValueError("no responses")
    a, b = 1.0, 0.0
    for _ in range(iterations):
        ga = gb = 0.0
        for theta, y in data:
            p = probability(theta, a, b)
            err = y - p
            common = 1.7 * err * p * (1 - p)
            ga += common * (theta - b)
            gb += common * (-a)
        a = max(0.05, min(4.0, a + lr * ga / len(data)))
        b = max(-4.0, min(4.0, b + lr * gb / len(data)))
    mean_p = sum(probability(t, a, b) for t, _ in data) / len(data)
    return ItemParameters(task_id=task_id, a=round(a, 4), b=round(b, 4),
                          p_correct=round(mean_p, 4))


def calibrate(response_matrix: dict[str, list[tuple[float, int]]],
              min_a: float = 0.5) -> dict:
    """Return kept / removed task IDs plus the difficulty distribution."""
    fitted = [fit_item(tid, rows) for tid, rows in response_matrix.items()]
    kept = [p for p in fitted if p.keep(min_a=min_a)]
    removed = [p for p in fitted if not p.keep(min_a=min_a)]
    bs = sorted(p.b for p in fitted)
    return {
        "total": len(fitted),
        "kept": len(kept),
        "removed": len(removed),
        "removed_ids": [p.task_id for p in removed],
        "difficulty_quartiles": [bs[0], bs[len(bs) // 4], bs[len(bs) // 2],
                                 bs[3 * len(bs) // 4], bs[-1]] if bs else [],
        "items": [{"task_id": p.task_id, "a": p.a, "b": p.b} for p in fitted],
    }


def discrimination_report(response_matrix: dict[str, list[int]]) -> dict:
    """Sanity check: an item answered identically by everyone carries no info."""
    flat = [t for rows in response_matrix.values() for t in rows if len(set(rows)) == 1]
    return {"uninformative_items": len(flat), "note":
            "all-pass or all-fail tasks should be removed before reporting the leaderboard"}


if __name__ == "__main__":
    # Demonstration with synthetic abilities; real input comes from results/.
    demo = {f"task-{i:03d}": [(0.0, i % 2), (1.0, 1), (-1.0, 0)] for i in range(10)}
    print(calibrate(demo)["kept"], "of", len(demo), "items retained")
