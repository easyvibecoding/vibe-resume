"""Perplexity data export — lenient reader (schema unverified 2026)."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from core.schema import Activity, ActivityType, Source

NAME = "perplexity"


def _parse_ts(v: Any) -> datetime | None:
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
    import_dir = Path(cfg["extractors"]["cloud_perplexity"]["import_dir"])
    if not import_dir.exists():
        return []
    activities: list[Activity] = []
    for f in _iter_json(import_dir):
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        threads = data if isinstance(data, list) else data.get("threads") or []
        for t in threads:
            if not isinstance(t, dict):
                continue
            entries = t.get("entries") or t.get("queries") or []
            if not entries:
                continue
            start = _parse_ts(t.get("created_at")) or datetime.fromtimestamp(
                f.stat().st_mtime, tz=timezone.utc
            )
            end = _parse_ts(t.get("updated_at")) or start
            snippets = [str(e.get("query", ""))[:200] for e in entries[:3] if isinstance(e, dict)]
            activities.append(
                Activity(
                    source=Source.PERPLEXITY,
                    session_id=str(t.get("id") or t.get("uuid") or ""),
                    timestamp_start=start,
                    timestamp_end=end,
                    project=t.get("title") or None,
                    activity_type=ActivityType.CHAT,
                    user_prompts_count=len(entries),
                    summary=" | ".join(snippets)[:500],
                    raw_ref=str(f),
                )
            )
    return activities
