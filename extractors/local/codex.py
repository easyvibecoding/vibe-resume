"""Extract from ~/.codex/sessions/**/rollout-*.jsonl — one Activity per session.

OpenAI Codex CLI writes conversation transcripts under
    ~/.codex/sessions/YYYY/MM/DD/rollout-<iso-ts>-<uuid>.jsonl

Each row is {timestamp, type, payload}. Event types we care about:
- session_meta  — first few rows carry `cwd`, `git.branch`, `cli_version`,
  `originator`, `id` (session UUID)
- response_item — with payload.type in {message, function_call, reasoning,
  function_call_output}. message + role=user is a user prompt; function_call
  is a tool invocation whose `arguments` (often a JSON-encoded string) can
  carry file paths.
- event_msg — runtime telemetry (token_count, agent_reasoning, user_message
  echo, …). We ignore most of these to avoid double-counting user prompts
  that are already in response_item.

Codex respects $CODEX_HOME to relocate the base dir; the extractor reads
its path from `cfg["extractors"]["codex"]["path"]` so users who set
CODEX_HOME just need to mirror it in config.yaml.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source
from extractors.base import iter_jsonl

NAME = "codex"


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _flatten_content(content: Any) -> str:
    """Collapse Codex's content shape (str | list[{type,text}]) into text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict) and p.get("type") in (
                "input_text",
                "text",
                "output_text",
            ):
                txt = p.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
        return " ".join(parts).strip()
    return ""


def _extract_file_paths(args: Any) -> list[str]:
    """Pull filesystem-looking paths from a function_call arguments dict."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(args, dict):
        return []
    paths: list[str] = []
    for key in ("file_path", "path", "filePath", "workdir", "target"):
        v = args.get(key)
        if isinstance(v, str):
            paths.append(v)
    # Some shell-style tool calls wrap the command under `command` / `args`
    # — we don't try to parse those heuristically; raw_ref still captures
    # the source file for later inspection.
    return paths


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["codex"]["path"]).expanduser()
    if not base.exists():
        return []

    activities: list[Activity] = []
    for rollout_file in base.rglob("rollout-*.jsonl"):
        act = _process_session(rollout_file)
        if act:
            activities.append(act)
    return activities


def _process_session(path: Path) -> Activity | None:
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    user_prompts = 0
    tool_calls = 0
    cwd: str | None = None
    git_branch: str | None = None
    cli_version: str | None = None
    session_id: str = path.stem.replace("rollout-", "")
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
        payload = entry.get("payload") or {}

        if etype == "session_meta":
            cwd = payload.get("cwd") or cwd
            cli_version = payload.get("cli_version") or cli_version
            git = payload.get("git")
            if isinstance(git, dict):
                git_branch = git.get("branch") or git_branch
            sid = payload.get("id")
            if isinstance(sid, str):
                session_id = sid
            continue

        if etype != "response_item":
            # event_msg / turn_context / others don't contribute to counts
            # we care about (they'd double-count user_message echoes).
            continue

        payload_type = payload.get("type")
        if payload_type == "message" and payload.get("role") == "user":
            txt = _flatten_content(payload.get("content", ""))
            # Skip synthetic system reminders injected into the stream.
            if txt and not txt.startswith("<") and "<system-reminder>" not in txt:
                user_prompts += 1
                if len(user_text_chunks) < 8:
                    user_text_chunks.append(txt[:300])
        elif payload_type == "function_call":
            tool_calls += 1
            name = payload.get("name", "")
            if isinstance(name, str) and name:
                tool_names[name] = tool_names.get(name, 0) + 1
            for fp in _extract_file_paths(payload.get("arguments")):
                if len(files_touched) < 50:
                    files_touched.add(fp)

    if not any_entry or not first_ts:
        return None

    summary = " | ".join(user_text_chunks[:3])[:500]
    keywords = sorted(tool_names, key=lambda k: -tool_names[k])[:10]

    extra: dict[str, Any] = {}
    if cli_version:
        extra["cli_version"] = cli_version
    if git_branch:
        extra["git_branch"] = git_branch

    return Activity(
        source=Source.CODEX,
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
