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


if __name__ == "__main__":
    unittest.main()
