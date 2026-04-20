"""Google Takeout → Gemini Apps importer.

Reads `Takeout/My Activity/Gemini Apps/MyActivity.json` (flat activity stream).
Clusters consecutive records within 30 min into pseudo-sessions.
"""
from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "gemini_takeout"
SESSION_GAP = timedelta(minutes=30)


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _locate(root: Path) -> Iterator[Path]:
    for p in root.rglob("MyActivity.json"):
        if "Gemini" in str(p):
            yield p
    for z in root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(z) as zf:
                if any("Gemini" in n and n.endswith("MyActivity.json") for n in zf.namelist()):
                    out = z.parent / z.stem
                    out.mkdir(exist_ok=True)
                    zf.extractall(out)
                    for p in out.rglob("MyActivity.json"):
                        if "Gemini" in str(p):
                            yield p
        except (zipfile.BadZipFile, OSError):
            continue


def extract(cfg: dict[str, Any]) -> list[Activity]:
    import_dir = Path(cfg["extractors"]["cloud_gemini"]["import_dir"])
    if not import_dir.exists():
        return []
    activities: list[Activity] = []
    for src in _locate(import_dir):
        try:
            records = json.loads(src.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(records, list):
            continue
        dated = []
        for r in records:
            ts = _parse_ts(r.get("time"))
            if ts:
                dated.append((ts, r))
        dated.sort()
        if not dated:
            continue

        cluster: list[tuple[datetime, dict]] = []
        sid_counter = 0

        def flush() -> None:
            nonlocal sid_counter
            if not cluster:
                return
            start = cluster[0][0]
            end = cluster[-1][0]
            prompts = []
            for _, r in cluster[:3]:
                t = (r.get("title") or "").replace("Prompted ", "")
                if t:
                    prompts.append(t[:200])
            activities.append(
                Activity(
                    source=Source.GEMINI,
                    session_id=f"{src.stem}-{sid_counter}",
                    timestamp_start=start,
                    timestamp_end=end,
                    activity_type=ActivityType.CHAT,
                    user_prompts_count=len(cluster),
                    summary=" | ".join(prompts)[:500],
                    raw_ref=str(src),
                )
            )
            sid_counter += 1

        for ts, r in dated:
            if cluster and ts - cluster[-1][0] > SESSION_GAP:
                flush()
                cluster = []
            cluster.append((ts, r))
        flush()
    return activities
