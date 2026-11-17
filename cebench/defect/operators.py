"""D1–D6 parameterized defect injection (paper §2.3, M2/M3 substrate).

WorldBench used mutation testing to *validate a judge*. We turn the same knife
around and use it to *measure a model*: known defects are injected into a
reference implementation, so ground truth is exact, difficulty is controllable
(1–5 injected defects), and generation ability cannot substitute for
verification ability because the artifact under review was not written by the
model being tested.

Every operator must be registered in taxonomy.md with a source of evidence.
An operator invented without a real failure case is not a contribution claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import DEFECT_CLASSES


@dataclass
class MutationResult:
    defect_id: str
    applied: bool
    description: str
    ground_truth: dict[str, Any] = field(default_factory=dict)
    source: str = ""


def _replace(pattern: str, repl: str, source: str, *, count: int = 1,
             flags: int = re.I | re.S) -> tuple[str, bool]:
    new, n = re.subn(pattern, repl, source, count=count, flags=flags)
    return new, n > 0


def d1_remove_feature(source: str, config: dict[str, Any]) -> MutationResult:
    """Remove one interactive control (a real, commonly reported failure)."""
    label = config.get("label", "button")
    pattern = config.get("pattern", r"<button[^>]*>.*?</button>")
    new, ok = _replace(pattern, "", source)
    return MutationResult("D1", ok, f"removed interactive control: {label}",
                          {"missing_feature": label, "l0_rule": None}, new)


def d2_external_dependency(source: str, config: dict[str, Any]) -> MutationResult:
    """Introduce a CDN dependency, breaking the single-file contract."""
    url = config.get("url", "https://cdn.jsdelivr.net/npm/lib@1.0.0/lib.min.js")
    tag = f'<script src="{url}"></script>'
    new, ok = _replace(r"</head>", tag + "\n</head>", source)
    if not ok:
        new, ok = tag + source, True
    return MutationResult("D2", ok, "injected external CDN script (violates L0-01)",
                          {"external_url": url, "l0_rule": "L0-01"}, new)


def d3_timer_instead_of_raf(source: str, config: dict[str, Any]) -> MutationResult:
    """Replace every rAF call with a timer — animation still declared, wrong mechanism."""
    new, ok = _replace(r"requestAnimationFrame", "setTimeout", source, count=0, flags=re.I)
    return MutationResult("D3", ok, "replaced requestAnimationFrame with setTimeout",
                          {"broken_mechanism": "animation_loop", "l0_rule": "L0-05"}, new)


def d4_remove_reduced_motion(source: str, config: dict[str, Any]) -> MutationResult:
    """Strip the reduced-motion branch (accessibility regression)."""
    new, ok = _replace(r"[^\n;{}]*prefers-reduced-motion[^\n;{}]*[;{}]?", "", source, count=0)
    return MutationResult("D4", ok, "removed prefers-reduced-motion handling",
                          {"broken_mechanism": "accessibility", "l0_rule": "L0-06"}, new)


def d5_audio_autostart(source: str, config: dict[str, Any]) -> MutationResult:
    """Start an AudioContext outside any user gesture (autoplay violation)."""
    snippet = "<script>const __ce_ac = new AudioContext().resume();</script>"
    new, ok = _replace(r"</body>", snippet + "\n</body>", source)
    if not ok:
        new, ok = source + snippet, True
    return MutationResult("D5", ok, "added ungated AudioContext start (violates L0-08)",
                          {"broken_mechanism": "audio_gesture", "l0_rule": "L0-08"}, new)


def d6_static_fake_3d(source: str, config: dict[str, Any]) -> MutationResult:
    """Replace a real canvas surface with a flat image (forbidden shortcut)."""
    placeholder = ('<img alt="static scene" src="data:image/svg+xml,'
                   '%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27600%27 '
                   'height=%27400%27%3E%3C/svg%3E" />')
    new, ok = _replace(r"<canvas\b[^>]*>.*?</canvas>", placeholder, source)
    return MutationResult("D6", ok, "replaced live canvas with a static image (specification gaming)",
                          {"broken_mechanism": "real_geometry", "l0_rule": None,
                           "gate_rule": "forbidden_shortcut"}, new)


OPERATORS: dict[str, Callable[[str, dict[str, Any]], MutationResult]] = {
    "D1": d1_remove_feature,
    "D2": d2_external_dependency,
    "D3": d3_timer_instead_of_raf,
    "D4": d4_remove_reduced_motion,
    "D5": d5_audio_autostart,
    "D6": d6_static_fake_3d,
}


def apply_mutations(source: str, configs: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Apply a list of defect configs; return mutated source + exact ground truth.

    `configs` items look like {"class": "D2", "url": "..."}. Unknown classes are
    ignored rather than silently producing an unregistered defect.
    """
    current = source
    records: list[dict[str, Any]] = []
    for i, cfg in enumerate(configs):
        cls = cfg.get("class", "")
        if cls not in OPERATORS or cls not in DEFECT_CLASSES:
            continue
        result = OPERATORS[cls](current, cfg)
        if result.applied:
            current = result.source
        records.append({
            "index": i,
            "defect_id": result.defect_id,
            "applied": result.applied,
            "description": result.description,
            **result.ground_truth,
        })
    return current, records


def difficulty_level(records: list[dict[str, Any]]) -> int:
    """Number of *applied* defects = the IRT difficulty ladder for M2."""
    return sum(1 for r in records if r["applied"])
