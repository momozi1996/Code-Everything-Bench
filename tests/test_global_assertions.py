"""Runs on a fresh clone with the standard library alone.

Runtime (browser) assertions are executed only when Playwright is installed;
otherwise their SKIP status is asserted. A green suite here therefore means
"every check that could run passed, and every check that could not run said so".
"""

from __future__ import annotations

import unittest
from pathlib import Path

from cebench.assertions.base import FAIL, NA, PASS, SKIP, summarize
from cebench.assertions.global_suite import run_global_suite
from cebench.config import L0_IDS
from cebench.runner import playwright_available

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def by_id(source: str):
    return {r.id: r for r in run_global_suite(source)}


class TestGlobalSuite(unittest.TestCase):
    def test_suite_has_exactly_eight_declared_rules(self):
        rs = run_global_suite("")
        self.assertEqual(len(rs), 8)
        self.assertEqual([r.id for r in rs], list(L0_IDS))

    def test_pass_fixture_passes_all_static_rules(self):
        rs = by_id(read("minimal_pass.html"))
        for rid in ("L0-01", "L0-02", "L0-05", "L0-06", "L0-07", "L0-08"):
            self.assertEqual(rs[rid].status, PASS,
                             f"{rid} failed: {rs[rid].evidence}")

    def test_runtime_rules_are_skipped_not_passed_without_browser(self):
        rs = by_id(read("minimal_pass.html"))
        for rid in ("L0-03", "L0-04"):
            self.assertEqual(rs[rid].status, SKIP)
            self.assertIn("browser_unavailable", rs[rid].evidence)

    def test_external_cdn_is_detected(self):
        rs = by_id(read("fail_external_cdn.html"))
        self.assertEqual(rs["L0-01"].status, FAIL)
        self.assertIn("external", rs["L0-01"].evidence)

    def test_missing_doctype_and_viewport_are_detected(self):
        rs = by_id("<html><body>hello</body></html>")
        self.assertEqual(rs["L0-02"].status, FAIL)
        self.assertIn("doctype", rs["L0-02"].evidence)
        self.assertIn("viewport", rs["L0-02"].evidence)

    def test_na_for_rules_that_do_not_apply(self):
        rs = by_id("<!doctype html><meta name='viewport' content='width=device-width'>"
                   "<p>static page</p>")
        for rid in ("L0-05", "L0-06", "L0-07", "L0-08"):
            self.assertEqual(rs[rid].status, NA, f"{rid}: {rs[rid].evidence}")

    def test_effective_denominator_excludes_na_and_skip(self):
        s = summarize(run_global_suite(read("minimal_pass.html")))
        self.assertEqual(s["total"], 8)
        self.assertEqual(s["passed"], 6)
        self.assertEqual(s["skipped"], 2)
        self.assertEqual(s["na"], 0)
        self.assertEqual(s["effective_assertions"], 6)
        self.assertAlmostEqual(s["pass_rate"], 1.0)
        self.assertFalse(s["coverage_complete"])  # two browser checks could not run

    def test_na_does_not_inflate_pass_rate(self):
        rs = run_global_suite("<!doctype html><meta name='viewport' "
                              "content='width=device-width'><p>static</p>")
        s = summarize(rs)
        self.assertEqual(s["effective_assertions"], 2)  # L0-01, L0-02 only
        self.assertEqual(s["na"], 4)
        self.assertEqual(s["skipped"], 2)

    @unittest.skipUnless(playwright_available(), "Playwright not installed")
    def test_browser_mode_passes_fixture_and_fails_overflow(self):
        from cebench.runner import browser_page
        with browser_page(FIX / "minimal_pass.html") as page:
            rs = {r.id: r for r in run_global_suite(read("minimal_pass.html"), page)}
            self.assertEqual(rs["L0-03"].status, PASS, rs["L0-03"].evidence)
            self.assertEqual(rs["L0-04"].status, PASS, rs["L0-04"].evidence)
        with browser_page(FIX / "fail_overflow_360.html") as page:
            rs = {r.id: r for r in run_global_suite(read("fail_overflow_360.html"), page)}
            self.assertEqual(rs["L0-04"].status, FAIL, rs["L0-04"].evidence)


if __name__ == "__main__":
    unittest.main()
