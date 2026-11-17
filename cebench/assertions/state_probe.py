"""Harness-side runtime state probe.

Why harness-side: the reference implementations are third-party artifacts and
under-test models will not cooperate by exposing `window.__state`. Requiring
such an interface would change the task itself. The evaluator therefore injects
observation code after loading the artifact and infers state from the outside.

Evidence grades (paper §5.3):
    E1  explicit state read   — global variable / exposed object found
    E2  behavioural inference — interaction produces a measurable state delta
    E3  pixel sampling        — canvas hash before/after interaction (weakest)

Motivation: DOM-based scoring was measured to be nearly uncorrelated with true
runtime state correctness in WorldCoder-Bench (Kendall tau_b = -0.02), and
WorldBench's mutation test showed code-only judges still award full credit
after a feature is deleted. A DOM node existing is not evidence of behaviour.
"""

from __future__ import annotations

from typing import Any

# Injected into the page after load. Read-only: it must not alter the artifact.
PROBE_JS = r"""
(() => {
  const out = { globals: [], canvases: [], listeners: [], audio: 0, raf: 0, errors: [] };
  const SKIP = new Set(['__cebench_probe__']);
  for (const k of Object.keys(window)) {
    if (SKIP.has(k)) continue;
    let v; try { v = window[k]; } catch (e) { continue; }
    const t = typeof v;
    if (t === 'object' && v !== null || t === 'number' || t === 'string' || t === 'boolean') {
      if (t === 'object' && v instanceof HTMLElement) continue;
      let brief;
      try { brief = JSON.stringify(v).slice(0, 400); } catch (e) { brief = String(v).slice(0, 120); }
      out.globals.push({ key: k, type: t, value: brief });
    }
  }
  document.querySelectorAll('canvas').forEach((c, i) => {
    let hash = null;
    try {
      const ctx = c.getContext('2d');
      if (ctx) {
        const d = ctx.getImageData(0, 0, Math.min(c.width, 64), Math.min(c.height, 64)).data;
        let h = 0; for (let j = 0; j < d.length; j += 97) h = ((h * 31) + d[j]) | 0;
        hash = h >>> 0;
      }
    } catch (e) { /* webgl / tainted canvas */ }
    out.canvases.push({ index: i, width: c.width, height: c.height, hash2d: hash });
  });
  out.audio = (window.__probeAudioCount || 0);
  out.raf = (window.__probeRafCount || 0);
  return out;
})()
"""

# Injected BEFORE the artifact's own scripts, to count API usage without
# changing semantics. Kept minimal on purpose: a heavy patch would itself
# become a confound.
INIT_JS = r"""
(() => {
  window.__probeAudioCount = 0; window.__probeRafCount = 0;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (AC) {
    const Wrapped = class extends AC { constructor(...a) { super(...a); window.__probeAudioCount++; } };
    try { window.AudioContext = Wrapped; } catch (e) {}
  }
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => { window.__probeRafCount++; return raf(cb); };
})()
"""


def infer_evidence_grade(before: dict[str, Any], after: dict[str, Any]) -> str:
    """Grade the strength of a state observation from a pre/post probe pair."""
    g_before = {g["key"]: g.get("value") for g in before.get("globals", [])}
    g_after = {g["key"]: g.get("value") for g in after.get("globals", [])}
    if any(g_after.get(k) != v for k, v in g_before.items()):
        return "E1"
    c_before = [c.get("hash2d") for c in before.get("canvases", [])]
    c_after = [c.get("hash2d") for c in after.get("canvases", [])]
    if c_before != c_after and any(x is not None for x in c_after):
        return "E3"
    if before.get("raf") != after.get("raf") or before.get("audio") != after.get("audio"):
        return "E2"
    return "E0"  # no observable state change: NOT evidence of correctness


def probe(page: Any) -> dict[str, Any]:
    """Run the injected probe and return its observation dict."""
    try:
        return page.evaluate(PROBE_JS)
    except Exception as exc:
        return {"error": str(exc), "globals": [], "canvases": [], "listeners": [],
                "audio": 0, "raf": 0}
