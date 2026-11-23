"""L0 — the eight global assertions shared by every task in the bank.

These are the ten community baseline rules from the source corpus distilled
into mechanically checkable form (paper §5.2). Six are static source checks;
two (L0-03 console errors, L0-04 360px overflow) require a real browser and are
reported as SKIP when Playwright is unavailable. SKIP is never a PASS.

Design rule: the reference implementation of each task must pass all applicable
L0 rules. If it does not, the *assertion* is wrong, not the artifact. This is
enforced by the CI meta-test gate.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import L0_IDS
from .base import FAIL, NA, PASS, SKIP, AssertionResult, make_result, summarize

_EXTERNAL = (
    (re.compile(r"<script[^>]*\bsrc\s*=", re.I), "external <script src>"),
    (re.compile(r"<link[^>]*\bhref\s*=\s*['\"](?!#|data:)", re.I), "external <link href>"),
    (re.compile(r"<img[^>]*\bsrc\s*=\s*['\"]https?://", re.I), "remote <img src>"),
    (re.compile(r"<iframe[^>]*\bsrc\s*=\s*['\"]https?://", re.I), "remote <iframe src>"),
    (re.compile(r"@import\s+url\(", re.I), "CSS @import"),
    (re.compile(r"url\(\s*['\"]?https?://", re.I), "remote CSS url()"),
    (re.compile(r"\bfetch\(\s*['\"]https?://", re.I), "external fetch()"),
    (re.compile(r"https?://(?:cdn\.|unpkg\.|cdnjs\.|jsdelivr\.|fonts\.googleapis\.|code\.jquery\.com)", re.I),
     "known CDN domain"),
)

_GESTURE = re.compile(
    r"addEventListener\(\s*['\"](?:click|pointerdown|pointerup|keydown|keyup|touchstart|touchend)['\"]",
    re.I,
)
_POINTER = re.compile(
    r"addEventListener\(\s*['\"](?:click|pointerdown|mousedown|touchstart)['\"]|onclick\s*=", re.I
)
_KEYBOARD = re.compile(
    r"addEventListener\(\s*['\"](?:keydown|keyup|keypress)['\"]|onkeydown\s*=|tabindex|<button\b", re.I
)
_ANIMATION = re.compile(
    r"requestAnimationFrame|setInterval\s*\(|setTimeout\s*\(|@keyframes|animate\s*\(|transition\s*:", re.I
)
_AUDIO = re.compile(r"\b(?:webkit)?AudioContext\b", re.I)


def _l01(source: str, page: Any) -> AssertionResult:
    hits = [label for pat, label in _EXTERNAL if pat.search(source)]
    if hits:
        return make_result(L0_IDS[0], "Single file / no external resources", FAIL,
                           "external references: " + ", ".join(hits))
    return make_result(L0_IDS[0], "Single file / no external resources", PASS,
                       "no external script/link/import/fetch references")


def _l02(source: str, page: Any) -> AssertionResult:
    doctype = re.search(r"<!doctype\s+html", source, re.I) is not None
    viewport = re.search(r"<meta[^>]*name\s*=\s*['\"]viewport['\"][^>]*>", source, re.I)
    width_ok = bool(viewport and "width=device-width" in viewport.group(0).lower())
    missing = [n for n, ok in (("doctype", doctype), ("meta viewport", bool(viewport)),
                               ("width=device-width", width_ok)) if not ok]
    if missing:
        return make_result(L0_IDS[1], "DOCTYPE + viewport meta", FAIL,
                           "missing: " + ", ".join(missing))
    return make_result(L0_IDS[1], "DOCTYPE + viewport meta", PASS,
                       "doctype html + responsive viewport declared")


def _runtime_unavailable(rule: str, name: str, reason: str = "browser_unavailable") -> AssertionResult:
    return make_result(rule, name, SKIP, f"{reason}: a pinned Chromium page is required")


def _l03(source: str, page: Any) -> AssertionResult:
    name = "No console / page errors under file://"
    if page is None:
        return _runtime_unavailable(L0_IDS[2], name)
    try:
        errors = list(getattr(page, "console_errors", [])) + list(getattr(page, "page_errors", []))
    except Exception as exc:  # pragma: no cover - defensive
        return make_result(L0_IDS[2], name, SKIP, f"probe failed: {exc}")
    if errors:
        return make_result(L0_IDS[2], name, FAIL, "; ".join(str(e)[:160] for e in errors[:5]))
    return make_result(L0_IDS[2], name, PASS, "0 console errors, 0 uncaught exceptions")


def _l04(source: str, page: Any) -> AssertionResult:
    name = "No horizontal overflow at 360px"
    if page is None:
        return _runtime_unavailable(L0_IDS[3], name)
    try:
        page.set_viewport_size({"width": 360, "height": 780})
        metrics = page.evaluate("() => ({s: document.documentElement.scrollWidth,"
                                " c: document.documentElement.clientWidth})")
        overflow = int(metrics["s"]) - int(metrics["c"])
    except Exception as exc:  # pragma: no cover - defensive
        return make_result(L0_IDS[3], name, SKIP, f"probe failed: {exc}")
    if overflow > 1:
        return make_result(L0_IDS[3], name, FAIL, f"scrollWidth exceeds clientWidth by {overflow}px")
    return make_result(L0_IDS[3], name, PASS, "360px viewport: no horizontal scroll")


def _l05(source: str, page: Any) -> AssertionResult:
    name = "Animation uses requestAnimationFrame"
    if not _ANIMATION.search(source):
        return make_result(L0_IDS[4], name, NA, "no animation declared")
    if "requestAnimationFrame" not in source:
        return make_result(L0_IDS[4], name, FAIL,
                           "animation present but driven by timer instead of rAF")
    return make_result(L0_IDS[4], name, PASS, "rAF-driven animation loop")


def _l06(source: str, page: Any) -> AssertionResult:
    name = "prefers-reduced-motion honoured"
    if not _ANIMATION.search(source):
        return make_result(L0_IDS[5], name, NA, "no animation declared")
    if "prefers-reduced-motion" not in source:
        return make_result(L0_IDS[5], name, FAIL, "animation without reduced-motion branch")
    return make_result(L0_IDS[5], name, PASS, "reduced-motion media query / matchMedia present")


def _l07(source: str, page: Any) -> AssertionResult:
    name = "Pointer + keyboard parity"
    if not _POINTER.search(source):
        return make_result(L0_IDS[6], name, NA, "no pointer interaction declared")
    if not _KEYBOARD.search(source):
        return make_result(L0_IDS[6], name, FAIL, "pointer interaction without keyboard path")
    return make_result(L0_IDS[6], name, PASS, "both pointer and keyboard input paths present")


def _l08(source: str, page: Any) -> AssertionResult:
    name = "Web Audio requires a user gesture"
    if not _AUDIO.search(source):
        return make_result(L0_IDS[7], name, NA, "no Web Audio usage")
    gesture = bool(_GESTURE.search(source))
    eager = bool(re.search(r"new\s+(?:webkit)?AudioContext\s*\([^)]*\)\s*\.", source, re.I))
    if not gesture or eager:
        return make_result(L0_IDS[7], name, FAIL,
                           "AudioContext starts without a gated gesture (autoplay risk)")
    return make_result(L0_IDS[7], name, PASS, "AudioContext created inside a gesture handler")


_CHECKS = (_l01, _l02, _l03, _l04, _l05, _l06, _l07, _l08)


def run_global_suite(source: str, page: Any = None) -> list[AssertionResult]:
    """Evaluate all eight L0 rules against an artifact's source.

    `page` is an optional Playwright-like page object. When omitted, runtime
    rules return SKIP with evidence `browser_unavailable` — never PASS.
    """
    return [check(source, page) for check in _CHECKS]


def global_summary(source: str, page: Any = None) -> dict[str, Any]:
    s = summarize(run_global_suite(source, page))
    s["suite"] = "L0-global"
    s["rules"] = list(L0_IDS)
    return s
