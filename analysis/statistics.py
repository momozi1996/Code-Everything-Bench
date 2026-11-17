#!/usr/bin/env python3
"""Uncertainty, paired comparisons and multiple-comparison control.

Journal requirement: report bootstrap 95% CIs, paired tests, effect sizes
(Cliff's delta) and Holm correction. Reporting means without intervals is not
acceptable for a benchmark paper. Pure-stdlib implementations keep the
interface runnable on a fresh clone.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence


def bootstrap_ci(values: Sequence[float], *, stat: Callable[[Sequence[float]], float] | None = None,
                 n_boot: int = 2000, alpha: float = 0.05, seed: int = 2027) -> tuple[float, float]:
    if not values:
        raise ValueError("empty sample")
    rng = random.Random(seed)
    agg = stat or (lambda xs: sum(xs) / len(xs))
    estimates = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        estimates.append(agg(sample))
    estimates.sort()
    lo = estimates[int((alpha / 2) * n_boot)]
    hi = estimates[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return round(lo, 4), round(hi, 4)


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Non-parametric effect size; |δ| < 0.147 negligible, > 0.474 large."""
    gt = lt = 0
    for x in a:
        for y in b:
            gt += x > y
            lt += x < y
    return round((gt - lt) / (len(a) * len(b)), 4)


def permutation_pvalue(a: Sequence[float], b: Sequence[float],
                       n_perm: int = 5000, seed: int = 2027) -> float:
    """Paired-ish two-sample permutation test on the difference of means."""
    rng = random.Random(seed)
    obs = abs(sum(a) / len(a) - sum(b) / len(b))
    pool = list(a) + list(b)
    extreme = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        x, y = pool[:len(a)], pool[len(a):]
        if abs(sum(x) / len(x) - sum(y) / len(y)) >= obs:
            extreme += 1
    return round((extreme + 1) / (n_perm + 1), 4)


def holm_correction(pvalues: Sequence[float], alpha: float = 0.05) -> list[bool]:
    """Return the reject decisions in the original order."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    m = len(pvalues)
    rejected = [False] * m
    for rank, i in enumerate(order):
        if pvalues[i] <= alpha / (m - rank):
            rejected[i] = True
        else:
            break
    return rejected


def significance_groups(means: dict[str, float], pvalue_matrix: dict[tuple[str, str], float],
                        alpha: float = 0.05) -> dict[str, str]:
    """Assign letters (a/b/c) so non-significant configurations share a group.

    The leaderboard sorts by these groups, never by raw point differences.
    This prevents a 1.7-point gap being rendered as a ranking.
    """
    names = sorted(means, key=lambda k: -means[k])
    groups: dict[str, str] = {}
    letter = 0
    for name in names:
        if name in groups:
            continue
        label = chr(ord("a") + letter)
        for other in names:
            if other in groups:
                continue
            key = tuple(sorted((name, other)))
            p = pvalue_matrix.get(key, 0.0)
            if name == other or p >= alpha:
                groups[other] = label
        letter += 1
    return groups


if __name__ == "__main__":
    a, b = [0.8, 0.7, 0.9, 0.75], [0.5, 0.55, 0.6, 0.45]
    print("CI(A):", bootstrap_ci(a), "delta:", cliffs_delta(a, b),
          "p:", permutation_pvalue(a, b, n_perm=1000))
    print("Holm:", holm_correction([0.001, 0.02, 0.04, 0.6]))
