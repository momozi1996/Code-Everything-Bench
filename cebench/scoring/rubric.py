"""F / R / V / E rubric and the Cap rule (paper §5.5–§5.6).

    F  Functional      deterministic  (L0 + L1 assertions, state probes)
    R  Requirement     deterministic  (structured requirement checklist)
    V  Visual          judge-assisted (interaction recording + closed questions)
    E  Engineering     deterministic  (performance, responsive, stability)

Deterministic weight = F 0.35 + R 0.30 + E 0.15 = 0.80. This is not a policy
statement but a property of the scoring formula, which makes the
"verifiability budget" unfalsifiable-by-omission: a task whose deterministic
mass falls below the threshold cannot be admitted to CE-Frozen.

Cap is applied only to *passing* runs. It compresses quality among delivered
artifacts without contaminating the binary main metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..config import (CAP_CORE_INTERACTION_FAIL, CAP_DEFAULT,
                      DETERMINISTIC_DIMENSIONS, DETERMINISTIC_WEIGHT_MIN,
                      WEIGHTS)
from ..assertions.base import AssertionResult, FAIL, PASS, summarize

DIMENSIONS = ("F", "R", "V", "E")


def dimension_scores(results: Iterable[AssertionResult]) -> dict[str, float | None]:
    """Weighted pass rate per dimension; None when a dimension has no evidence."""
    rs = list(results)
    out: dict[str, float | None] = {}
    for dim in DIMENSIONS:
        subset = [r for r in rs if r.dimension == dim and r.status in (PASS, FAIL)]
        if not subset:
            out[dim] = None
            continue
        num = sum(r.weight for r in subset if r.status == PASS)
        den = sum(r.weight for r in subset)
        out[dim] = num / den if den else None
    return out


def deterministic_mass() -> float:
    return sum(WEIGHTS[d] for d in DETERMINISTIC_DIMENSIONS)


@dataclass
class QualityScore:
    dimensions: dict[str, float | None]
    weighted: float
    cap: float
    final: float
    effective_assertions: int
    pass_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {"dimensions": self.dimensions, "weighted": self.weighted,
                "cap": self.cap, "final": self.final,
                "effective_assertions": self.effective_assertions,
                "pass_rate": self.pass_rate}


def quality(results: Iterable[AssertionResult], *, cap: float = CAP_DEFAULT) -> QualityScore:
    rs = list(results)
    dims = dimension_scores(rs)
    # A dimension with no evidence is excluded and the remaining weights are
    # renormalised, so absent evidence never silently counts as a perfect score.
    active = {d: v for d, v in dims.items() if v is not None}
    total_w = sum(WEIGHTS[d] for d in active)
    weighted = (sum(WEIGHTS[d] * float(v) for d, v in active.items()) / total_w
                if total_w else 0.0)
    s = summarize(rs)
    return QualityScore(
        dimensions=dims,
        weighted=weighted,
        cap=cap,
        final=min(weighted, cap),
        effective_assertions=s["effective_assertions"],
        pass_rate=s["pass_rate"],
    )


def cap_for(observation: dict[str, Any]) -> float:
    return (CAP_CORE_INTERACTION_FAIL
            if observation.get("core_interaction_degraded", False) else CAP_DEFAULT)


def assert_verifiability_budget() -> bool:
    """CI guard: the deterministic mass must never drop below the threshold."""
    return deterministic_mass() >= DETERMINISTIC_WEIGHT_MIN
