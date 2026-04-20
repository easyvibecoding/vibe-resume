"""Scan local image folders for AI-generation metadata.

Detects:
- Stable Diffusion A1111: PNG tEXt chunk "parameters"
- ComfyUI: PNG tEXt "workflow" or "prompt" (JSON-shaped)
- Midjourney (post Oct 2025): IPTC/XMP with "Job ID" / "Description"
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from core.schema import Activity, ActivityType, Source

NAME = "image_local"


def _scan_roots(cfg: dict[str, Any]) -> list[Path]:
    roots = cfg["extractors"]["image_local"].get("roots") or []
    out = []
    for r in roots:
        p = Path(r)
        if p.exists():
            out.append(p)
    return out


def _classify(info: dict, filename: str) -> tuple[Source, dict] | None:
    if "parameters" in info:  # A1111
        params = str(info["parameters"])[:2000]
        return Source.A1111, {"parameters": params}
    for key in ("workflow", "prompt"):
        if key in info:
            try:
                data = json.loads(info[key]) if isinstance(info[key], str) else info[key]
                return Source.COMFYUI, {key: data}
            except (json.JSONDecodeError, TypeError):
                return Source.COMFYUI, {key: str(info[key])[:1000]}
    if "Job ID" in info or "Midjourney" in str(info):
        return Source.MIDJOURNEY, {k: str(v)[:500] for k, v in info.items()}
    return None


def extract(cfg: dict[str, Any]) -> list[Activity]:
    activities: list[Activity] = []
    excludes = cfg.get("scan", {}).get("exclude_globs") or []
    for root in _scan_roots(cfg):
        for f in root.rglob("*.png"):
            s = str(f)
            if any(ex.strip("*") in s for ex in excludes):
                continue
            try:
                with Image.open(f) as img:
                    info = dict(img.info or {})
            except (UnidentifiedImageError, OSError):
                continue
            hit = _classify(info, f.name)
            if not hit:
                continue
            source, extra = hit
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            prompt_preview = str(extra.get("parameters") or extra.get("prompt") or extra)[:300]
            activities.append(
                Activity(
                    source=source,
                    session_id=f.stem,
                    timestamp_start=mtime,
                    timestamp_end=mtime,
                    project=str(f.parent),
                    activity_type=ActivityType.IMAGE_GEN,
                    user_prompts_count=1,
                    summary=prompt_preview,
                    raw_ref=str(f),
                    extra=extra,
                )
            )
    return activities
