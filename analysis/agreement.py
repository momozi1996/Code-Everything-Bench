#!/usr/bin/env python3
"""Inter-rater agreement and calibration (paper §2.7, RQ5, §8.2).

Thresholds are part of the protocol, not preferences:
    human vs deterministic assertions   Cohen's κ >= 0.90
    human vs LLM judge                  Cohen's κ >= 0.70  (else judge may not score)
    three reviewers                     Fleiss' κ  >= 0.60 (task admission)
    judge on known-defect calibration   accuracy    >= 0.85 (judge activation)

A κ below the assertion threshold is treated as a *bug in the assertion*, not
as human error — the deterministic suite is the thing under test there.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence


def cohen_kappa(a: Sequence, b: Sequence) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("paired, non-empty ratings required")
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum((ca[k] / n) * (cb[k] / n) for k in labels)
    return round((observed - expected) / (1 - expected), 4) if expected < 1 else 1.0


def fleiss_kappa(matrix: Sequence[Sequence]) -> float:
    """Rows = items, columns = category counts across raters."""
    if not matrix:
        raise ValueError("empty matrix")
    n_items = len(matrix)
    n_raters = sum(matrix[0])
    if any(sum(row) != n_raters for row in matrix):
        raise ValueError("every item must have the same number of ratings")
    p_j = [sum(row[j] for row in matrix) / (n_items * n_raters)
           for j in range(len(matrix[0]))]
    p_i = [((sum(x * x for x in row)) - n_raters) / (n_raters * (n_raters - 1))
           for row in matrix]
    p_bar = sum(p_i) / n_items
    p_e = sum(p * p for p in p_j)
    return round((p_bar - p_e) / (1 - p_e), 4) if p_e < 1 else 1.0


def expected_calibration_error(predicted: Iterable[float], actual: Iterable[float],
                               bins: int = 10) -> float:
    """ECE for RQ5a: |self-assessed completion - assertion pass rate|."""
    pairs = list(zip(predicted, actual))
    if not pairs:
        raise ValueError("no predictions")
    buckets: list[list[float]] = [[] for _ in range(bins)]
    for p, y in pairs:
        idx = min(bins - 1, max(0, int(float(p) * bins)))
        buckets[idx].append(abs(float(p) - float(y)))
    total = sum(len(b) for b in buckets)
    return round(sum(sum(b) for b in buckets) / total, 4)


def topk_hit_rate(predicted_weak: Sequence[Sequence[str]],
                  actual_failed: Sequence[Sequence[str]], k: int = 3) -> float:
    """RQ5b: does a model know *where* it is weak? Compare to a random baseline."""
    if not predicted_weak:
        raise ValueError("no predictions")
    hits = sum(len(set(list(p)[:k]) & set(a)) / max(1, len(set(a)))
               for p, a in zip(predicted_weak, actual_failed))
    return round(hits / len(predicted_weak), 4)


def judge_stability(scores: Sequence[float]) -> dict:
    """Fixed evidence, K re-runs (paper §8.2, GameCraft σ=0.0037 analogue)."""
    n = len(scores)
    mean = sum(scores) / n
    var = sum((x - mean) ** 2 for x in scores) / n
    return {"k": n, "mean": round(mean, 4), "sd": round(var ** 0.5, 4),
            "threshold_sd": 0.02}


if __name__ == "__main__":
    print("Cohen kappa:", cohen_kappa([1, 1, 0, 0, 1], [1, 0, 0, 0, 1]))
    print("Fleiss kappa:", fleiss_kappa([[3, 0, 0], [0, 3, 0], [2, 1, 0]]))
    print("ECE:", expected_calibration_error([0.9, 0.5, 0.2], [0.8, 0.5, 0.4]))
