"""Assertion primitives shared by L0 (global), L1 (task-specific), L2 (visual).

Four statuses, not two. SKIP means "could not run" and NA means "not applicable":
neither may be silently converted into PASS. The denominator of every task score
is the number of *effective* assertions (PASS + FAIL); NA and SKIP are excluded
and reported separately, otherwise tasks with different assertion counts would
be implicitly weighted differently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
NA = "NA"

TIER_L0 = "L0"
TIER_L1 = "L1"
TIER_L2 = "L2"


@dataclass
class AssertionResult:
    id: str
    name: str
    tier: str
    status: str
    evidence: str = ""
    dimension: str = "F"  # F / R / V / E — used by the rubric
    weight: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        # `meta` carries the assertion kind so the scorer can tell a runtime
        # interaction probe from a static source regex. Gate semantics depend
        # on this distinction; see docs/assertion-review.md.
        return {
            "id": self.id, "name": self.name, "tier": self.tier,
            "status": self.status, "evidence": self.evidence,
            "dimension": self.dimension, "weight": self.weight,
            "meta": self.meta,
        }

    @property
    def effective(self) -> bool:
        return self.status in (PASS, FAIL)


@dataclass
class Assertion:
    id: str
    name: str
    tier: str
    check: Callable[..., AssertionResult]
    dimension: str = "F"
    weight: float = 1.0


def make_result(assertion_id: str, name: str, status: str, evidence: str,
                *, tier: str = TIER_L0, dimension: str = "F",
                meta: dict[str, Any] | None = None) -> AssertionResult:
    return AssertionResult(id=assertion_id, name=name, tier=tier,
                           status=status, evidence=evidence, dimension=dimension,
                           meta=meta or {})


def summarize(results: Iterable[AssertionResult]) -> dict[str, Any]:
    """Aggregate outcomes with an explicit effective-assertion denominator."""
    rs = list(results)
    passed = sum(1 for r in rs if r.status == PASS)
    failed = sum(1 for r in rs if r.status == FAIL)
    skipped = sum(1 for r in rs if r.status == SKIP)
    na = sum(1 for r in rs if r.status == NA)
    effective = passed + failed
    return {
        "total": len(rs),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "na": na,
        "effective_assertions": effective,
        "pass_rate": (passed / effective) if effective else None,
        "all_effective_passed": effective > 0 and failed == 0,
        # A benchmark must never report a clean run while checks were skipped.
        "coverage_complete": skipped == 0,
    }
