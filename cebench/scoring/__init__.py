"""Gate (veto) -> Rubric (F/R/V/E + Cap) -> Aggregation (four numbers)."""

from .aggregate import leaderboard_columns, score_run, RunScore
from .gate import GateResult, evaluate_gate
from .rubric import (QualityScore, assert_verifiability_budget, cap_for,
                     deterministic_mass, dimension_scores, quality)

__all__ = [
    "evaluate_gate", "GateResult", "quality", "QualityScore", "cap_for",
    "dimension_scores", "deterministic_mass", "assert_verifiability_budget",
    "score_run", "RunScore", "leaderboard_columns",
]
