"""Extract from ~/.gemini/tmp/<project_hash>/ — one Activity per session.

Gemini CLI + Antigravity IDE share ~/.gemini/ as the base dir. CLI sessions
live under a per-project hashed subdirectory:

    ~/.gemini/tmp/<sha256_hex>/
        logs.json             # list of {sessionId, messageId, type, message,
                              #   timestamp} — currently user-only event log
        chats/                # optional; one json per session when present
            session-YYYY-MM-DDTHH-mm-<short>.json
              { sessionId, projectHash, startTime, lastUpdated,
                messages: [ {id, timestamp, type, content} ] }

Not every project dir has chats/ — on older CLI versions the logs.json stream
is the only record. We prefer chats/session-*.json when available (richer
data, captures gemini responses + tool turns) and fall back to aggregating
logs.json by sessionId otherwise. Session UUIDs dedupe between the two
sources.

Antigravity's conversations live at ~/.gemini/antigravity/conversations/*.pb
(binary protobuf) and aren't parsed here — see ROADMAP.md for that work.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "gemini_cli"


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes())
    except (json.JSONDecodeError, ValueError, FileNotFoundError):
        return None


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["gemini_cli"]["path"]).expanduser()
    if not base.exists():
        return []

    activities: list[Activity] = []
    seen_session_ids: set[str] = set()

    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        project_hash = project_dir.name
        # Skip Gemini CLI's own helper bin dir.
        if project_hash == "bin":
            continue

        # 1. Prefer richer chats/session-*.json files.
        chats_dir = project_dir / "chats"
        if chats_dir.is_dir():
            for session_file in chats_dir.glob("session-*.json"):
                act = _activity_from_chat_file(session_file, project_hash)
                if act and act.session_id not in seen_session_ids:
                    seen_session_ids.add(act.session_id)
                    activities.append(act)

        # 2. Fall back to logs.json for any sessions not covered above.
        logs_file = project_dir / "logs.json"
        if logs_file.exists():
            for act in _activities_from_logs(logs_file, project_hash):
                if act.session_id not in seen_session_ids:
                    seen_session_ids.add(act.session_id)
                    activities.append(act)

    return activities


def _activity_from_chat_file(path: Path, project_hash: str) -> Activity | None:
    data = _safe_load_json(path)
    if not isinstance(data, dict):
        return None

    session_id = data.get("sessionId") or path.stem
    messages = data.get("messages") or []
    first_ts = _parse_ts(data.get("startTime", ""))
    last_ts = _parse_ts(data.get("lastUpdated", "")) or first_ts

    user_prompts = 0
    assistant_turns = 0
    user_text_chunks: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        mtype = m.get("type")
        # chats/ files use type='user' / type='gemini' (not role='assistant')
        if mtype == "user":
            user_prompts += 1
            content = m.get("content")
            txt = content.strip() if isinstance(content, str) else ""
            if txt and not txt.startswith("<") and len(user_text_chunks) < 8:
                user_text_chunks.append(txt[:300])
        elif mtype == "gemini":
            assistant_turns += 1

        # Tighten timestamps from message list even if startTime was missing.
        mts = _parse_ts(m.get("timestamp", ""))
        if mts:
            if not first_ts or mts < first_ts:
                first_ts = mts
            if not last_ts or mts > last_ts:
                last_ts = mts

    if not first_ts:
        return None

    return Activity(
        source=Source.GEMINI_CLI,
        session_id=session_id,
        timestamp_start=first_ts,
        timestamp_end=last_ts,
        project=_project_label(project_hash),
        activity_type=ActivityType.CODING,
        tech_stack=[],
        keywords=[],
        summary=" | ".join(user_text_chunks[:3])[:500],
        user_prompts_count=user_prompts,
        # chats/ files rarely carry explicit tool_use markers; surface the
        # assistant turn count in extra for downstream enrichers that want
        # to weight response-rich sessions.
        tool_calls_count=0,
        files_touched=[],
        raw_ref=str(path),
        extra={
            "project_hash": project_hash,
            "assistant_turns": assistant_turns,
            "source_shape": "chats",
        },
    )


def _activities_from_logs(path: Path, project_hash: str) -> list[Activity]:
    data = _safe_load_json(path)
    if not isinstance(data, list):
        return []

    # Group events by sessionId (logs.json may interleave multiple sessions).
    by_session: dict[str, list[dict]] = defaultdict(list)
    for entry in data:
        if isinstance(entry, dict):
            sid = entry.get("sessionId")
            if isinstance(sid, str):
                by_session[sid].append(entry)

    activities: list[Activity] = []
    for session_id, events in by_session.items():
        timestamps = [_parse_ts(e.get("timestamp", "")) for e in events]
        timestamps = [t for t in timestamps if t]
        if not timestamps:
            continue

        user_prompts = sum(1 for e in events if e.get("type") == "user")
        user_text_chunks: list[str] = []
        for e in events:
            if e.get("type") != "user":
                continue
            msg = e.get("message")
            if isinstance(msg, str):
                txt = msg.strip()
                if txt and not txt.startswith("<") and len(user_text_chunks) < 8:
                    user_text_chunks.append(txt[:300])

        activities.append(
            Activity(
                source=Source.GEMINI_CLI,
                session_id=session_id,
                timestamp_start=min(timestamps),
                timestamp_end=max(timestamps),
                project=_project_label(project_hash),
                activity_type=ActivityType.CODING,
                tech_stack=[],
                keywords=[],
                summary=" | ".join(user_text_chunks[:3])[:500],
                user_prompts_count=user_prompts,
                tool_calls_count=0,
                files_touched=[],
                raw_ref=f"{path}#{session_id}",
                extra={
                    "project_hash": project_hash,
                    "source_shape": "logs",
                },
            )
        )

    return activities


def _project_label(project_hash: str) -> str:
    """Short human-readable handle for a project.

    Gemini CLI hashes the project's filesystem root (unclear algorithm —
    sha256 of cwd plus some salt) and doesn't write back a reverse mapping,
    so the best we can do without reverse-engineering internals is surface
    a short prefix that's still stable across runs. Antigravity stores the
    real repo name alongside its own tracker at
    ~/.gemini/antigravity/code_tracker/active/<repo>_<sha>/ — folding those
    mappings in is future work.
    """
    return f"gemini:{project_hash[:12]}"
