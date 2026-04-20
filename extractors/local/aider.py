"""Scan $HOME for `.aider.chat.history.md` files; one Activity per file."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "aider"

HEADER_USER = re.compile(r"^#### .+", re.MULTILINE)
HEADER_ASSISTANT = re.compile(r"^> .+", re.MULTILINE)


def _scan_roots(cfg: dict[str, Any]) -> list[Path]:
    roots = cfg.get("scan", {}).get("roots") or []
    if cfg.get("scan", {}).get("mode") == "full":
        roots = [str(Path.home())]
    return [Path(r) for r in roots]


def extract(cfg: dict[str, Any]) -> list[Activity]:
    excludes = cfg.get("scan", {}).get("exclude_globs") or []
    activities: list[Activity] = []
    seen: set[Path] = set()
    for root in _scan_roots(cfg):
        if not root.exists():
            continue
        for f in root.rglob(".aider.chat.history.md"):
            if f in seen:
                continue
            if any(ex.strip("*") in str(f) for ex in excludes):
                continue
            seen.add(f)
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            user_n = len(HEADER_USER.findall(text))
            asst_n = len(HEADER_ASSISTANT.findall(text))
            if user_n == 0:
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            try:
                ctime = datetime.fromtimestamp(f.stat().st_birthtime, tz=UTC)
            except AttributeError:
                ctime = mtime
            first = next((m for m in HEADER_USER.finditer(text)), None)
            snippet = text[first.start() : first.start() + 300] if first else ""
            activities.append(
                Activity(
                    source=Source.AIDER,
                    session_id=str(f.relative_to(root)) if f.is_relative_to(root) else f.name,
                    timestamp_start=ctime,
                    timestamp_end=mtime,
                    project=str(f.parent),
                    activity_type=ActivityType.CODING,
                    user_prompts_count=user_n,
                    tool_calls_count=asst_n,
                    summary=snippet.replace("\n", " ")[:500],
                    raw_ref=str(f),
                )
            )
    return activities
