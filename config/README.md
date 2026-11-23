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
| `training_cutoff` | ISO date; used for POST/PRE contamination splits | ✅ |
| `params` | `temperature`, `max_tokens`, `top_p`, `seed` overrides | optional |
| `extra_headers` | Additional request headers for custom gateways | optional |

Add or remove entries freely. A configuration is **harness × model**, not a bare
model — the same model under two harnesses is two rows, because the L2
interface changes what the agent can observe.

## 4. Validate before spending money

```bash
python3 scripts/run_evaluation.py --check         # schema + no literal keys + env vars present
python3 scripts/run_evaluation.py --dry-run       # full pipeline, no network, no results written
python3 scripts/run_evaluation.py --task case-085 --limit 1   # one real task first
python3 scripts/run_evaluation.py                 # full 180 x N x repetitions batch (all)
python3 scripts/run_evaluation.py --task-set core  # paper census: 111 tasks
python3 scripts/run_evaluation.py --task-set extended  # 69 label-balanced tasks
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
