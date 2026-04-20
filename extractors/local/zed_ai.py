"""Zed AI threads from ~/.local/share/zed/threads/ or ~/.config/zed/conversations/."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "zed"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    candidates = [
        Path("~/.local/share/zed/threads").expanduser(),
        Path("~/.config/zed/conversations").expanduser(),
        Path("~/Library/Application Support/Zed/threads").expanduser(),
    ]
    activities: list[Activity] = []
    for base in candidates:
        if not base.exists():
            continue
        for f in list(base.rglob("*.json")):
            try:
                data = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            messages = data.get("messages") if isinstance(data, dict) else None
            if not messages:
                continue
            user_n = sum(1 for m in messages if m.get("role") == "user")
            asst_n = sum(1 for m in messages if m.get("role") == "assistant")
            if user_n + asst_n == 0:
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            activities.append(
                Activity(
                    source=Source.ZED,
                    session_id=data.get("id") or f.stem,
                    timestamp_start=mtime,
                    timestamp_end=mtime,
                    activity_type=ActivityType.CODING,
                    user_prompts_count=user_n,
                    tool_calls_count=asst_n,
                    summary=str(data.get("title", ""))[:200],
                    raw_ref=str(f),
                )
            )
    return activities
