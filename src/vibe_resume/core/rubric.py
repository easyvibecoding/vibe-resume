"""Bundled, cited AI-proficiency market rubric (consumed by enrich + review).

The bundled baseline lives next to this module as ``market_rubric.yaml``.
A user-cache copy at ``<user_root>/data/cache/market_rubric.yaml`` (written by
the #46 research pass) takes precedence when present and parseable. All fields
degrade to empty/safe defaults so a malformed rubric never crashes the pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from vibe_resume.core.paths import user_root as _user_root

_BUNDLED = Path(__file__).with_name("market_rubric.yaml")
_STALE_DAYS = 180


@dataclass(frozen=True)
class YellowFlag:
    kind: str
    pattern: str
    why: str

    @property
    def regex(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


@dataclass(frozen=True)
class MarketRubric:
    version: int = 0
    refreshed_at: str | None = None
    source_note: str = ""
    sources: tuple[dict[str, str], ...] = ()
    bullet_formula: str = ""
    agentic_keywords: list[str] = field(default_factory=list)
    ai_tool_names: list[str] = field(default_factory=list)
    human_gate_verbs: list[str] = field(default_factory=list)
    human_gate_verbs_by_locale: dict[str, list[str]] = field(default_factory=dict)
    senior_differentiators: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    yellow_flags: tuple[YellowFlag, ...] = ()
    metric_hints: dict[str, list[str]] = field(default_factory=dict)

    def is_stale(self, *, as_of: date | None = None) -> bool:
        if not self.refreshed_at:
            return False
        try:
            ref = date.fromisoformat(self.refreshed_at)
        except ValueError:
            return False
        today = as_of or date.today()
        return (today - ref).days > _STALE_DAYS


def _coerce(data: dict[str, Any]) -> MarketRubric:
    yfs = tuple(
        YellowFlag(
            kind=str(y.get("kind", "")),
            pattern=str(y.get("pattern", "")),
            why=str(y.get("why", "")),
        )
        for y in (data.get("yellow_flag_patterns") or [])
        if isinstance(y, dict) and y.get("pattern")
    )
    return MarketRubric(
        version=int(data.get("version", 0) or 0),
        refreshed_at=(str(data["refreshed_at"]) if data.get("refreshed_at") else None),
        source_note=str(data.get("source_note") or ""),
        sources=tuple(data.get("sources") or ()),
        bullet_formula=str(data.get("bullet_formula") or ""),
        agentic_keywords=list(data.get("agentic_keywords") or []),
        ai_tool_names=list(data.get("ai_tool_names") or []),
        human_gate_verbs=list(data.get("human_gate_verbs") or []),
        human_gate_verbs_by_locale={
            str(k): list(v)
            for k, v in (data.get("human_gate_verbs_by_locale") or {}).items()
        },
        senior_differentiators=list(data.get("senior_differentiators") or []),
        anti_patterns=list(data.get("anti_patterns") or []),
        yellow_flags=yfs,
        metric_hints={
            str(k): list(v) for k, v in (data.get("metric_hints") or {}).items()
        },
    )


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


@lru_cache(maxsize=1)
def load_rubric() -> MarketRubric:
    override = _user_root() / "data" / "cache" / "market_rubric.yaml"
    if override.exists():
        data = _read(override)
        if data is not None:
            return _coerce(data)
    return _coerce(_read(_BUNDLED) or {})
