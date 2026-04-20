"""Extract Continue.dev sessions from ~/.continue/sessions/*.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "continue_dev"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["continue_dev"]["path"])
    if not base.exists():
        return []

    activities: list[Activity] = []
    for f in base.glob("*.json"):
        if f.name == "sessions.json":
            continue
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue

        history = data.get("history") or []
        user_n = sum(1 for h in history if h.get("message", {}).get("role") == "user")
        asst_n = sum(1 for h in history if h.get("message", {}).get("role") == "assistant")
        if user_n + asst_n == 0:
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        snippets = []
        for h in history[:5]:
            msg = h.get("message") or {}
            if msg.get("role") == "user":
                c = msg.get("content") or ""
                if isinstance(c, str):
                    snippets.append(c[:200])
        activities.append(
            Activity(
                source=Source.CONTINUE,
                session_id=data.get("sessionId") or f.stem,
                timestamp_start=mtime,
                timestamp_end=mtime,
                project=data.get("title") or None,
                activity_type=ActivityType.CODING,
                user_prompts_count=user_n,
                tool_calls_count=asst_n,
                summary=" | ".join(snippets)[:500],
                raw_ref=str(f),
            )
        )
    return activities
