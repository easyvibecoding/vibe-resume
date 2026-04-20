"""Midjourney — scan image folders for MJ-embedded IPTC/XMP metadata (post Oct 2025)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from core.schema import Activity, ActivityType, Source

NAME = "midjourney"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    roots = [Path(r).expanduser() for r in (cfg["extractors"]["image_local"].get("roots") or [])]
    activities: list[Activity] = []
    for root in roots:
        if not root.exists():
            continue
        for f in root.rglob("*.png"):
            try:
                with Image.open(f) as img:
                    info = dict(img.info or {})
                    xmp = img.getxmp() if hasattr(img, "getxmp") else {}
            except (UnidentifiedImageError, OSError, AttributeError):
                continue
            blob = str(info) + str(xmp)
            if "midjourney" not in blob.lower() and "Job ID" not in blob:
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            activities.append(
                Activity(
                    source=Source.MIDJOURNEY,
                    session_id=f.stem,
                    timestamp_start=mtime,
                    timestamp_end=mtime,
                    activity_type=ActivityType.IMAGE_GEN,
                    user_prompts_count=1,
                    raw_ref=str(f),
                    extra={"info": {k: str(v)[:300] for k, v in info.items()}},
                )
            )
    return activities
