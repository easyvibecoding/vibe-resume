"""Subagent model-tier policy (#60) — quota-pool isolation across fan-outs.

Any tool-spawned subagent fan-out (codebase scan #59, subprocess enrich,
score-driven iterate #57, future parallel passes) should pick its model tier by
**quota-pool isolation + sufficiency**, not a hardcoded "cheapest":

- Orchestrator on **Opus** → subagents on **Sonnet** (separate, far-cheaper pool;
  more than capable for these summarize/rewrite tasks) — protects the Opus budget.
- Session already on **Sonnet** → keep Sonnet (no downgrade).
- **Haiku** only when the task is trivial and minimum cost is explicitly chosen.

The CLI can't reliably introspect the orchestrator's live tier, so the safe
default sub-tier is **Sonnet** (covers Opus→Sonnet and Sonnet→Sonnet; Haiku is
opt-in). Purely operational (#51 untouched — it changes *which model* does
grounded work, never *what* may be claimed).
"""
from __future__ import annotations

from typing import Any

DEFAULT_SUBAGENT_MODEL = "sonnet"


def resolve_subagent_model(
    cfg: dict[str, Any] | None,
    command: str | None = None,
    explicit: str | None = None,
) -> str:
    """Resolve the subagent model tier: explicit flag > per-command config >
    global `agents.subagent_model` > default (sonnet)."""
    if explicit:
        return explicit
    cfg = cfg or {}
    if command:
        cmd_val = (cfg.get(command) or {}).get("subagent_model")
        if cmd_val:
            return str(cmd_val)
    glob = (cfg.get("agents") or {}).get("subagent_model")
    return str(glob) if glob else DEFAULT_SUBAGENT_MODEL
