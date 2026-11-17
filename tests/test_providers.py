"""The API input layer must be safe and usable before any key exists."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cebench.evaluation import RunPlan, TaskSpec, run_evaluation
from cebench.generate import (SYSTEM_PROMPT, DeliveryNote, GenerationResult,
                              build_messages, extract_delivery_note, extract_html,
                              generate_one)
from cebench.providers import (ConfigError, DryRunClient, MissingCredentialError,
                               build_client, load_model_configs, resolve_api_key,
                               validate_configs)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config" / "models.example.json"


def write_tmp(obj: dict) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(obj, f)
    f.close()
    return Path(f.name)


def minimal(**over):
    d = {"id": "cfg-test", "protocol": "openai-compatible",
         "base_url": "https://example.com/v1", "api_key_env": "TEST_API_KEY",
         "model": "model-x", "harness": "single-shot-l2",
         "training_cutoff": "2026-01-01"}
    d.update(over)
    return d


class TestConfigSafety(unittest.TestCase):
    def test_example_config_loads(self):
        cfgs = load_model_configs(EXAMPLE)
        self.assertEqual(len(cfgs), 4)
        self.assertEqual([c.protocol for c in cfgs][1], "anthropic")

    def test_literal_key_is_rejected(self):
        # Build the fake token at runtime: no credential-shaped literal lives in
        # the source, but the written config still has to be rejected.
        fake = "sk-" + "x" * 24
        cfg = write_tmp({"models": [minimal(extra_headers={"X-Note": fake})]})
        with self.assertRaises(ConfigError):
            load_model_configs(cfg)
        cfg.unlink()

    def test_api_key_field_is_rejected(self):
        cfg = write_tmp({"models": [minimal(api_key="whatever")]})
        with self.assertRaises(ConfigError):
            load_model_configs(cfg)
        cfg.unlink()

    def test_env_var_must_be_a_name(self):
        cfg = write_tmp({"models": [minimal(api_key_env="my-secret-value")]})
        with self.assertRaises(ConfigError):
            load_model_configs(cfg)
        cfg.unlink()

    def test_missing_required_field(self):
        cfg = write_tmp({"models": [minimal(training_cutoff="")]})
        with self.assertRaises(ConfigError):
            load_model_configs(cfg)
        cfg.unlink()

    def test_sanitized_contains_no_secret(self):
        c = load_model_configs(EXAMPLE)[0]
        s = c.sanitized()
        self.assertNotIn("api_key", s)
        self.assertEqual(s["api_key_env"], "OPENAI_API_KEY")
        self.assertNotIn("sk-", json.dumps(s))

    def test_validate_reports_missing_keys_without_failing(self):
        cfgs = load_model_configs(EXAMPLE)
        with patch.dict(os.environ, {}, clear=True):
            report = validate_configs(cfgs, require_keys=False)
        self.assertTrue(report["ready"])
        self.assertEqual(len(report["missing_keys"]), 4)
        self.assertEqual(report["missing_keys"][0]["env_var"], "OPENAI_API_KEY")

    def test_resolve_key_reads_environment(self):
        c = load_model_configs(EXAMPLE)[0]
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MissingCredentialError):
                resolve_api_key(c)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy-value"}):
            self.assertEqual(resolve_api_key(c), "dummy-value")

    def test_strict_mode_fails_when_keys_missing(self):
        cfgs = load_model_configs(EXAMPLE)
        with patch.dict(os.environ, {}, clear=True):
            report = validate_configs(cfgs, require_keys=True)
        self.assertFalse(report["ready"])


class TestDryRunAndBoundary(unittest.TestCase):
    def test_dry_run_client_never_produces_scoreable_output(self):
        c = load_model_configs(EXAMPLE)[0]
        client = build_client(c, dry_run=True)
        self.assertIsInstance(client, DryRunClient)
        r = client.chat(build_messages("hello", "t1", {}))
        self.assertTrue(r.dry_run)
        self.assertIn("DRY_RUN_PLACEHOLDER", r.content)

    def test_real_client_requires_key(self):
        c = load_model_configs(EXAMPLE)[0]
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MissingCredentialError):
                build_client(c, dry_run=False)

    def test_system_prompt_does_not_leak_the_rubric(self):
        for forbidden in ("L0-01", "Gate", "0.35", "Pass@Budget", "F1", "rubric", "assertion"):
            self.assertNotIn(forbidden, SYSTEM_PROMPT,
                             f"system prompt leaked {forbidden!r} to the model")

    def test_run_plan_loads_from_example(self):
        p = RunPlan.load(ROOT / "config" / "run.example.json")
        self.assertEqual(p.repetitions, 3)
        self.assertEqual(p.track, "CE-Frozen")


class TestGenerationParsing(unittest.TestCase):
    def test_extract_html_from_fence(self):
        text = ('Here is the artifact.\n```html\n<!doctype html><html><body>ok</body></html>\n```\n'
                'Hand-off note follows.')
        html = extract_html(text)
        self.assertIsNotNone(html)
        self.assertTrue(html.lower().startswith("<!doctype html>"))
        self.assertIn("</html>", html)

    def test_extract_html_rejects_prose_only(self):
        self.assertIsNone(extract_html("I could not build the page."))

    def test_extract_delivery_note(self):
        text = ('<!doctype html><html></html>\n\nCEBENCH_DELIVERY '
                '{"self_assessed_completion": 82, "weak_points": ["audio", "mobile"], '
                '"claimed_checks": ["opened in browser, no console errors"]}')
        note = extract_delivery_note(text)
        self.assertAlmostEqual(note.self_assessed_completion, 0.82)
        self.assertEqual(len(note.weak_points), 2)
        self.assertEqual(len(note.claimed_checks), 1)

    def test_missing_note_is_not_invented(self):
        note = extract_delivery_note("<!doctype html><html></html>")
        self.assertIsNone(note.self_assessed_completion)
        self.assertEqual(note.weak_points, [])

    def test_dry_run_generation_is_never_scoreable(self):
        g = GenerationResult("t", "c", 1, "<html></html>", DeliveryNote(), {},
                             dry_run=True)
        self.assertFalse(g.scoreable)

    def test_offline_stub_is_not_reported_as_a_provider_error(self):
        cfg = load_model_configs(EXAMPLE)[0]
        g = generate_one(build_client(cfg, dry_run=True), "t", "prompt",
                         cfg.id, 1, {})
        self.assertEqual(g.error, "")
        self.assertFalse(g.scoreable)


class TestDryRunOrchestration(unittest.TestCase):
    """A rehearsal must actually exercise the pipeline, and must never score."""

    def setUp(self):
        self.configs = load_model_configs(EXAMPLE)
        self.plan = RunPlan(run_id="unit-test-dry-run", split="POST", repetitions=1)
        self.task = TaskSpec(task_id="dry-run-synthetic", prompt="[synthetic]",
                             published_at=None)

    def test_dry_run_is_not_silently_filtered_out_by_the_post_split(self):
        # Regression: a synthetic task has no publishedAt, so a strict POST
        # filter used to skip every loop while still printing "DRY RUN COMPLETE".
        with tempfile.TemporaryDirectory() as tmp:
            rows = run_evaluation(self.configs, self.plan, [self.task],
                                  dry_run=True, out_root=tmp, verbose=False)
            self.assertEqual(len(rows), len(self.configs))
            for r in rows:
                self.assertEqual(r["split"], "DRY-RUN")
                self.assertTrue(r["dry_run"])
                self.assertFalse(r["evaluation_ready"])
                self.assertIn(r["pass_at_budget"], ("", None, False))
                self.assertEqual(r["final_score"], "")
            self.assertEqual(list(Path(tmp).iterdir()), [],
                             "dry run must not create a run directory")

    def test_real_runs_still_apply_the_split_filter(self):
        pre_task = TaskSpec(task_id="old-task", prompt="[synthetic]",
                            published_at="2020-01-01", split="PRE")
        with patch("cebench.evaluation.build_client",
                   side_effect=lambda cfg, dry_run=False: DryRunClient(cfg)):
            with tempfile.TemporaryDirectory() as tmp:
                rows = run_evaluation(self.configs[:1], self.plan, [pre_task],
                                      dry_run=False, out_root=tmp, verbose=False)
        self.assertEqual(rows, [], "a PRE task must not leak into a POST run")


if __name__ == "__main__":
    unittest.main()
