# Filling in your model API credentials

Everything here is a **template**. Real keys and real model configurations are
never committed. You supply them locally at run time.

## 1. Copy the templates

```bash
cp config/models.example.json config/models.json   # git-ignored
cp config/run.example.json   config/run.json       # git-ignored
cp .env.example              .env                  # git-ignored
```

## 2. Edit `.env`

Set only the variables you need. The name must match `api_key_env` in
`config/models.json`.

```bash
set -a; source .env; set +a
```

## 3. Edit `config/models.json`

| Field | Meaning | Required |
|---|---|---|
| `id` | Stable configuration ID used as the leaderboard row key | ✅ |
| `protocol` | `openai-compatible` or `anthropic` | ✅ |
| `base_url` | Endpoint root. OpenAI-style roots end in `/v1`; Anthropic roots do not | ✅ |
| `api_key_env` | **Name** of the environment variable holding the key (never the key itself) | ✅ |
| `model` | Exact model/version string. Record it verbatim — a floating alias is not reproducible | ✅ |
| `harness` | `single-shot-l2` / `agent-harness-l2` / your own identifier | ✅ |
| `harness_impl` | Concrete implementation behind `harness`, e.g. `mini-swe-agent` for `agent-harness-l2`. Defaults to the `harness` value | optional |
| `harness_version` | Exact pinned release of the implementation — a floating tag / `latest` is not reproducible | optional but strongly recommended |
| `training_cutoff` | ISO date; used for POST/PRE contamination splits | ✅ |
| `params` | `temperature`, `max_tokens`, `top_p`, `seed` overrides | optional |
| `params.max_tokens` | **512000 for every target** (judge: 8192). Must match `budget.max_output_tokens` in the run plan and `TARGET_MAX_TOKENS` in `cebench/config.py`. A target below 512000 triggers a validation warning: a truncated single-file artifact is scored as `artifact_does_not_load`. `finish_reason=length` is recorded in `outcomes.csv` as `truncated`. | ✅ for targets |
| `extra_headers` | Additional request headers for custom gateways | optional |
| `timeout_seconds` / `max_retries` | Per-entry overrides of the `defaults` values | optional |

**v0.7 (2026-11-24):** the target cap was raised 96k → **512k** and the per-request
timeout to **3600 s**; cost is explicitly not a constraint for the full batch, the
priority is that all 258 tasks can deliver a complete artifact. The cap is a ceiling,
not a target — models normally stop far earlier. If a provider rejects a 512k
`max_tokens` (some expose a smaller hard limit), override `params.max_tokens` for
that one model and record the deviation in the run plan. Published `results/<run-id>/config.json`
snapshots from earlier runs keep their historical 96k value and are never rewritten.

Add or remove entries freely. A configuration is **harness × model**, not a bare
model — the same model under two harnesses is two rows, because the L2
interface changes what the agent can observe. The harness policy (see
`docs/harness-matrix.md`) runs **two parallel regimes**: Regime 1, every model
under `single-shot-l2`; Regime 2, every model under one pinned
`agent-harness-l2` implementation (`mini-swe-agent`). Inside a regime the
harness value is constant so leaderboard differences are attributable to the
model; the two regimes produce two separate leaderboards that are never merged.

## 4. Validate before spending money

```bash
python3 scripts/run_evaluation.py --check         # schema + no literal keys + env vars present
python3 scripts/run_evaluation.py --dry-run       # full pipeline, no network, no results written
python3 scripts/run_evaluation.py --task case-085 --limit 1   # one real task first
python3 scripts/run_evaluation.py                 # full 258 x N x repetitions batch (all)
python3 scripts/run_evaluation.py --task-set core  # paper census: 111 tasks
python3 scripts/run_evaluation.py --task-set extended  # 147 extended tasks
```

`--check` never calls an API. `--dry-run` uses a stub client whose output is
explicitly marked `dry_run: true`; such artifacts are **not scoreable** and are
never written under `results/`. This is deliberate: a benchmark that measures
unverified claims must not create fake ones during development.

## 5. What gets published

When you publish a run, `results/<run-id>/config.json` is written in
**sanitised** form: model IDs, versions, harnesses, seeds, budgets and cutoff
dates are recorded; `api_key_env` names are kept but key values are never
serialised. Anyone can then reproduce the run by supplying their own key.

## Security rules

- A literal key in `config/models.json` is rejected by validation.
- `.env`, `config/models.json`, `config/run.json` are git-ignored.
- Request/response bodies in traces contain prompts and outputs only; the
  `Authorization` header is never logged.
- Use a **restricted-key** with a spending cap for large batches.

See `cebench/providers.py` for the client contract and `docs/reproducibility.md`
for the full reproduction contract.
