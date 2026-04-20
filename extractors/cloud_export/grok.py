"""Grok xAI data export — lenient reader (schema unverified 2026)."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from core.schema import Activity, ActivityType, Source

NAME = "grok"


def _parse_ts(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v if v < 1e11 else v / 1000, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _iter_json(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.json"):
        yield p
    for z in root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(z) as zf:
                out = z.parent / z.stem
                out.mkdir(exist_ok=True)
                zf.extractall(out)
                yield from out.rglob("*.json")
        except (zipfile.BadZipFile, OSError):
            continue


def extract(cfg: dict[str, Any]) -> list[Activity]:
    import_dir = Path(cfg["extractors"]["cloud_grok"]["import_dir"])
    if not import_dir.exists():
        return []
    activities: list[Activity] = []
    for f in _iter_json(import_dir):
        if "conversation" not in f.name.lower() and "chat" not in f.name.lower():
            continue
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        convs = data if isinstance(data, list) else data.get("conversations") or []
        for c in convs:
            if not isinstance(c, dict):
                continue
            msgs = c.get("messages") or c.get("chat_messages") or []
            user_n = sum(1 for m in msgs if str(m.get("role", "")).lower() in ("user", "human"))
            asst_n = sum(1 for m in msgs if str(m.get("role", "")).lower() == "assistant")
            if user_n == 0:
                continue
            start = (
                _parse_ts(c.get("created_at"))
                or _parse_ts((msgs[0] if msgs else {}).get("created_at"))
                or datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            )
            end = _parse_ts(c.get("updated_at")) or start
            activities.append(
                Activity(
                    source=Source.GROK,
                    session_id=str(c.get("id") or c.get("uuid") or ""),
                    timestamp_start=start,
                    timestamp_end=end,
                    project=c.get("title") or None,
                    activity_type=ActivityType.CHAT,
                    user_prompts_count=user_n,
                    tool_calls_count=asst_n,
                    raw_ref=str(f),
                )
            )
    return activities
