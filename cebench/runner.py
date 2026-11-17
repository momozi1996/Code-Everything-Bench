"""L2 execution interface — the contract between an agent and the evaluator.

What an agent (or a submitted run) may observe:
    ✅ its own artifact rendered in a browser, screenshots, console/network
       errors, build logs, and the results of tests it writes itself
    ❌ the original author's demo, the hidden rubric, the corpus reference
       implementation, or internet search for answers

The browser layer is optional and lazily loaded. When it is missing the runner
records `browser_unavailable` and returns SKIP for runtime assertions; it does
not fabricate a pass. This is the same rule we apply to the systems under test.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .assertions import (global_summary, run_global_suite,
                         run_task_assertions, task_assertion_summary)
from .assertions.state_probe import INIT_JS, probe
from .config import DEFAULT_BUDGET, ROOT, VERSION


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


@contextmanager
def browser_page(artifact: str | Path) -> Iterator[Any]:
    """Open a single-file HTML artifact via file:// with a pinned viewport.

    Yields a page-like object with `console_errors` and `page_errors` lists
    attached, so L0-03 can be evaluated without importing Playwright upstream.
    """
    if not playwright_available():
        raise RuntimeError("browser_unavailable: install requirements.txt and `playwright install chromium`")
    from playwright.sync_api import sync_playwright  # type: ignore

    path = Path(artifact).resolve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.add_init_script(INIT_JS)
        page.goto(path.as_uri(), wait_until="load")
        page.wait_for_timeout(300)
        page.console_errors = errors           # type: ignore[attr-defined]
        page.page_errors = page_errors         # type: ignore[attr-defined]
        try:
            yield page
        finally:
            browser.close()


def load_source(artifact: str | Path) -> str:
    p = Path(artifact)
    if not p.is_file():
        raise FileNotFoundError(f"no deliverable file at {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def verify_artifact(artifact: str | Path, task_dir: str | Path | None = None,
                    *, use_browser: bool | None = None) -> dict[str, Any]:
    """Run L0 (+L1 when a task pack is given) and return a structured observation.

    Static assertions always run. Browser assertions run only when Playwright is
    available; otherwise they are SKIP with explicit evidence.
    """
    source = load_source(artifact)
    want_browser = playwright_available() if use_browser is None else use_browser
    page = None
    state: dict[str, Any] = {}
    if want_browser and playwright_available():
        with browser_page(artifact) as pg:
            page = pg
            state = probe(pg)
            l0 = run_global_suite(source, pg)
            l1_results = []
            if task_dir:
                from .config import load_config
                specs = load_config(Path(task_dir) / "assertions" / "task.json").get("assertions", [])
                l1_results = run_task_assertions(specs, source, pg)
    else:
        l0 = run_global_suite(source, None)
        l1_results = []
        if task_dir:
            from .config import load_config
            specs = load_config(Path(task_dir) / "assertions" / "task.json").get("assertions", [])
            l1_results = run_task_assertions(specs, source, None)

    from .assertions.base import summarize
    l0s = summarize(l0)
    l1s = summarize(l1_results) if l1_results else {"total": 0, "effective_assertions": 0,
                                                    "pass_rate": None, "coverage_complete": True}
    return {
        "schema_version": VERSION,
        "artifact": str(Path(artifact).resolve()),
        "task_id": Path(task_dir).name if task_dir else None,
        "browser_available": want_browser and playwright_available(),
        "evaluation_ready": bool(l0s["coverage_complete"]),
        "budget": DEFAULT_BUDGET,
        "l0": [r.to_dict() for r in l0],
        "l0_summary": l0s,
        "l1": [r.to_dict() for r in l1_results],
        "l1_summary": l1s,
        "state_probe": state,
        "note": ("Gate is not evaluated in static mode: core-interaction and "
                 "console checks require the pinned browser." if page is None else
                 "Full browser evidence collected."),
    }


def contract() -> dict[str, Any]:
    """Machine-readable description of the L2 interface (for run submitters)."""
    return {
        "observe": ["rendered artifact", "screenshot", "console/network errors",
                    "build log", "self-authored test results", "runtime state probe"],
        "forbidden": ["original author's demo", "hidden rubric", "reference implementation",
                      "internet search for answers"],
        "required_delivery": ["artifact file", "assumptions.md", "delivery note with "
                              "self-assessed completion and top-3 weak points"],
        "budget": DEFAULT_BUDGET,
        "version": VERSION,
        "root": str(ROOT),
    }
