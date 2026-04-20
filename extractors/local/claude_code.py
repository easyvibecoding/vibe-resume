"""Extract from ~/.claude/projects/*/*.jsonl — one Activity per session."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source
from extractors.base import iter_jsonl

NAME = "claude_code"


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["claude_code"]["path"])
    if not base.exists():
        return []

    activities: list[Activity] = []
    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            if "/subagents/" in str(jsonl_file):
                continue
            act = _process_session(jsonl_file, project_dir.name)
            if act:
                activities.append(act)
    return activities


def _process_session(path: Path, project_dirname: str) -> Activity | None:
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    user_prompt_count = 0
    tool_call_count = 0
    cwd: str | None = None
    git_branch: str | None = None
    session_id: str = path.stem
    files_touched: set[str] = set()
    tool_names: defaultdict[str, int] = defaultdict(int)
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

        cwd = entry.get("cwd") or cwd
        git_branch = entry.get("gitBranch") or git_branch
        session_id = entry.get("sessionId") or session_id

        etype = entry.get("type")
        if etype == "user":
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                txt = content.strip()
            elif isinstance(content, list):
                txt = " ".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            else:
                txt = ""
            if txt and not txt.startswith("<") and "<system-reminder>" not in txt:
                user_prompt_count += 1
                if len(user_text_chunks) < 8:
                    user_text_chunks.append(txt[:300])
        elif etype == "assistant":
            msg = entry.get("message", {})
            for part in msg.get("content", []) or []:
                if isinstance(part, dict) and part.get("type") == "tool_use":
                    tool_call_count += 1
                    name = part.get("name", "")
                    if name:
                        tool_names[name] += 1
                    inp = part.get("input") or {}
                    for key in ("file_path", "path", "filePath"):
                        v = inp.get(key)
                        if isinstance(v, str) and len(files_touched) < 50:
                            files_touched.add(v)

    if not any_entry or not first_ts:
        return None

    summary_preview = " | ".join(user_text_chunks[:3])
    keywords = sorted(tool_names, key=lambda k: -tool_names[k])[:10]

    return Activity(
        source=Source.CLAUDE_CODE,
        session_id=session_id,
        timestamp_start=first_ts,
        timestamp_end=last_ts,
        project=cwd or project_dirname,
        activity_type=ActivityType.CODING,
        tech_stack=[],
        keywords=keywords,
        summary=summary_preview[:500],
        user_prompts_count=user_prompt_count,
        tool_calls_count=tool_call_count,
        files_touched=sorted(files_touched),
        raw_ref=str(path),
        extra={"git_branch": git_branch, "tool_histogram": dict(tool_names)},
    )
