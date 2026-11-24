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
STATIC_KINDS = {"source_contains", "source_absent"}
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
        meta = {"kind": kind}
        if kind in STATIC_KINDS:
            pattern = spec.get("pattern", "")
            found = bool(re.search(pattern, source, re.I | re.S)) if pattern else False
            ok = found if kind == "source_contains" else not found
            out.append(make_result(aid, name, PASS if ok else FAIL,
                                   f"pattern {pattern!r} {'found' if found else 'absent'}",
                                   tier="L1", dimension=dim, meta=meta))
        elif kind in BROWSER_KINDS:
            if page is None:
                out.append(make_result(aid, name, SKIP, "browser_unavailable: "
                                       "pinned Chromium page required", tier="L1",
                                       dimension=dim, meta=meta))
            else:
                ok, detail = _browser_check(spec, page)
                out.append(make_result(aid, name, PASS if ok else FAIL,
                                       detail, tier="L1", dimension=dim, meta=meta))
        elif kind in VISUAL_KINDS:
            out.append(make_result(aid, name, NA,
                                   "routed to L2 multimodal judge; not auto-scored",
                                   tier="L2", dimension=dim, meta=meta))
        else:
            out.append(make_result(aid, name, SKIP, f"unknown assertion kind {kind!r}",
                                   tier="L1", dimension=dim, meta=meta))
    return out


# A selector inherited from a third-party reference implementation (e.g.
# "#rake") is not observable by the model under test — the information-boundary
# rule forbids showing the reference. When such a selector misses, fall back to
# a semantic, implementation-agnostic candidate and record the substitution in
# the evidence. An interaction_delta still requires a real state change, so the
# fallback cannot fabricate a PASS. See docs/assertion-review.md.
GENERIC_SELECTORS = {
    "selector_exists": 'button, [role="button"], [onclick], canvas, svg, body',
    "interaction_delta": "canvas, svg, body",
}


def _resolve_element(spec: dict[str, Any], page: Any) -> tuple[Any, str, bool]:
    sel = spec.get("selector", "") or ""
    el = page.query_selector(sel) if sel else None
    if el is not None:
        return el, sel, False
    generic = GENERIC_SELECTORS.get(spec.get("kind", ""), "body")
    return page.query_selector(generic), sel or "<none>", True


def _browser_check(spec: dict[str, Any], page: Any) -> tuple[bool, str]:
    """Return (passed, human-readable evidence), never a bare bool."""
    try:
        el, sel, fell_back = _resolve_element(spec, page)
        if el is None:
            return False, f"browser probe: no interactive element (selector {sel!r})"
        note = (f"browser probe on {sel!r}"
                + (" [generic selector fallback]" if fell_back else ""))
        if spec.get("kind") == "selector_exists":
            return True, note
        if spec.get("kind") == "interaction_delta":
            from .state_probe import infer_evidence_grade, probe
            before = probe(page)
            action = spec.get("action", "click")
            if action == "click":
                el.click()
            elif action.startswith("key:"):
                page.keyboard.press(action.split(":", 1)[1])
            page.wait_for_timeout(int(spec.get("settle_ms", 200)))
            after = probe(page)
            grade = infer_evidence_grade(before, after)
            return grade != "E0", f"{note}; state evidence grade {grade}"
    except Exception as exc:
        return False, f"browser probe raised {type(exc).__name__}: {exc}"[:220]
    return False, "browser probe: unsupported kind"


def task_assertion_summary(path: str, source: str, page: Any = None) -> dict[str, Any]:
    assertions = load_task_assertions(path)
    s = summarize(run_task_assertions(assertions, source, page))
    s.update(classify(assertions))
    s["suite"] = "L1-task"
    return s
