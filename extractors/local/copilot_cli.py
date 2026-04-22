"""Extract from ~/.copilot/session-state/<uuid>/events.jsonl — one Activity per session.

GitHub Copilot CLI persists each session as its own directory under
`~/.copilot/session-state/<session_uuid>/`. Inside we care about
`events.jsonl`, an event stream with rows shaped like:

    {type, data, id, timestamp, parentId}

Event types we consume:
- `session.start` — first event, carries `sessionId`, `copilotVersion`,
  `producer`, `context.cwd`, `startTime`
- `user.message` — `data.content` (string). Counts as a user prompt.
- `assistant.message` — `data.toolRequests` (list) + `data.content`.
  Each non-empty toolRequests entry counts as a tool call and may carry
  file paths in its arguments.
- `session.shutdown` — marks end of session.

Copilot CLI also maintains a SQLite session store alongside the JSONL;
we stick to the JSONL because it's the source of truth the docs point to
and it's faster to parse than attaching to a live DB. $COPILOT_HOME
overrides the base; extractor reads path from config.

This is a separate extractor from `copilot_vscode` (which parses the
Copilot Chat VS Code extension's per-workspace chat sessions). Same
parent product, different storage layout, different tool surface, so
each gets its own extractor + `Source.*` tag.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source
from extractors.base import iter_jsonl

NAME = "copilot_cli"


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_file_paths(tool_request: dict) -> list[str]:
    """Pull filesystem-looking strings out of a single toolRequests entry."""
    if not isinstance(tool_request, dict):
        return []
    paths: list[str] = []
    # toolRequests shape isn't publicly documented; inspect common key names.
    args = tool_request.get("arguments") or tool_request.get("input") or {}
    if isinstance(args, dict):
        for key in ("file_path", "path", "filePath", "file", "workdir", "target"):
            v = args.get(key)
            if isinstance(v, str):
                paths.append(v)
    return paths


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["copilot_cli"]["path"]).expanduser()
    if not base.exists():
        return []

    activities: list[Activity] = []
    for session_dir in base.iterdir():
        if not session_dir.is_dir():
            continue
        events_file = session_dir / "events.jsonl"
        if not events_file.exists():
            continue
        act = _process_session(events_file)
        if act:
            activities.append(act)
    return activities


def _process_session(path: Path) -> Activity | None:
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    user_prompts = 0
    tool_calls = 0
    session_id: str = path.parent.name
    cwd: str | None = None
    copilot_version: str | None = None
    producer: str | None = None
    files_touched: set[str] = set()
    tool_names: dict[str, int] = {}
    user_text_chunks: list[str] = []
    any_entry = False

    for entry in iter_jsonl(path):
        any_entry = True
        ts = _parse_ts(entry.get("timestamp", ""))
        if ts:
            if not first_ts or ts < first_ts:
                first_ts = ts
            if not last_ts or ts > last_ts:
                last_ts = ts

        etype = entry.get("type")
        data = entry.get("data") or {}

        if etype == "session.start":
            sid = data.get("sessionId")
            if isinstance(sid, str):
                session_id = sid
            ctx = data.get("context") or {}
            if isinstance(ctx, dict):
                cwd = ctx.get("cwd") or cwd
            copilot_version = data.get("copilotVersion") or copilot_version
            producer = data.get("producer") or producer
            start = _parse_ts(data.get("startTime", ""))
            if start and (not first_ts or start < first_ts):
                first_ts = start
        elif etype == "user.message":
            content = data.get("content") or data.get("transformedContent") or ""
            if isinstance(content, str):
                txt = content.strip()
                if txt and not txt.startswith("<"):
                    user_prompts += 1
                    if len(user_text_chunks) < 8:
                        user_text_chunks.append(txt[:300])
        elif etype == "assistant.message":
            tool_requests = data.get("toolRequests") or []
            if isinstance(tool_requests, list):
                for tr in tool_requests:
                    if not isinstance(tr, dict):
                        continue
                    tool_calls += 1
                    name = tr.get("name") or tr.get("toolName") or ""
                    if isinstance(name, str) and name:
                        tool_names[name] = tool_names.get(name, 0) + 1
                    for fp in _extract_file_paths(tr):
                        if len(files_touched) < 50:
                            files_touched.add(fp)

    if not any_entry or not first_ts:
        return None

    summary = " | ".join(user_text_chunks[:3])[:500]
    keywords = sorted(tool_names, key=lambda k: -tool_names[k])[:10]

    extra: dict[str, Any] = {}
    if copilot_version:
        extra["copilot_version"] = copilot_version
    if producer:
        extra["producer"] = producer

    return Activity(
        source=Source.COPILOT_CLI,
        session_id=session_id,
        timestamp_start=first_ts,
        timestamp_end=last_ts,
        project=cwd or path.parent.name,
        activity_type=ActivityType.CODING,
        tech_stack=[],
        keywords=keywords,
        summary=summary,
        user_prompts_count=user_prompts,
        tool_calls_count=tool_calls,
        files_touched=sorted(files_touched),
        raw_ref=str(path),
        extra=extra,
    )
