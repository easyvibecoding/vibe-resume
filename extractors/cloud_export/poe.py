"""Poe per-chat TXT/CSV importer.

Each file in data/imports/poe/ is treated as one conversation. TXT format:
blocks separated by blank lines, each block "[Sender]\\n[timestamp]\\n[text]".
CSV: columns timestamp, sender, message.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "poe"


def _parse_ts(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_txt(f: Path) -> Activity | None:
    blocks = [b for b in f.read_text(errors="ignore").split("\n\n") if b.strip()]
    user_n = 0
    asst_n = 0
    ts_list: list[datetime] = []
    snippet: list[str] = []
    for b in blocks:
        lines = b.splitlines()
        if not lines:
            continue
        sender = lines[0].strip().lstrip("[").rstrip("]").lower()
        ts = _parse_ts(lines[1]) if len(lines) > 1 else None
        if ts:
            ts_list.append(ts)
        text = "\n".join(lines[2:]).strip()
        if sender in ("you", "user", "human"):
            user_n += 1
            if len(snippet) < 3:
                snippet.append(text[:200])
        else:
            asst_n += 1
    if user_n == 0:
        return None
    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
    start = min(ts_list) if ts_list else mtime
    end = max(ts_list) if ts_list else mtime
    return Activity(
        source=Source.POE,
        session_id=f.stem,
        timestamp_start=start,
        timestamp_end=end,
        project=f.stem,
        activity_type=ActivityType.CHAT,
        user_prompts_count=user_n,
        tool_calls_count=asst_n,
        summary=" | ".join(snippet)[:500],
        raw_ref=str(f),
    )


def _extract_csv(f: Path) -> Activity | None:
    with open(f) as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
    if not rows:
        return None
    user_rows = [r for r in rows if str(r.get("sender", "")).lower() in ("you", "user")]
    asst_rows = [r for r in rows if str(r.get("sender", "")).lower() not in ("you", "user")]
    ts_list = [t for t in (_parse_ts(r.get("timestamp", "")) for r in rows) if t]
    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
    start = min(ts_list) if ts_list else mtime
    end = max(ts_list) if ts_list else mtime
    return Activity(
        source=Source.POE,
        session_id=f.stem,
        timestamp_start=start,
        timestamp_end=end,
        project=f.stem,
        activity_type=ActivityType.CHAT,
        user_prompts_count=len(user_rows),
        tool_calls_count=len(asst_rows),
        summary=" | ".join(str(r.get("message", ""))[:200] for r in user_rows[:3])[:500],
        raw_ref=str(f),
    )


def extract(cfg: dict[str, Any]) -> list[Activity]:
    import_dir = Path(cfg["extractors"]["cloud_poe"]["import_dir"])
    if not import_dir.exists():
        return []
    activities: list[Activity] = []
    for f in import_dir.rglob("*.txt"):
        a = _extract_txt(f)
        if a:
            activities.append(a)
    for f in import_dir.rglob("*.csv"):
        a = _extract_csv(f)
        if a:
            activities.append(a)
    return activities
