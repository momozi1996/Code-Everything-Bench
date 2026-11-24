"""Unified model API layer — the part the user fills in before a real run.

Design contract:

* Credentials are **never stored in a file**. Each configuration names an
  environment variable via `api_key_env`; a literal key in the config is a
  validation error.
* Two protocols are supported out of the box: `openai-compatible` (covers
  OpenAI, vLLM, SGLang, Ollama shims, and most gateways) and `anthropic`.
  Both use the standard library only — no SDK dependency.
* `DryRunClient` never touches the network and never produces a scoreable
  artifact. It exists so the whole pipeline can be rehearsed before keys exist.
* The Authorization header is never written to a trace or a log.

Add a new provider by subclassing `BaseClient` and registering it in
`CLIENT_REGISTRY`; nothing else in the codebase needs to change.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (TARGET_MAX_TOKENS, TARGET_MAX_TOKENS_RECOMMENDED_MIN)

PROTOCOLS = ("openai-compatible", "anthropic")

# Reject anything that looks like a pasted credential anywhere in the config.
_LITERAL_KEY_PATTERNS = (
    re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16,}"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"),
)


class ConfigError(ValueError):
    """Configuration is malformed or unsafe."""


class MissingCredentialError(RuntimeError):
    """A referenced environment variable is not set."""


class ProviderError(RuntimeError):
    """The remote API returned an error after retries."""


@dataclass
class ModelConfig:
    id: str
    protocol: str
    base_url: str
    api_key_env: str
    model: str
    harness: str
    training_cutoff: str
    harness_impl: str = ""      # concrete implementation, e.g. "mini-swe-agent"; defaults to harness
    harness_version: str = ""   # exact pinned release; a floating tag is not reproducible
    params: dict[str, Any] = field(default_factory=dict)
    extra_headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120
    max_retries: int = 3
    role: str = "target"  # "target" (generates artifacts) | "judge" (scores L2)

    @classmethod
    def from_dict(cls, d: dict[str, Any], defaults: dict[str, Any] | None = None) -> "ModelConfig":
        defaults = defaults or {}
        required = ("id", "protocol", "base_url", "api_key_env", "model", "harness",
                    "training_cutoff")
        missing = [k for k in required if not d.get(k)]
        if missing:
            raise ConfigError(f"configuration {d.get('id', '?')!r} missing fields: {missing}")
        if d["protocol"] not in PROTOCOLS:
            raise ConfigError(f"unknown protocol {d['protocol']!r}; choose from {PROTOCOLS}")
        if not re.match(r"^[A-Z][A-Z0-9_]*$", str(d["api_key_env"])):
            raise ConfigError("api_key_env must be an UPPER_SNAKE_CASE variable NAME, not a value")
        if "api_key" in d or "apiKey" in d or "token" in d:
            raise ConfigError("a literal credential field was found; use api_key_env instead")
        params = {**{k: defaults[k] for k in ("temperature", "max_tokens", "top_p")
                     if k in defaults}, **(d.get("params") or {})}
        return cls(
            id=d["id"], protocol=d["protocol"], base_url=d["base_url"].rstrip("/"),
            api_key_env=d["api_key_env"], model=d["model"], harness=d["harness"],
            training_cutoff=d["training_cutoff"], params=params,
            harness_impl=str(d.get("harness_impl") or d["harness"]),
            harness_version=str(d.get("harness_version") or ""),
            extra_headers=d.get("extra_headers") or {},
            timeout_seconds=int(d.get("timeout_seconds", defaults.get("timeout_seconds", 120))),
            max_retries=int(d.get("max_retries", defaults.get("max_retries", 3))),
            role=str(d.get("role") or defaults.get("role") or "target"),
        )

    def sanitized(self) -> dict[str, Any]:
        """Safe to commit: no key value, only the variable name."""
        return {"id": self.id, "protocol": self.protocol, "base_url": self.base_url,
                "api_key_env": self.api_key_env, "model": self.model,
                "harness": self.harness, "training_cutoff": self.training_cutoff,
                "harness_impl": self.harness_impl or self.harness,
                "harness_version": self.harness_version,
                "params": self.params, "timeout_seconds": self.timeout_seconds,
                "role": self.role}


def load_model_configs(path: str | Path) -> list[ModelConfig]:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"model config not found: {p}. Copy config/models.example.json first.")
    raw = p.read_text(encoding="utf-8")
    for pat in _LITERAL_KEY_PATTERNS:
        if pat.search(raw):
            raise ConfigError("a credential-looking literal was found in the model config. "
                              "Put keys in .env and reference them by api_key_env.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON: {exc}") from exc
    defaults = data.get("defaults", {})
    rows = data.get("models", [])
    if not rows:
        raise ConfigError("no models defined")
    configs = [ModelConfig.from_dict(d, defaults) for d in rows]
    ids = [c.id for c in configs]
    if len(ids) != len(set(ids)):
        raise ConfigError("duplicate configuration ids")
    return configs


def resolve_api_key(cfg: ModelConfig) -> str:
    value = os.environ.get(cfg.api_key_env)
    if not value:
        raise MissingCredentialError(
            f"environment variable {cfg.api_key_env} is not set for configuration {cfg.id}. "
            "Copy .env.example to .env, fill it in, then: set -a; source .env; set +a")
    return value


def validate_configs(configs: list[ModelConfig], *, require_keys: bool = True) -> dict[str, Any]:
    """Check configuration without calling any API."""
    report: dict[str, Any] = {"checked": len(configs), "missing_keys": [], "warnings": [],
                              "ready": True, "configs": [c.sanitized() for c in configs]}
    for c in configs:
        try:
            resolve_api_key(c)
        except MissingCredentialError as exc:
            report["missing_keys"].append({"id": c.id, "env_var": c.api_key_env,
                                           "hint": str(exc)})
        # A target capped below the recommended floor will truncate a 12–35 KB
        # single-file artifact mid-script. Warn, but do not block: local models
        # may genuinely have smaller context windows.
        if c.role == "target":
            cap = int(c.params.get("max_tokens", TARGET_MAX_TOKENS) or 0)
            if cap < TARGET_MAX_TOKENS_RECOMMENDED_MIN:
                report["warnings"].append(
                    {"id": c.id, "field": "params.max_tokens", "value": cap,
                     "hint": f"below the {TARGET_MAX_TOKENS_RECOMMENDED_MIN} token floor; "
                             f"truncated artifacts are likely. Use {TARGET_MAX_TOKENS}."})
    if require_keys and report["missing_keys"]:
        report["ready"] = False
    return report


@dataclass
class LLMResponse:
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    response_id: str = ""
    dry_run: bool = False
    finish_reason: str = ""   # "length" means the output was cut off by the cap

    def to_dict(self) -> dict[str, Any]:
        return {"content_length": len(self.content), "usage": self.usage,
                "model": self.model, "response_id": self.response_id,
                "dry_run": self.dry_run, "finish_reason": self.finish_reason}


class BaseClient:
    def __init__(self, cfg: ModelConfig, api_key: str = "") -> None:
        self.cfg = cfg
        self._api_key = api_key  # never logged, never serialised

    def chat(self, messages: list[dict[str, str]], **overrides: Any) -> LLMResponse:
        raise NotImplementedError

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers}, method="POST")
        last_error = ""
        for attempt in range(self.cfg.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < self.cfg.max_retries:
                    time.sleep(min(8.0, 2 ** attempt))
                    continue
                # Do not include the request body: it may contain the prompt,
                # and never include headers (Authorization lives there).
                raise ProviderError(f"{self.cfg.id}: {last_error} from {url}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = type(exc).__name__
                if attempt + 1 < self.cfg.max_retries:
                    time.sleep(min(8.0, 2 ** attempt))
                    continue
                raise ProviderError(f"{self.cfg.id}: {last_error} contacting {url}") from exc
        raise ProviderError(f"{self.cfg.id}: exhausted retries ({last_error})")


class OpenAICompatibleClient(BaseClient):
    """POST {base_url}/chat/completions — works with most gateways."""

    def chat(self, messages: list[dict[str, str]], **overrides: Any) -> LLMResponse:
        params = {**self.cfg.params, **overrides}
        body = {"model": self.cfg.model, "messages": messages,
                "temperature": params.get("temperature", 0.7),
                "max_tokens": params.get("max_tokens", TARGET_MAX_TOKENS),
                "top_p": params.get("top_p", 1.0)}
        if params.get("seed") is not None:
            body["seed"] = params["seed"]
        # Optional generation controls, passed through only from a fixed
        # allow-list. Reasoning-style models otherwise spend the whole output
        # budget on hidden tokens and return an empty message. Nothing here can
        # carry a credential.
        for key in ("reasoning_effort", "thinking", "thinking_budget",
                    "frequency_penalty", "presence_penalty", "stop"):
            if params.get(key) is not None:
                body[key] = params[key]
        headers = {"Authorization": f"Bearer {self._api_key}", **self.cfg.extra_headers}
        data = self._post(f"{self.cfg.base_url}/chat/completions", headers, body)
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.cfg.id}: unexpected response shape") from exc
        return LLMResponse(content=content, usage=data.get("usage", {}),
                           model=data.get("model", self.cfg.model),
                           response_id=data.get("id", ""),
                           finish_reason=str(choice.get("finish_reason") or ""))


class AnthropicClient(BaseClient):
    """POST {base_url}/v1/messages with x-api-key and anthropic-version."""

    def chat(self, messages: list[dict[str, str]], **overrides: Any) -> LLMResponse:
        params = {**self.cfg.params, **overrides}
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [{"role": m["role"], "content": m["content"]}
                for m in messages if m["role"] != "system"]
        body: dict[str, Any] = {"model": self.cfg.model, "messages": conv,
                                "max_tokens": params.get("max_tokens", TARGET_MAX_TOKENS),
                                "temperature": params.get("temperature", 0.7)}
        if system:
            body["system"] = system
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01",
                   **self.cfg.extra_headers}
        data = self._post(f"{self.cfg.base_url}/v1/messages", headers, body)
        try:
            content = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"{self.cfg.id}: unexpected response shape") from exc
        return LLMResponse(content=content, usage=data.get("usage", {}),
                           model=data.get("model", self.cfg.model),
                           response_id=data.get("id", ""),
                           finish_reason=str(data.get("stop_reason") or ""))


class DryRunClient(BaseClient):
    """Offline stub. Its output is explicitly non-scoreable."""

    def chat(self, messages: list[dict[str, str]], **overrides: Any) -> LLMResponse:
        return LLMResponse(
            content="<!-- DRY_RUN_PLACEHOLDER: no model was called; not scoreable -->",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.cfg.model, response_id="dry-run", dry_run=True)


CLIENT_REGISTRY = {"openai-compatible": OpenAICompatibleClient, "anthropic": AnthropicClient}


def build_client(cfg: ModelConfig, *, dry_run: bool = False) -> BaseClient:
    if dry_run:
        return DryRunClient(cfg)
    return CLIENT_REGISTRY[cfg.protocol](cfg, resolve_api_key(cfg))
