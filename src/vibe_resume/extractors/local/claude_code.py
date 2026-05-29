"""Extract from ~/.claude/projects/*/*.jsonl — one Activity per session."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from vibe_resume.core.schema import Activity, ActivityType, Source
from vibe_resume.extractors.base import git_identity, iter_jsonl, sample_spread

NAME = "claude_code"
_SUMMARY_MAX = 4000


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
    sess = cfg.get("sessions", {})
    sample_n = int(sess.get("sample_prompts", 12))
    per_chars = int(sess.get("per_prompt_chars", 300))
    capture_args = bool(sess.get("capture_tool_args", False))

    activities: list[Activity] = []
    git_cache: dict = {}
    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            if "/subagents/" in str(jsonl_file):
                continue
            act = _process_session(jsonl_file, project_dir.name,
                                   sample_n, per_chars, capture_args, git_cache)
            if act:
                activities.append(act)
    return activities


def _process_session(path: Path, project_dirname: str,
                     sample_n: int, per_chars: int, capture_args: bool,
                     git_cache: dict) -> Activity | None:
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
    tool_args: list[str] = []
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
                user_text_chunks.append(txt[:per_chars])
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
                    if capture_args and len(tool_args) < sample_n:
                        try:
                            tool_args.append(json.dumps(inp)[:per_chars])
                        except (TypeError, ValueError):
                            pass

    if not any_entry or not first_ts:
        return None

    sampled = sample_spread(user_text_chunks, sample_n)
    summary_preview = " | ".join(sampled)[:_SUMMARY_MAX]
    keywords = sorted(tool_names, key=lambda k: -tool_names[k])[:10]
    extra: dict[str, Any] = {"git_branch": git_branch, "tool_histogram": dict(tool_names)}
    if capture_args and tool_args:
        extra["tool_args"] = "\n".join(tool_args)
    if cwd:
        remote, toplevel = git_identity(cwd, git_cache)
        if remote:
            extra["git_remote"] = remote
        if toplevel:
            extra["git_toplevel"] = toplevel

    return Activity(
        source=Source.CLAUDE_CODE,
        session_id=session_id,
        timestamp_start=first_ts,
        timestamp_end=last_ts,
        project=cwd or project_dirname,
        activity_type=ActivityType.CODING,
        tech_stack=[],
        keywords=keywords,
        summary=summary_preview,
        user_prompts_count=user_prompt_count,
        tool_calls_count=tool_call_count,
        files_touched=sorted(files_touched),
        raw_ref=str(path),
        extra=extra,
    )
