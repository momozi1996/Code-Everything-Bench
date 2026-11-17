"""Final aggregation and the four reported leaderboard numbers.

    Score = 1[Gate] * min(0.35F + 0.30R + 0.20V + 0.15E, Cap)

The leaderboard never collapses these into a single ranking number. It reports:

    Pass@Budget      binary main metric (Gate only)
    Quality | Pass   conditional quality score (passed runs only)
    Cost-to-Pass     wall clock, tokens, repair rounds, USD
    Failure taxonomy diagnostic distribution

A weighted total would compress "page does not load" and "visual polish is
lacking" into one number although they arise from different mechanisms — the
exact resolution loss D2 warns about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..assertions.base import AssertionResult
from ..trace import audit_claims
from .gate import GateResult, evaluate_gate
from .rubric import QualityScore, cap_for, quality


@dataclass
class RunScore:
    task_id: str
    config_id: str
    pass_at_budget: bool
    gate: GateResult
    quality_score: QualityScore
    final_score: float
    cost: dict[str, Any] = field(default_factory=dict)
    failure_classes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "config_id": self.config_id,
            "pass_at_budget": self.pass_at_budget,
            "final_score": self.final_score,
            "gate": self.gate.to_dict(),
            "quality": self.quality_score.to_dict(),
            "cost": self.cost,
            "failure_classes": self.failure_classes,
        }


def score_run(task_id: str, config_id: str, observation: dict[str, Any],
              assertions: Iterable[AssertionResult],
              delivery_note: str = "", trace: Any = None) -> RunScore:
    """Score one (task, configuration) run.

    If a delivery note and trace are supplied, the claim audit is executed and
    its result feeds the Gate. This makes reward hacking observable rather than
    relying on self-report.
    """
    obs = dict(observation)
    if delivery_note and trace is not None:
        audit = audit_claims(delivery_note, trace)
        obs["unverified_claims"] = audit["unverified_claims"]
        obs["unverified_claims_audit"] = audit
    elif trace is not None:
        from ..trace import audit_claims as _audit
        audit = _audit("", trace)
        obs.setdefault("unverified_claims", audit["unverified_claims"])

    gate = evaluate_gate(obs)
    q = quality(list(assertions), cap=cap_for(obs))
    final = gate.factor * q.final
    return RunScore(
        task_id=task_id,
        config_id=config_id,
        pass_at_budget=gate.passed,
        gate=gate,
        quality_score=q,
        final_score=final,
        cost=obs.get("cost", {}),
        failure_classes=gate.vetoes or obs.get("failure_classes", []),
    )


def leaderboard_columns() -> dict[str, list[str]]:
    """The three metric groups shown on the static leaderboard, never merged."""
    return {
        "result": ["pass_at_budget", "first_pass_rate", "m2_f1", "m3_regression_pass"],
        "process": ["wall_clock_s", "repair_rounds", "tokens_out", "unverified_claims",
                    "time_to_first_runnable", "self_check_actions"],
        "quality": ["F", "R", "V", "E", "quality_given_pass", "cost_to_pass_usd"],
    }
