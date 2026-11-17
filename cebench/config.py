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

# --- L0: eight global assertions, shared by all 111 tasks -------------------
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
GATE_RULES = (
    "artifact_does_not_load",
    "core_interaction_unusable",
    "unverified_claims",          # claimed checks with no trace evidence
    "forbidden_shortcut",         # e.g. static image posing as real 3D
    "no_deliverable_file",
)

# --- Rubric: F / R / V / E, deterministic weight = 0.80 --------------------
WEIGHTS = {"F": 0.35, "R": 0.30, "V": 0.20, "E": 0.15}
DETERMINISTIC_DIMENSIONS = ("F", "R", "E")
DETERMINISTIC_WEIGHT_MIN = 0.75
CAP_DEFAULT = 1.0
CAP_CORE_INTERACTION_FAIL = 0.5

DEFAULT_BUDGET = {
    "wall_clock_minutes": 30,
    "max_repair_rounds": 15,
    "max_output_tokens": 60000,
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
