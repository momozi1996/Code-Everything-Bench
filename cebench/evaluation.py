"""Run orchestration: config -> generation -> verification -> scoring -> outcomes.

This is the entry point a contributor uses once they have filled in
`config/models.json` and the environment variables named there. It is also the
only place allowed to write rows under `results/`.

Honesty rules enforced here:

* No browser => `evaluation_ready = False` => **no score is written**. Runtime
  assertions return SKIP; converting them to PASS would fabricate a result.
* `dry_run` outputs are never written and never scored.
* `config.json` published with a run is sanitised (no key values).
* Every score in `outcomes.csv` is derived from a committed artifact + trace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import io
from .config import ROOT, load_config
from .generate import generate_one
from .providers import ModelConfig, build_client
from .runner import verify_artifact
from .scoring import score_run
from .trace import Trace, audit_claims

OUTCOME_FIELDS = [
    "config_id", "harness", "model", "task_id", "repetition", "split",
    "track", "pass_at_budget", "final_score", "F", "R", "V", "E",
    "quality_given_pass", "unverified_claims", "claimed_checks",
    "trace_verified_checks", "self_assessed_completion", "l0_pass", "l0_fail",
    "l0_skip", "l1_pass", "l1_fail", "tokens_out", "evaluation_ready",
    "dry_run", "error", "notes",
]


@dataclass
class TaskSpec:
    task_id: str
    prompt: str
    published_at: str | None = None
    split: str = "POST"
    domains: list[str] = field(default_factory=list)
    task_set: str = "core"                 # core | extended
    reference_kind: str = "runnable-html"  # runnable-html | post-only


@dataclass
class RunPlan:
    run_id: str
    track: str = "CE-Frozen"
    mode: str = "Replay"
    split: str = "POST"
    repetitions: int = 3
    seed: int = 2027
    budget: dict[str, Any] = field(default_factory=dict)
    measurements: list[str] = field(default_factory=lambda: ["M1", "M2"])
    task_set: str = "all"
    task_ids: list[str] = field(default_factory=list)
    limit: int | None = None

    @classmethod
    def load(cls, path: str | Path) -> "RunPlan":
        d = load_config(path)
        if not d.get("run_id"):
            raise ValueError("run plan needs a run_id")
        return cls(
            run_id=d["run_id"], track=d.get("track", "CE-Frozen"),
            mode=d.get("mode", "Replay"), split=d.get("split", "POST"),
            repetitions=int(d.get("repetitions", 3)), seed=int(d.get("seed", 2027)),
            budget=d.get("budget", {}), measurements=d.get("measurements", ["M1"]),
            task_set=d.get("task_set", "all"), task_ids=d.get("task_ids") or [],
            limit=d.get("limit"))


def load_prompts(corpus_path: str | Path | None = None,
                 task_ids: Iterable[str] | None = None,
                 split: str = "POST", cutoff: str | None = None) -> list[TaskSpec]:
    """Load verbatim prompts from the pinned corpus (single source of truth).

    Prompts are NOT vendored in this repository. Run `scripts/sync_corpus.py`
    first to materialise `data/corpus/cases.jsonl` locally.
    """
    p = Path(corpus_path) if corpus_path else ROOT / "data" / "corpus" / "cases.jsonl"
    if not p.is_file():
        raise FileNotFoundError(
            f"corpus not found at {p}. Run: python3 scripts/sync_corpus.py --ref <commit-hash>")
    wanted = set(task_ids) if task_ids else None
    out: list[TaskSpec] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            tid = r.get("id")
            if not r.get("prompt") or not (r.get("demoUrl") or "").endswith(".html"):
                continue
            if not r.get("xUrl") or not r.get("publishedAt"):
                continue
            if wanted and tid not in wanted:
                continue
            published = str(r.get("publishedAt") or "")[:10]
            if split in ("POST", "PRE") and cutoff:
                is_post = published > cutoff
                if (split == "POST") != is_post:
                    continue
            out.append(TaskSpec(task_id=tid, prompt=r["prompt"], published_at=published,
                                split=split, domains=r.get("code2Tags") or []))
    return out


def load_prompts_from_packs(task_set: str = "all",
                            task_ids: Iterable[str] | None = None,
                            split: str = "all",
                            tasks_root: str | Path | None = None) -> list[TaskSpec]:
    """Load verbatim prompts from the materialised task packs.

    This is the task source for full-bank runs. Unlike :func:`load_prompts`,
    it does **not** gate on a runnable ``.html`` reference: Extended-set tasks
    are admitted on verbatim-prompt evidence alone. They have
    ``has_reference_oracle=false`` (no reference-as-oracle meta-test), but
    L0/L1 assertions still run against every generated artifact, so the
    generate -> assert -> score chain is complete for all 180 tasks.

    ``task_set``: ``core`` (111, paper's full-measurement census),
    ``extended`` (69), or ``all`` (180). POST/PRE contamination is still
    computed per configuration at run time, never statically here.
    """
    root = Path(tasks_root) if tasks_root else ROOT / "tasks"

    def manifest_ids(name: str) -> list[str]:
        p = root / name
        if not p.is_file():
            return []
        return [t["task_id"] for t in io.read_json(p).get("tasks", [])]

    core = manifest_ids("manifest.json")
    ext = manifest_ids("manifest_extended.json")
    if task_set == "core":
        ids = core
    elif task_set == "extended":
        ids = ext
    elif task_set == "all":
        ids = core + ext
    else:
        raise ValueError(f"unknown task_set {task_set!r}; use core | extended | all")

    wanted = set(task_ids) if task_ids else None
    out: list[TaskSpec] = []
    for tid in ids:
        if wanted and tid not in wanted:
            continue
        pack_dir = root / tid
        prompt_file = pack_dir / "prompt.md"
        meta_file = pack_dir / "task.json"
        if not prompt_file.is_file() or not meta_file.is_file():
            continue
        # Strip the single provenance comment line; everything after it is the
        # verbatim prompt as materialised by scripts/build_task_packs.py.
        text = prompt_file.read_text(encoding="utf-8")
        if text.startswith("<!--"):
            text = text.split("-->", 1)[-1]
        prompt = text.strip()
        if not prompt:
            continue
        meta = io.read_json(meta_file)
        published = str(meta.get("published_at") or "")[:10] or None
        out.append(TaskSpec(
            task_id=tid, prompt=prompt, published_at=published, split=split,
            domains=meta.get("code2_tags") or [],
            task_set=meta.get("set") or ("core" if tid in core else "extended"),
            reference_kind=meta.get("reference_kind") or "post-only",
        ))
    return out


def build_observation(gen, verification: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Translate generation + assertion evidence into Gate/Rubric inputs."""
    l0 = verification.get("l0", [])
    l1 = verification.get("l1", [])
    l1_auto = [r for r in l1 if r.get("status") in ("PASS", "FAIL")
               and r.get("id", "").startswith("L1")]
    interaction_ok = bool(l1_auto) and all(r["status"] == "PASS" for r in l1_auto)

    note_text = ". ".join(gen.delivery_note.claimed_checks)
    trace = Trace.from_records(gen.config_id, gen.task_id, gen.trace_events)
    audit = audit_claims(note_text, trace)
    ready = bool(verification.get("evaluation_ready"))

    obs = {
        "loads": bool(gen.artifact_html),
        "core_interaction_ok": interaction_ok,
        "unverified_claims": audit["unverified_claims"],
        "unverified_claims_audit": audit,
        "forbidden_shortcut": any(r.get("status") == "FAIL" and
                                  "shortcut" in r.get("name", "").lower() for r in l0 + l1),
        "has_deliverable": bool(gen.artifact_html),
        "core_interaction_degraded": False,
        "cost": {"tokens_out": gen.usage.get("completion_tokens", 0)},
    }
    return obs, ready


def run_evaluation(configs: list[ModelConfig], plan: RunPlan, tasks: list[TaskSpec],
                   *, dry_run: bool = False, out_root: str | Path | None = None,
                   verbose: bool = True) -> list[dict[str, Any]]:
    """Execute M1 for every (task, configuration, repetition)."""
    base = Path(out_root) if out_root else ROOT / "results" / plan.run_id
    if not dry_run:
        base.mkdir(parents=True, exist_ok=True)
        io.write_json(base / "config.json", {
            "run_id": plan.run_id, "track": plan.track, "mode": plan.mode,
            "split": plan.split, "repetitions": plan.repetitions, "seed": plan.seed,
            "budget": plan.budget, "measurements": plan.measurements,
            "task_count": len(tasks),
            "configurations": [c.sanitized() for c in configs],
            "note": "API keys are referenced by environment-variable name only; "
                    "no credential value is stored in this file.",
        })

    rows: list[dict[str, Any]] = []
    # Only "target" configurations generate artifacts. A "judge" configuration
    # scores L2 visual reviews and must never be asked to build the artifact.
    target_configs = [c for c in configs if getattr(c, "role", "target") == "target"]
    if not target_configs:
        raise ValueError("no target configuration to evaluate (all entries are role=judge)")
    for cfg in target_configs:
        client = build_client(cfg, dry_run=dry_run)
        for task in tasks:
            # POST/PRE is computed per (task, configuration), not by filtering
            # the task bank: a task published after one model's cutoff may be
            # PRE for a newer model. Filtering globally would lose tasks.
            # A dry run has no publication date and no real split; it must be
            # exempt from the filter, otherwise the rehearsal silently executes
            # zero generations and still looks successful.
            effective_split = ("DRY-RUN" if dry_run else
                               "POST" if (task.published_at or "") > cfg.training_cutoff
                               else "PRE")
            if (not dry_run and plan.split in ("POST", "PRE")
                    and effective_split != plan.split):
                continue
            for rep in range(1, plan.repetitions + 1):
                seed = plan.seed + rep * 1000 + abs(hash(cfg.id + task.task_id)) % 10000
                gen = generate_one(
                    client, task.task_id, task.prompt, cfg.id, rep, plan.budget,
                    seed=seed, out_dir=None if dry_run else base)
                row = _score_one(cfg, plan, task, rep, gen, dry_run,
                                 split=effective_split)
                rows.append(row)
                if verbose:
                    state = ("DRY-RUN" if dry_run else
                             "NO-BROWSER" if not row["evaluation_ready"] else
                             "PASS" if row["pass_at_budget"] else "FAIL")
                    print(f"  [{state:10s}] {cfg.id} / {task.task_id} / r{rep}  {row['error'] or ''}")
    if not dry_run:
        io.write_csv(base / "outcomes.csv", rows, OUTCOME_FIELDS)
        print(f"wrote {base / 'outcomes.csv'} ({len(rows)} rows)")
    return rows


def _score_one(cfg: ModelConfig, plan: RunPlan, task: TaskSpec, rep: int,
               gen, dry_run: bool, *, split: str = "POST") -> dict[str, Any]:
    row: dict[str, Any] = {k: "" for k in OUTCOME_FIELDS}
    row.update({"config_id": cfg.id, "harness": cfg.harness, "model": cfg.model,
                "task_id": task.task_id, "repetition": rep, "split": split,
                "track": plan.track, "dry_run": dry_run,
                "tokens_out": gen.usage.get("completion_tokens", 0),
                "self_assessed_completion": gen.delivery_note.self_assessed_completion or "",
                "error": gen.error, "evaluation_ready": False})
    if not gen.scoreable:
        row["notes"] = "dry_run or no artifact: intentionally not scored"
        return row

    # The task pack directory must be passed in, otherwise the task-specific L1
    # assertions are never loaded and every score rests on L0 alone.
    task_dir = ROOT / "tasks" / task.task_id
    verification = verify_artifact(gen.artifact_path,
                                   task_dir if task_dir.is_dir() else None,
                                   use_browser=None)
    obs, ready = build_observation(gen, verification)
    l0s, l1s = verification["l0_summary"], verification["l1_summary"]
    row.update({
        "l0_pass": l0s["passed"], "l0_fail": l0s["failed"], "l0_skip": l0s["skipped"],
        "l1_pass": l1s.get("passed", 0), "l1_fail": l1s.get("failed", 0),
        "claimed_checks": obs["unverified_claims_audit"]["claimed_checks"],
        "trace_verified_checks": obs["unverified_claims_audit"]["trace_verified_checks"],
        "unverified_claims": obs["unverified_claims"],
    })
    if not ready:
        row["notes"] = "runtime assertions SKIP (no pinned browser): no score written"
        return row

    from .assertions.base import AssertionResult
    results = [AssertionResult(id=r["id"], name=r["name"], tier=r["tier"],
                               status=r["status"], dimension=r.get("dimension", "F"))
               for r in verification["l0"] + verification["l1"]]
    s = score_run(task.task_id, cfg.id, obs, results)
    row.update({
        "evaluation_ready": True,
        "pass_at_budget": s.pass_at_budget, "final_score": round(s.final_score, 4),
        "quality_given_pass": round(s.quality_score.final, 4) if s.pass_at_budget else "",
        "F": s.quality_score.dimensions["F"] or "", "R": s.quality_score.dimensions["R"] or "",
        "V": s.quality_score.dimensions["V"] or "", "E": s.quality_score.dimensions["E"] or "",
        "notes": ";".join(s.gate.vetoes) if s.gate.vetoes else "delivered",
    })
    return row


def m2_contract() -> dict[str, Any]:
    """M2 interface (verification). Implementation lands after the M1 pipeline
    is validated; the contract is fixed now so contributors can prepare."""
    return {
        "input": "reference HTML with 1-5 injected defects from cebench.defect.apply_mutations",
        "ground_truth": "the exact applied-defect records; no hidden rubric",
        "task": "model inspects the artifact and returns a defect list",
        "metrics": ["precision", "recall", "F1", "accuracy when answering 'no defects'"],
        "difficulty": "number of applied defects (IRT ladder)",
        "status": "interface defined; runner pending",
    }
