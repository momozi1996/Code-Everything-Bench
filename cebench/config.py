"""Single source of truth for the benchmark contract.

Every constant here has a counterpart in the paper (§3 formulation, §5 scoring).
Changing a weight, a Gate rule or an L0 rule without updating the manuscript is
a protocol violation; CI checks the two stay in sync via `cebench.cli selftest`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
CORPUS_COMMIT = "v556ab07"  # pinned snapshot of momozi1996/Code-Everything

# --- L0: eight global assertions, shared by every task in the bank ----------
L0_IDS = (
    "L0-01",  # single file / no external resources
    "L0-02",  # doctype + viewport meta
    "L0-03",  # no console/page errors under file://        (browser)
    "L0-04",  # no horizontal overflow at 360px              (browser)
    "L0-05",  # animation uses requestAnimationFrame
    "L0-06",  # prefers-reduced-motion honoured
    "L0-07",  # pointer + keyboard parity
    "L0-08",  # Web Audio starts only after a user gesture
)
BROWSER_ONLY = {"L0-03", "L0-04"}

# --- Gate: multiplicative veto, five rules --------------------------------
# Semantics (v0.6, see docs/benchmark-spec.md §6 and docs/assertion-review.md):
#   [0] artifact_does_not_load     — the deliverable is not a complete, loadable
#       HTML document (missing </html>/</body> closing tag, or the pinned
#       browser could not open it). A token-truncated artifact lands here, not
#       under [1]: its root cause is an incomplete deliverable.
#   [1] core_interaction_unusable  — the *runtime* interaction probes
#       (interaction_delta / selector_exists L1 assertions) produced no PASS at
#       all. Static source_contains/source_absent failures are NOT Gate
#       evidence: they are requirement signals and belong in F/R/E. Binding
#       them to a veto made every strict regex a zero-score switch (design-
#       decisions #19 corrected).
#   [2] unverified_claims          — claimed checks with no trace evidence
#   [3] forbidden_shortcut         — e.g. static image posing as real 3D
#   [4] no_deliverable_file        — nothing was delivered
GATE_RULES = (
    "artifact_does_not_load",
    "core_interaction_unusable",
    "unverified_claims",
    "forbidden_shortcut",
    "no_deliverable_file",
)

# --- Rubric: F / R / V / E, deterministic weight = 0.80 --------------------
WEIGHTS = {"F": 0.35, "R": 0.30, "V": 0.20, "E": 0.15}
DETERMINISTIC_DIMENSIONS = ("F", "R", "E")
DETERMINISTIC_WEIGHT_MIN = 0.75
CAP_DEFAULT = 1.0
# Revived in v0.6: a run whose runtime probes are *partly* failing is usable but
# degraded — it passes the Gate yet its quality is capped. An all-failing probe
# set is a Gate veto, not a Cap. This is the distinction design-decisions #19
# lost when it moved the rule from Cap to Gate.
CAP_CORE_INTERACTION_FAIL = 0.5

# Single output cap for every target configuration and every run plan. A target
# max_tokens below this is a truncation risk: CE-Bench artifacts are 12–35 KB of
# inline HTML/CSS/JS and reasoning models additionally spend hidden tokens on
# reasoning. Providers fall back to this value when a model entry omits params.
#
# v0.7: raised 96k -> 512k. Cost is deliberately not a constraint for the
# full 180-task batch; the priority is that every task can deliver a complete
# single-file artifact. This is a *cap*, not a target — the model may stop
# much earlier. It must stay equal to `budget.max_output_tokens` in every run
# plan and to `params.max_tokens` on every target (tests/test_providers.py
# enforces this across all shipped configs).
TARGET_MAX_TOKENS = 512000
TARGET_MAX_TOKENS_RECOMMENDED_MIN = 512000

DEFAULT_BUDGET = {
    "wall_clock_minutes": 120,
    "max_repair_rounds": 15,
    "max_output_tokens": TARGET_MAX_TOKENS,
    "network": "deny",
}

# --- Defect taxonomy (paper §2.3) -----------------------------------------
DEFECT_CLASSES = ("D1", "D2", "D3", "D4", "D5", "D6")

# --- Tracks ---------------------------------------------------------------
TRACKS = ("CE-Frozen", "CE-Live", "CE-Hidden")
MODES = ("Replay", "Rebuild", "Transfer")


def load_config(path: str | Path) -> dict[str, Any]:
    """Load JSON, or a YAML subset, or full YAML when PyYAML is available.

    Task packs in this repository use JSON so that a fresh clone needs no
    dependencies. The paper's `*.yaml` specs are equivalent; both are accepted.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _yaml_subset(text)


def _yaml_subset(text: str) -> dict[str, Any]:
    """Tiny YAML subset: scalar keys, nested one-level maps, simple lists.

    Sufficient for the task packs shipped here; PyYAML is used when installed.
    """
    out: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        if body.startswith("- "):
            if current is None:
                raise ValueError("list item outside a mapping")
            current.setdefault("_list", []).append(_scalar(body[2:]))
            continue
        if ":" not in body:
            continue
        key, _, value = body.partition(":")
        key, value = key.strip(), value.strip()
        if indent == 0:
            if value:
                out[key] = _scalar(value)
                current = None
            else:
                out[key] = {}
                current = out[key]
        elif current is not None:
            current[key] = _scalar(value)
    for v in out.values():
        if isinstance(v, dict) and "_list" in v:
            items = v.pop("_list")
            v["items"] = items
    return out


def _scalar(value: str) -> Any:
    v = value.strip().strip('"').strip("'")
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", "~"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v
