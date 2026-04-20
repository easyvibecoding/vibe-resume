"""Best-effort Windsurf/Cascade extractor.

Path: ~/.codeium/windsurf/cascade/. File layout varies across Windsurf releases;
we recursively look for JSON/JSONL with message/conversation structure.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source
from extractors.base import iter_jsonl

NAME = "windsurf"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["windsurf"]["path"])
    if not base.exists():
        return []
    activities: list[Activity] = []

    for f in list(base.rglob("*.jsonl")) + list(base.rglob("*.json")):
        try:
            if f.suffix == ".jsonl":
                entries = list(iter_jsonl(f))
            else:
                raw = json.loads(f.read_text())
                entries = raw if isinstance(raw, list) else [raw]
        except (OSError, json.JSONDecodeError):
            continue

        user_n = 0
        asst_n = 0
        for e in entries:
            if not isinstance(e, dict):
                continue
            role = e.get("role") or e.get("message_type") or ""
            if "user" in str(role).lower():
                user_n += 1
            elif "assist" in str(role).lower() or "ai" in str(role).lower():
                asst_n += 1

        if user_n + asst_n == 0:
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        activities.append(
            Activity(
                source=Source.WINDSURF,
                session_id=f.stem,
                timestamp_start=mtime,
                timestamp_end=mtime,
                activity_type=ActivityType.CODING,
                user_prompts_count=user_n,
                tool_calls_count=asst_n,
                raw_ref=str(f),
            )
        )
    return activities
