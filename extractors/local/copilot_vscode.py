"""Extract GitHub Copilot chat from VS Code workspaceStorage/<hash>/chatSessions.

Format: each .jsonl file is delta-encoded — first line is kind:0 with full state
(requests[], sessionId, creationDate); subsequent kind:1 lines mutate it. We only
need summary stats, so we replay deltas onto a minimal state.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "copilot_vscode"


def _replay(path: Path) -> dict[str, Any] | None:
    state: dict[str, Any] | None = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("kind") == 0:
                    state = entry.get("v") or {}
                elif entry.get("kind") == 1 and state is not None:
                    keys = entry.get("k") or []
                    val = entry.get("v")
                    cur = state
                    for k in keys[:-1]:
                        cur = cur.setdefault(k, {}) if isinstance(cur, dict) else cur
                    if isinstance(cur, dict) and keys:
                        cur[keys[-1]] = val
    except OSError:
        return None
    return state


def _state_from_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["copilot_vscode"]["path"])
    if not base.exists():
        return []

    activities: list[Activity] = []
    for chat_dir in base.glob("*/chatSessions"):
        workspace_hash = chat_dir.parent.name
        for f in list(chat_dir.glob("*.jsonl")) + list(chat_dir.glob("*.json")):
            state = _replay(f) if f.suffix == ".jsonl" else _state_from_json(f)
            if not state:
                continue
            requests = state.get("requests") or []
            sid = state.get("sessionId") or f.stem
            created = state.get("creationDate")
            ts = (
                datetime.fromtimestamp(created / 1000, tz=timezone.utc)
                if isinstance(created, (int, float))
                else datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            )
            user_prompts: list[str] = []
            for req in requests:
                msg = req.get("message") if isinstance(req, dict) else None
                if isinstance(msg, dict):
                    t = msg.get("text") or ""
                    if t:
                        user_prompts.append(t[:200])

            if not requests:
                continue

            activities.append(
                Activity(
                    source=Source.COPILOT_VSCODE,
                    session_id=sid,
                    timestamp_start=ts,
                    timestamp_end=datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc),
                    project=workspace_hash,
                    activity_type=ActivityType.CODING,
                    user_prompts_count=len(user_prompts),
                    summary=" | ".join(user_prompts[:3])[:500],
                    raw_ref=str(f),
                )
            )
    return activities
