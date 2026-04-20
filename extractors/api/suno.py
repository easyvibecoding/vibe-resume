"""Suno library importer. Two modes:
1) API key (SUNO_API_KEY) — call library endpoint (unofficial/third-party aggregators).
2) Local downloaded MP3s — read ID3 tags (title/artist/year + Suno-specific comments).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "suno"


def _mp3_scan(roots: list[Path]) -> list[Activity]:
    try:
        from mutagen.mp3 import MP3  # noqa: F401
        from mutagen.id3 import ID3
    except ImportError:
        return []
    out: list[Activity] = []
    for r in roots:
        if not r.exists():
            continue
        for f in r.rglob("*.mp3"):
            try:
                tags = ID3(f)
            except Exception:
                continue
            title = str(tags.get("TIT2") or "")
            comment = str(tags.get("COMM::XXX") or tags.get("COMM::eng") or "")
            if "suno" not in (title + comment).lower() and "suno" not in str(f).lower():
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            out.append(
                Activity(
                    source=Source.SUNO,
                    session_id=f.stem,
                    timestamp_start=mtime,
                    timestamp_end=mtime,
                    activity_type=ActivityType.AUDIO_GEN,
                    summary=title[:200],
                    raw_ref=str(f),
                )
            )
    return out


def extract(cfg: dict[str, Any]) -> list[Activity]:
    sub = cfg["extractors"]["suno"]
    roots = [Path(r).expanduser() for r in (sub.get("local_roots") or ["~/Music/Suno", "~/Downloads"])]
    return _mp3_scan(roots)
