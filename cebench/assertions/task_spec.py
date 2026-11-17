"""L1 task-specific assertion loader.

Each task pack declares its assertions in `assertions/task.json`. Assertions are
compiled from the prompt's INTERACTION MODEL (paper §4.3). Supported kinds:

    source_contains      static: literal / regex must appear
    source_absent        static: literal / regex must not appear
    selector_exists      browser: element must exist
    interaction_delta    browser: an interaction must change runtime state
    visual_review        L2: routed to the multimodal judge, never auto-scored

A task is admitted to *full measurement* only when auto + state-probe
assertions total >= 8 (§4.1 S4). Otherwise it is marked M1-only and reported
separately — it must not be silently counted as a fully measured task.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import load_config
from .base import FAIL, NA, PASS, SKIP, AssertionResult, make_result, summarize

MIN_FULL_MEASUREMENT = 8

BROWSER_KINDS = {"selector_exists", "interaction_delta"}
VISUAL_KINDS = {"visual_review"}


def load_task_assertions(path: str) -> list[dict[str, Any]]:
    cfg = load_config(path)
    return list(cfg.get("assertions", []))


def classify(assertions: list[dict[str, Any]]) -> dict[str, Any]:
    auto = [a for a in assertions if a.get("kind") in
            ("source_contains", "source_absent", "interaction_delta", "selector_exists")]
    visual = [a for a in assertions if a.get("kind") in VISUAL_KINDS]
    static = [a for a in assertions if a.get("kind") in ("source_contains", "source_absent")]
    return {
        "total": len(assertions),
        "auto_assertable": len(auto),
        "state_probe": sum(1 for a in assertions if a.get("kind") == "interaction_delta"),
        "visual_only": len(visual),
        "static": len(static),
        "full_measurement": len(auto) >= MIN_FULL_MEASUREMENT,
        "track": "full" if len(auto) >= MIN_FULL_MEASUREMENT else "M1-only",
    }


def run_task_assertions(assertions: list[dict[str, Any]], source: str,
                        page: Any = None) -> list[AssertionResult]:
    """Evaluate L1 assertions. Static ones always run; browser ones SKIP
    honestly when no page is available."""
    out: list[AssertionResult] = []
    for spec in assertions:
        aid = spec.get("id", "L1-?")
        name = spec.get("name", aid)
        kind = spec.get("kind", "")
        dim = spec.get("dimension", "F")
        if kind in ("source_contains", "source_absent"):
            pattern = spec.get("pattern", "")
            found = bool(re.search(pattern, source, re.I | re.S)) if pattern else False
            ok = found if kind == "source_contains" else not found
            out.append(make_result(aid, name, PASS if ok else FAIL,
                                   f"pattern {pattern!r} {'found' if found else 'absent'}",
                                   tier="L1", dimension=dim))
        elif kind in BROWSER_KINDS:
            if page is None:
                out.append(make_result(aid, name, SKIP, "browser_unavailable: "
                                       "pinned Chromium page required", tier="L1", dimension=dim))
            else:
                ok = _browser_check(spec, page)
                out.append(make_result(aid, name, PASS if ok else FAIL,
                                       "browser interaction probe", tier="L1", dimension=dim))
        elif kind in VISUAL_KINDS:
            out.append(make_result(aid, name, NA,
                                   "routed to L2 multimodal judge; not auto-scored",
                                   tier="L2", dimension=dim))
        else:
            out.append(make_result(aid, name, SKIP, f"unknown assertion kind {kind!r}",
                                   tier="L1", dimension=dim))
    return out


def _browser_check(spec: dict[str, Any], page: Any) -> bool:
    try:
        if spec.get("kind") == "selector_exists":
            return page.query_selector(spec.get("selector", "body")) is not None
        if spec.get("kind") == "interaction_delta":
            from .state_probe import infer_evidence_grade, probe
            before = probe(page)
            sel = spec.get("selector", "")
            action = spec.get("action", "click")
            el = page.query_selector(sel)
            if el is None:
                return False
            if action == "click":
                el.click()
            elif action.startswith("key:"):
                page.keyboard.press(action.split(":", 1)[1])
            page.wait_for_timeout(int(spec.get("settle_ms", 200)))
            after = probe(page)
            return infer_evidence_grade(before, after) != "E0"
    except Exception:
        return False
    return False


def task_assertion_summary(path: str, source: str, page: Any = None) -> dict[str, Any]:
    assertions = load_task_assertions(path)
    s = summarize(run_task_assertions(assertions, source, page))
    s.update(classify(assertions))
    s["suite"] = "L1-task"
    return s
