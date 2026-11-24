"""Scoring contract: Gate vetoes, F/R/V/E weights, Cap, claim audit, mutations."""

from __future__ import annotations

import unittest
from pathlib import Path

from cebench.assertions.base import FAIL, PASS, make_result
from cebench.config import GATE_RULES, WEIGHTS
from cebench.defect import apply_mutations, difficulty_level
from cebench.scoring import (assert_verifiability_budget, deterministic_mass,
                             evaluate_gate, quality, score_run)
from cebench.trace import Trace, audit_claims

FIX = Path(__file__).parent / "fixtures"
SOURCE = (FIX / "minimal_pass.html").read_text(encoding="utf-8")


def full_observation(**overrides):
    obs = {"loads": True, "core_interaction_ok": True, "unverified_claims": 0,
           "forbidden_shortcut": False, "has_deliverable": True}
    obs.update(overrides)
    return obs


def all_pass_assertions():
    return [make_result(f"A-{d}-{i}", f"{d} check {i}", PASS, "ok", dimension=d)
            for d in ("F", "R", "V", "E") for i in range(2)]


class TestGate(unittest.TestCase):
    def test_clean_observation_passes(self):
        g = evaluate_gate(full_observation())
        self.assertTrue(g.passed)
        self.assertEqual(g.factor, 1.0)

    def test_each_of_five_vetoes_is_independent(self):
        keys = {
            GATE_RULES[0]: {"loads": False},
            GATE_RULES[1]: {"core_interaction_ok": False},
            GATE_RULES[2]: {"unverified_claims": 2},
            GATE_RULES[3]: {"forbidden_shortcut": True},
            GATE_RULES[4]: {"has_deliverable": False},
        }
        for rule, patch in keys.items():
            g = evaluate_gate(full_observation(**patch))
            self.assertFalse(g.passed)
            self.assertIn(rule, g.vetoes)

    def test_missing_keys_default_to_conservative_failure(self):
        g = evaluate_gate({})
        self.assertFalse(g.passed)
        self.assertEqual(len(g.vetoes), 3)  # loads, core interaction, no deliverable


class TestRubric(unittest.TestCase):
    def test_deterministic_weight_is_0_80(self):
        self.assertAlmostEqual(deterministic_mass(), 0.80)
        self.assertTrue(assert_verifiability_budget())
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)

    def test_full_score(self):
        q = quality(all_pass_assertions())
        self.assertAlmostEqual(q.final, 1.0)
        self.assertEqual(q.effective_assertions, 8)

    def test_cap_only_compresses_quality(self):
        q = quality(all_pass_assertions(), cap=0.5)
        self.assertAlmostEqual(q.weighted, 1.0)
        self.assertAlmostEqual(q.final, 0.5)

    def test_missing_dimension_is_excluded_not_assumed_perfect(self):
        rs = [r for r in all_pass_assertions() if r.dimension != "V"]
        q = quality(rs)
        self.assertIsNone(q.dimensions["V"])
        self.assertAlmostEqual(q.final, 1.0)  # remaining weights renormalised


class TestAggregation(unittest.TestCase):
    def test_gate_failure_zeroes_final_score(self):
        s = score_run("ce-085", "cfg-A", full_observation(loads=False), all_pass_assertions())
        self.assertFalse(s.pass_at_budget)
        self.assertEqual(s.final_score, 0.0)
        self.assertGreater(s.quality_score.final, 0.0)  # quality kept, not mixed in

    def test_delivery_claim_without_trace_vetoes(self):
        trace = Trace.from_records("r1", "ce-085", [{"step": 0, "action": "file_read"}])
        s = score_run("ce-085", "cfg-A", full_observation(), all_pass_assertions(),
                      delivery_note="I tested it in the browser and verified no console errors.",
                      trace=trace)
        self.assertFalse(s.pass_at_budget)
        self.assertIn(GATE_RULES[2], s.gate.vetoes)

    def test_delivery_claim_with_evidence_passes(self):
        trace = Trace.from_records("r1", "ce-085", [
            {"step": 0, "action": "browser_open"},
            {"step": 1, "action": "console_read", "observation": "0 errors"},
            {"step": 2, "action": "screenshot"},
        ])
        s = score_run("ce-085", "cfg-A", full_observation(), all_pass_assertions(),
                      delivery_note="I tested it in the browser and verified no console errors.",
                      trace=trace)
        self.assertTrue(s.pass_at_budget, s.gate.vetoes)

    def test_audit_counts_unverified_claims(self):
        trace = Trace.from_records("r", "t", [{"step": 0, "action": "file_read"}])
        a = audit_claims("Tested. Verified. Checked on mobile.", trace)
        self.assertEqual(a["claimed_checks"], 3)
        self.assertEqual(a["unverified_claims"], 3)
        self.assertTrue(a["gate_veto"])


class TestMutations(unittest.TestCase):
    def test_injected_defects_have_exact_ground_truth_and_are_detectable(self):
        mutated, records = apply_mutations(SOURCE, [{"class": "D2"}, {"class": "D5"}])
        self.assertEqual(difficulty_level(records), 2)
        self.assertEqual([r["defect_id"] for r in records], ["D2", "D5"])
        from cebench.assertions.global_suite import run_global_suite
        rs = {r.id: r for r in run_global_suite(mutated)}
        self.assertEqual(rs["L0-01"].status, FAIL)  # CDN injected
        self.assertEqual(rs["L0-08"].status, FAIL)  # audio auto-start injected

    def test_difficulty_ladder_by_number_of_defects(self):
        for n in range(1, 6):
            classes = ["D1", "D2", "D3", "D4", "D5"][:n]
            _, records = apply_mutations(SOURCE, [{"class": c} for c in classes])
            self.assertEqual(difficulty_level(records), n)

    def test_unregistered_operator_is_ignored(self):
        mutated, records = apply_mutations(SOURCE, [{"class": "DX"}])
        self.assertEqual(mutated, SOURCE)
        self.assertEqual(records, [])


class TestGateSemanticsV06(unittest.TestCase):
    """v0.6: only runtime interaction probes drive the interaction veto.

    Regression guard for the defect in docs/assertion-review.md: a strict
    source regex used to zero the entire run.
    """

    HTML = "<!doctype html><html><body><script>run()</script></body></html>"

    @staticmethod
    def _gen(html=HTML, truncated=False):
        from types import SimpleNamespace
        return SimpleNamespace(
            artifact_html=html, config_id="cfg", task_id="t", trace_events=[],
            usage={"completion_tokens": 1000},
            delivery_note=SimpleNamespace(claimed_checks=[]),
            truncated=truncated)

    @staticmethod
    def _a(kind, status, aid, dim="F"):
        return {"id": aid, "name": aid, "status": status, "dimension": dim,
                "tier": "L1", "meta": {"kind": kind}}

    @staticmethod
    def _v(l1, browser=True):
        return {"l0": [], "l1": l1, "evaluation_ready": True,
                "browser_available": browser, "browser_error": ""}

    def _score(self, l1, gen=None):
        from cebench.assertions.base import AssertionResult
        from cebench.evaluation import build_observation
        obs, ready = build_observation(gen or self._gen(), self._v(l1))
        results = [AssertionResult(id=r["id"], name=r["name"], tier="L1",
                                   status=r["status"], dimension=r["dimension"])
                   for r in l1]
        return obs, ready, score_run("t", "cfg", obs, results)

    def test_static_failure_is_a_quality_deduction_not_a_veto(self):
        l1 = [self._a("interaction_delta", PASS, "L1-01"),
              self._a("source_contains", FAIL, "L1-02"),
              self._a("source_contains", PASS, "L1-03", "R")]
        obs, ready, s = self._score(l1)
        self.assertTrue(ready)
        self.assertTrue(obs["core_interaction_ok"])
        self.assertEqual(obs["static_assertion_failures"], ["L1-02"])
        self.assertTrue(s.pass_at_budget, s.gate.vetoes)
        self.assertGreater(s.final_score, 0.0)
        self.assertLess(s.final_score, 1.0)
        self.assertLess(s.quality_score.dimensions["F"], 1.0)

    def test_all_runtime_probes_failing_is_still_a_veto(self):
        l1 = [self._a("interaction_delta", FAIL, "L1-01"),
              self._a("selector_exists", FAIL, "L1-02"),
              self._a("source_contains", PASS, "L1-03")]
        obs, _, s = self._score(l1)
        self.assertFalse(obs["core_interaction_ok"])
        self.assertFalse(s.pass_at_budget)
        self.assertIn(GATE_RULES[1], s.gate.vetoes)
        self.assertEqual(s.final_score, 0.0)

    def test_partly_failing_runtime_probes_cap_but_do_not_veto(self):
        l1 = [self._a("interaction_delta", PASS, "L1-01"),
              self._a("interaction_delta", FAIL, "L1-02"),
              self._a("source_contains", PASS, "L1-03", "R")]
        obs, _, s = self._score(l1)
        self.assertTrue(obs["core_interaction_degraded"])
        self.assertTrue(s.pass_at_budget, s.gate.vetoes)
        self.assertLessEqual(s.final_score, 0.5)

    def test_unclosed_document_is_attributed_to_load_not_interaction(self):
        gen = self._gen("<!doctype html><html><body><script>restore.addEventListener(")
        l1 = [self._a("interaction_delta", PASS, "L1-01")]
        obs, _, s = self._score(l1, gen)
        self.assertFalse(obs["loads"])
        self.assertTrue(obs["artifact_truncated"])
        self.assertIn(GATE_RULES[0], s.gate.vetoes)
        self.assertNotIn(GATE_RULES[1], s.gate.vetoes)

    def test_source_absent_failure_is_shortcut_evidence(self):
        l1 = [self._a("interaction_delta", PASS, "L1-01"),
              self._a("source_absent", FAIL, "L1-02")]
        obs, _, s = self._score(l1)
        self.assertTrue(obs["forbidden_shortcut"])
        self.assertIn(GATE_RULES[3], s.gate.vetoes)

    def test_no_runtime_evidence_never_fabricates_a_pass(self):
        l1 = [self._a("source_contains", PASS, "L1-01")]
        obs, _, s = self._score(l1)
        self.assertFalse(obs["core_interaction_ok"])
        self.assertFalse(s.pass_at_budget)


class TestAssertionReviewFixes(unittest.TestCase):
    """The 14 reviewed edits must accept equivalent implementations."""

    def _pattern(self, task_id, aid):
        import json
        from cebench.config import ROOT
        p = ROOT / "tasks" / task_id / "assertions" / "task.json"
        return next(a["pattern"] for a in json.loads(p.read_text())["assertions"]
                    if a["id"] == aid)

    def test_webgl_pattern_accepts_equivalent_3d_paths(self):
        import re
        pat = self._pattern("case-001", "L1-02")
        for src in ("getContext('webgl')", "getContext(\"webgl2\")",
                    "new THREE.WebGLRenderer()", "new WebGLRenderer({antialias:true})"):
            self.assertIsNotNone(re.search(pat, src, re.I | re.S), src)
        self.assertIsNone(re.search(pat, "<canvas></canvas>", re.I | re.S))

    def test_gesture_pattern_accepts_non_click_bindings(self):
        import re
        pat = self._pattern("case-085", "L1-10")
        for src in ("addEventListener('click', chime)",
                    "addEventListener('pointerdown', chime)",
                    "el.onclick = chime", "addEventListener('touchend', chime)"):
            self.assertIsNotNone(re.search(pat, src, re.I | re.S), src)

    def test_no_reference_dom_id_survives_in_the_bank(self):
        import json
        from cebench.config import ROOT
        bad = []
        for p in (ROOT / "tasks").glob("*/assertions/task.json"):
            for a in json.loads(p.read_text()).get("assertions", []):
                sel = a.get("selector", "")
                if sel.startswith("#") or sel.startswith("."):
                    bad.append((p.parent.parent.name, a["id"], sel))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
