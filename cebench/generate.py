"""M1 generation: turn a verbatim community prompt into a delivered artifact.

Information-boundary rule (paper §3.2): the system message describes the **L2
interface and delivery format only**. It must NOT reveal the L0 assertions, the
Gate rules or the rubric — the configuration observes `(p, ℰ)` but never `ρ`.
Revealing the checklist would turn the benchmark into instruction-following.

The delivery note is framed as an ordinary hand-off (RQ5), not as a quiz, so a
model does not become systematically conservative because it knows its
calibration is being scored.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .providers import BaseClient, LLMResponse
from .trace import DeliveryNote

SYSTEM_PROMPT = """You are delivering a product to a real user.

ENVIRONMENT
- The deliverable is ONE self-contained HTML file. It will be opened directly
  with file:// in a pinned Chromium, offline, at desktop and phone widths.
- You may inspect your own artifact in a browser: screenshots, console output,
  network errors and build logs. You may write and run your own checks.
- You cannot browse the internet, and you cannot see any original demo.

DELIVERABLE
1. A single HTML file containing everything it needs (CSS and JS inline).
2. A short hand-off note with these three fields, as JSON inside a
   ```json block tagged CEBENCH_DELIVERY:
     {"self_assessed_completion": <0..100>,
      "weak_points": ["...", "...", "..."],
      "claimed_checks": ["..."]}
   `weak_points` = the three functional areas you are least confident about.
   `claimed_checks` = checks you actually performed, each with its observation.

BUDGET
A wall-clock limit, a maximum number of repair rounds and a token cap apply.
Deliver the best artifact you can within them. If a requirement could not be
met, say so in the hand-off note rather than implying success.
"""

_CODE_FENCE = re.compile(r"```(?:html|HTML)?\s*(<!doctype[\s\S]*?)```", re.I)
_DOCTYPE = re.compile(r"<!doctype\s+html[\s\S]*", re.I)
_DELIVERY = re.compile(r"CEBENCH_DELIVERY\s*(\{[\s\S]*?\})", re.I)
_JSON_FENCE = re.compile(r"```json\s*(\{[\s\S]*?\})\s*```", re.I)


def build_messages(prompt: str, task_id: str, budget: dict[str, Any]) -> list[dict[str, str]]:
    user = (f"TASK ID: {task_id}\n\nUSER REQUEST (verbatim, do not rewrite):\n"
            f"{prompt}\n\nBUDGET: {json.dumps(budget, ensure_ascii=False)}\n\n"
            "Return the HTML first, then the CEBENCH_DELIVERY note.")
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def extract_html(text: str) -> str | None:
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip()
    m = _DOCTYPE.search(text)
    if m:
        # Cut anything after the closing html tag so prose is not delivered as code.
        chunk = m.group(0)
        end = re.search(r"</html\s*>", chunk, re.I)
        return (chunk[:end.end()] if end else chunk).strip()
    return None


def extract_delivery_note(text: str) -> DeliveryNote:
    raw = None
    m = _DELIVERY.search(text)
    if m:
        raw = m.group(1)
    else:
        for block in _JSON_FENCE.findall(text):
            try:
                obj = json.loads(block)
            except json.JSONDecodeError:
                continue
            if "self_assessed_completion" in obj or "weak_points" in obj:
                raw = block
                break
    if not raw:
        return DeliveryNote()  # absent note is not an invented note
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return DeliveryNote()
    score = obj.get("self_assessed_completion")
    try:
        score = float(score) / 100.0 if score is not None else None
    except (TypeError, ValueError):
        score = None
    return DeliveryNote(
        self_assessed_completion=score,
        weak_points=[str(x) for x in (obj.get("weak_points") or [])][:3],
        claimed_checks=[str(x) for x in (obj.get("claimed_checks") or [])],
    )


@dataclass
class GenerationResult:
    task_id: str
    config_id: str
    repetition: int
    artifact_html: str | None
    delivery_note: DeliveryNote
    usage: dict[str, Any]
    dry_run: bool = False
    error: str = ""
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    artifact_path: str | None = None

    @property
    def scoreable(self) -> bool:
        return bool(self.artifact_html) and not self.dry_run and not self.error

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "config_id": self.config_id,
                "repetition": self.repetition, "scoreable": self.scoreable,
                "dry_run": self.dry_run, "error": self.error,
                "usage": self.usage, "artifact_path": self.artifact_path,
                "self_assessed_completion": self.delivery_note.self_assessed_completion,
                "weak_points": self.delivery_note.weak_points,
                "claimed_checks": self.delivery_note.claimed_checks}


def generate_one(client: BaseClient, task_id: str, prompt: str, config_id: str,
                 repetition: int, budget: dict[str, Any], *, seed: int | None = None,
                 out_dir: str | Path | None = None) -> GenerationResult:
    """One (task, configuration, repetition) generation.

    `out_dir=None` (dry run) means nothing is written. Dry-run artifacts are
    never scoreable, so a rehearsal cannot silently become a published result.
    """
    messages = build_messages(prompt, task_id, budget)
    events: list[dict[str, Any]] = [
        {"step": 0, "action": "file_read", "target": task_id,
         "observation": f"prompt of {len(prompt)} chars loaded"},
        {"step": 1, "action": "browser_open", "target": "request",
         "observation": f"configuration={config_id} repetition={repetition} seed={seed}"},
    ]
    try:
        response: LLMResponse = client.chat(messages, seed=seed)
    except Exception as exc:  # provider errors are recorded, never swallowed
        return GenerationResult(task_id, config_id, repetition, None, DeliveryNote(),
                                {}, error=f"{type(exc).__name__}: {exc}",
                                trace_events=events)
    events.append({"step": 2, "action": "console_read", "target": "response",
                   "observation": json.dumps(response.to_dict(), ensure_ascii=False)})
    html = extract_html(response.content)
    note = extract_delivery_note(response.content)
    result = GenerationResult(
        task_id=task_id, config_id=config_id, repetition=repetition,
        artifact_html=html, delivery_note=note, usage=response.usage,
        dry_run=response.dry_run, trace_events=events,
        # The offline stub deliberately emits no HTML. Recording that as a
        # provider error would make a healthy rehearsal look like a failure.
        error="" if (html or response.dry_run) else
              "no HTML artifact found in model response")

    if out_dir is not None and not response.dry_run and html:
        base = Path(out_dir)
        (base / "artifacts").mkdir(parents=True, exist_ok=True)
        (base / "traces").mkdir(parents=True, exist_ok=True)
        (base / "delivery_notes").mkdir(parents=True, exist_ok=True)
        stem = f"{config_id}__{task_id}__r{repetition}"
        art = base / "artifacts" / f"{stem}.html"
        art.write_text(html, encoding="utf-8")
        (base / "delivery_notes" / f"{stem}.md").write_text(
            json.dumps({"self_assessed_completion": note.self_assessed_completion,
                        "weak_points": note.weak_points,
                        "claimed_checks": note.claimed_checks},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        events.append({"step": 3, "action": "assertion_run", "target": "deliverable",
                       "observation": f"artifact written: {art.name}"})
        (base / "traces" / f"{stem}.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
            encoding="utf-8")
        result.artifact_path = str(art)
        result.trace_events = events
    return result
