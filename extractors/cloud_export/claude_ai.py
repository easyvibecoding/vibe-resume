"""Claude.ai export ZIP importer.

Drop exported .zip into data/imports/claude/. We read `conversations.json`
(array) and optionally `projects.json`.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from core.schema import Activity, ActivityType, Source

NAME = "claude_ai"


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _locate(root: Path, name: str) -> Iterator[Path]:
    for p in root.rglob(name):
        yield p
    for z in root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(z) as zf:
                if any(n.endswith(name) for n in zf.namelist()):
                    out = z.parent / z.stem
                    out.mkdir(exist_ok=True)
                    zf.extractall(out)
                    for p in out.rglob(name):
                        yield p
        except (zipfile.BadZipFile, OSError):
            continue


def extract(cfg: dict[str, Any]) -> list[Activity]:
    import_dir = Path(cfg["extractors"]["cloud_claude_ai"]["import_dir"])
    if not import_dir.exists():
        return []
    activities: list[Activity] = []
    for conv_file in _locate(import_dir, "conversations.json"):
        try:
            data = json.loads(conv_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, list):
            continue
        for conv in data:
            if not isinstance(conv, dict):
                continue
            msgs = conv.get("chat_messages") or []
            user_n = sum(1 for m in msgs if m.get("sender") == "human")
            asst_n = sum(1 for m in msgs if m.get("sender") == "assistant")
            if user_n == 0:
                continue
            start = _parse_ts(conv.get("created_at"))
            end = _parse_ts(conv.get("updated_at")) or start
            if not start:
                continue
            snippets = []
            for m in msgs:
                if m.get("sender") == "human":
                    t = m.get("text") or ""
                    if t:
                        snippets.append(t[:200])
                    if len(snippets) >= 3:
                        break
            activities.append(
                Activity(
                    source=Source.CLAUDE_AI,
                    session_id=conv.get("uuid") or "",
                    timestamp_start=start,
                    timestamp_end=end,
                    project=conv.get("name") or None,
                    activity_type=ActivityType.CHAT,
                    user_prompts_count=user_n,
                    tool_calls_count=asst_n,
                    summary=" | ".join(snippets)[:500],
                    raw_ref=f"{conv_file}#{conv.get('uuid','')}",
                )
            )
    return activities
