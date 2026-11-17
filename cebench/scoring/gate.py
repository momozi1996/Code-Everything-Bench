"""Gate — five multiplicative vetoes (paper §5.5).

A Gate failure sets Pass@Budget = 0 regardless of quality. Using a multiplier
rather than a scored dimension is what prevents "does not load" from being
compensated by high visual quality.

Historical note: the earlier draft put "core interaction unusable" only under a
quality Cap, which was self-contradictory — Pass@Budget would have stayed 1.
It is a Gate rule now (design-decisions #19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import GATE_RULES


@dataclass
class GateResult:
    passed: bool
    vetoes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def factor(self) -> float:
        return 1.0 if self.passed else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "factor": self.factor,
                "vetoes": self.vetoes, "evidence": self.evidence}


def evaluate_gate(observation: dict[str, Any]) -> GateResult:
    """Evaluate the five vetoes from a scored observation.

    Expected keys (all optional, defaults are conservative):
        loads, core_interaction_ok, unverified_claims, forbidden_shortcut,
        has_deliverable, budget_exceeded, unverified_claims_audit
    """
    vetoes: list[str] = []
    checks = {
        GATE_RULES[0]: observation.get("loads", False) is True,
        GATE_RULES[1]: observation.get("core_interaction_ok", False) is True,
        GATE_RULES[2]: int(observation.get("unverified_claims", 0)) == 0,
        GATE_RULES[3]: observation.get("forbidden_shortcut", False) is False,
        GATE_RULES[4]: observation.get("has_deliverable", False) is True,
    }
    for rule, ok in checks.items():
        if not ok:
            vetoes.append(rule)
    return GateResult(
        passed=not vetoes,
        vetoes=vetoes,
        evidence={
            "checks": checks,
            "unverified_claims": int(observation.get("unverified_claims", 0)),
            "budget_exceeded": bool(observation.get("budget_exceeded", False)),
            "claim_audit": observation.get("unverified_claims_audit", {}),
        },
    )
