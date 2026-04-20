"""ElevenLabs history via API. Requires ELEVENLABS_API_KEY."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "elevenlabs"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    env = cfg["extractors"]["elevenlabs"].get("api_key_env") or "ELEVENLABS_API_KEY"
    key = os.environ.get(env)
    if not key:
        return []
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/history?page_size=1000",
        headers={"xi-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except (urllib.error.URLError, json.JSONDecodeError):
        return []
    activities: list[Activity] = []
    for item in data.get("history") or []:
        ts_unix = item.get("date_unix") or 0
        ts = datetime.fromtimestamp(ts_unix, tz=UTC)
        activities.append(
            Activity(
                source=Source.ELEVENLABS,
                session_id=str(item.get("history_item_id", "")),
                timestamp_start=ts,
                timestamp_end=ts,
                project=item.get("voice_name"),
                activity_type=ActivityType.AUDIO_GEN,
                user_prompts_count=1,
                summary=str(item.get("text", ""))[:500],
                raw_ref=f"elevenlabs/{item.get('history_item_id')}",
                extra={
                    "voice_id": item.get("voice_id"),
                    "character_count": item.get("character_count_change_to"),
                    "model_id": item.get("model_id"),
                },
            )
        )
    return activities
