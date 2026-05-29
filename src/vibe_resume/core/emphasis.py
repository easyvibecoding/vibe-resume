"""Emphasis lever: a file-based重點控制 that rides the enrich bias stack and
the render ranking. `_emphasis.yaml` is human-editable; enrich injects it as
the highest-priority bias block, render boosts/penalizes ranked groups."""
from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel

from vibe_resume.core.paths import user_root

EMPHASIS_PATH = user_root() / "data" / "cache" / "_emphasis.yaml"
_BOOST = 10_000   # dominates _rank_score (sessions + achievements*5 + breadth*2)


class EmphasisRecord(BaseModel):
    version: int = 1
    intent: str = ""
    keywords: list[str] = []
    bias_instruction: str = ""
    spotlight: list[str] = []
    demote: list[str] = []


def load_emphasis(cfg: dict[str, Any] | None = None) -> EmphasisRecord | None:
    """Return the active emphasis, or None when disabled / absent / unreadable.
    `cfg.emphasis.enabled = false` (or the --no-emphasis flag, which sets it)
    suppresses the lever without deleting the file."""
    if cfg is not None and not cfg.get("emphasis", {}).get("enabled", True):
        return None
    if not EMPHASIS_PATH.exists():
        return None
    try:
        return EmphasisRecord(**(yaml.safe_load(EMPHASIS_PATH.read_text()) or {}))
    except Exception:
        return None


def write_emphasis(intent: str) -> EmphasisRecord:
    """Set `intent`, carry forward any hand-edited keywords/spotlight/demote."""
    existing = None
    if EMPHASIS_PATH.exists():
        try:
            existing = EmphasisRecord(**(yaml.safe_load(EMPHASIS_PATH.read_text()) or {}))
        except Exception:
            existing = None
    rec = existing or EmphasisRecord()
    rec.intent = intent
    EMPHASIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMPHASIS_PATH.write_text(yaml.safe_dump(rec.model_dump(), sort_keys=False, allow_unicode=True))
    return rec


def clear_emphasis() -> bool:
    if EMPHASIS_PATH.exists():
        EMPHASIS_PATH.unlink()
        return True
    return False


def rank_delta(name: str, emphasis: EmphasisRecord | None) -> int:
    if emphasis is None:
        return 0
    if name in emphasis.spotlight:
        return _BOOST
    if name in emphasis.demote:
        return -_BOOST
    return 0


def emphasis_block(emphasis: EmphasisRecord) -> str:
    kw = ", ".join(emphasis.keywords) if emphasis.keywords else "(none)"
    return (
        "\n\nHIGHEST-PRIORITY EMPHASIS — the candidate wants this résumé to "
        f"foreground:\n{emphasis.intent}\n"
        f"Surface these themes/keywords where the raw activity supports them "
        f"(never invent): {kw}\n"
        f"{emphasis.bias_instruction}\n"
        "This emphasis overrides earlier framing on tie-breaks; do not fabricate "
        "to satisfy it.\n"
    )
