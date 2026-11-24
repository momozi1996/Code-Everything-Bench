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


class TestHarnessPinning(unittest.TestCase):
    """The dual-regime policy needs every run to record its exact harness."""

    HARNESS_EXAMPLE = ROOT / "config" / "models.harness.example.json"

    def test_harness_impl_defaults_to_harness(self):
        cfg = write_tmp({"models": [minimal()]})
        c = load_model_configs(cfg)[0]
        self.assertEqual(c.harness_impl, c.harness)
        self.assertEqual(c.harness_version, "")
        cfg.unlink()

    def test_harness_impl_and_version_are_parsed_and_sanitised(self):
        cfgs = load_model_configs(self.HARNESS_EXAMPLE)
        by_id = {c.id: c for c in cfgs}
        agent = by_id["cfg-h1-mini-swe-agent"]
        self.assertEqual(agent.harness, "agent-harness-l2")
        self.assertEqual(agent.harness_impl, "mini-swe-agent")
        self.assertEqual(agent.harness_version, "PIN_ME")
        s = agent.sanitized()
        self.assertEqual(s["harness_impl"], "mini-swe-agent")
        self.assertEqual(s["harness_version"], "PIN_ME")
        # the bare row pins itself
        self.assertEqual(by_id["cfg-h0-bare"].harness_impl, "single-shot-l2")

    def test_entry_level_timeout_overrides_defaults(self):
        cfgs = load_model_configs(self.HARNESS_EXAMPLE)
        by_id = {c.id: c for c in cfgs}
        # A 512k output cap needs a generous wall-clock allowance: targets are
        # pinned to 3600 s; the judge has no entry-level value and therefore
        # inherits the same defaults-level 3600 s.
        self.assertEqual(by_id["cfg-h0-bare"].timeout_seconds, 3600)
        # judge row has no entry-level value -> falls back to defaults (3600)
        self.assertEqual(by_id["judge-deepseek-v41-flash"].timeout_seconds, 3600)
        # a config with distinct defaults still respects entry-level override
        cfg = write_tmp({"defaults": {"timeout_seconds": 1800},
                         "models": [minimal(timeout_seconds=240)]})
        self.assertEqual(load_model_configs(cfg)[0].timeout_seconds, 240)
        cfg.unlink()
        cfg = write_tmp({"defaults": {"timeout_seconds": 1800},
                         "models": [minimal()]})
        self.assertEqual(load_model_configs(cfg)[0].timeout_seconds, 1800)
        cfg.unlink()


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


class TestOutputCap(unittest.TestCase):
    """A truncated artifact is a scoring artifact, not a model failure."""

    def test_all_shipped_configs_use_one_target_cap(self):
        from cebench.config import TARGET_MAX_TOKENS
        for p in sorted((ROOT / "config").glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            if "models" in data:
                self.assertEqual(data.get("defaults", {}).get("max_tokens"),
                                 TARGET_MAX_TOKENS, p.name)
                for m in data["models"]:
                    expect = 8192 if m.get("role") == "judge" else TARGET_MAX_TOKENS
                    self.assertEqual(m.get("params", {}).get("max_tokens"), expect,
                                     f"{p.name}/{m['id']}")
            if "budget" in data:
                self.assertEqual(data["budget"]["max_output_tokens"],
                                 TARGET_MAX_TOKENS, p.name)

    def test_low_cap_emits_a_warning_not_a_hard_failure(self):
        cfg = write_tmp({"models": [minimal(params={"max_tokens": 16000})]})
        with patch.dict(os.environ, {"TEST_API_KEY": "x"}):
            report = validate_configs(load_model_configs(cfg), require_keys=False)
        self.assertTrue(report["ready"])
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("truncated", report["warnings"][0]["hint"])
        cfg.unlink()

    def test_provider_falls_back_to_contract_cap_and_keeps_finish_reason(self):
        from cebench.config import TARGET_MAX_TOKENS
        from cebench.providers import OpenAICompatibleClient
        p = write_tmp({"models": [minimal()]})
        cfg = load_model_configs(p)[0]
        p.unlink()
        client = OpenAICompatibleClient(cfg, "dummy")
        captured = {}

        def fake_post(url, headers, body):
            captured.update(body)
            return {"choices": [{"message": {"content": "ok"},
                                "finish_reason": "length"}],
                    "usage": {"completion_tokens": 512000}, "model": "x", "id": "y"}

        client._post = fake_post
        resp = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(captured["max_tokens"], TARGET_MAX_TOKENS)
        self.assertEqual(resp.finish_reason, "length")

    def test_generation_marks_a_length_stop_as_truncated(self):
        from types import SimpleNamespace
        from cebench.providers import LLMResponse
        from cebench.generate import generate_one

        class Stub:
            cfg = SimpleNamespace(params={"max_tokens": 512000})

            def chat(self, messages, **kw):
                return LLMResponse(content="<!doctype html><html></html>",
                                   usage={"completion_tokens": 512000},
                                   finish_reason="length")

        g = generate_one(Stub(), "t", "p", "c", 1, {}, out_dir=None)
        self.assertTrue(g.truncated)
        self.assertTrue(g.to_dict()["truncated"])


if __name__ == "__main__":
    unittest.main()
