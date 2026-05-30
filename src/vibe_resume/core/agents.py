"""Subagent model-tier policy (#60) + fan-out concurrency guidance (#61).

Tool-spawned subagent fan-outs (codebase scan #59, subprocess enrich, future
parallel passes) pick a model tier, defaulting to **Sonnet**:

- Sonnet has its own **weekly quota pool** (since 2025-11-24, distinct from Opus,
  with more headroom), so an Opus session benefits from drawing fan-out work from
  the Sonnet weekly pool. That is a real, verified reason to default to Sonnet.
- Session already on Sonnet → keep Sonnet. **Haiku** only when explicitly chosen.

**Important correction (#61):** tier choice picks *which weekly pool* you draw
from — it does **NOT** grant rate-limit isolation. The 429s seen on wide fan-outs
were **per-minute rate limits (RPM/ITPM/OTPM) tripped by uncapped concurrency**,
which hit regardless of tier or remaining weekly quota. The real mitigation is
**capping concurrency + exponential backoff honoring `retry-after`**, not the tier
choice. Process fan-outs in small batches (`FANOUT_CONCURRENCY`).

Purely operational (#51 untouched — it changes *which model* / *how many at once*,
never *what* may be claimed).
"""
from __future__ import annotations

from typing import Any

DEFAULT_SUBAGENT_MODEL = "sonnet"

# Recommended max concurrent subagents per fan-out batch (#61). Uncapped
# concurrency — not the tier — is what trips per-minute 429s; process scan/enrich
# fan-outs in batches this size with backoff. Mirrors Anthropic's guidance to
# lower CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY for high-volume runs.
FANOUT_CONCURRENCY = 5


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
