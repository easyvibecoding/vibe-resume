"""Extract Cline tasks from VS Code extension storage.

Old path: ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/
New path (2026): ~/.cline/data/tasks/
Each task dir contains api_conversation_history.json and ui_messages.json.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "cline"


def _load(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _candidate_task_dirs(cfg: dict[str, Any]) -> list[Path]:
    roots = [
        Path(cfg["extractors"]["cline"]["path"]),
        Path("~/.cline/data").expanduser(),
    ]
    dirs: list[Path] = []
    for r in roots:
        if not r.exists():
            continue
        for tasks in [r / "tasks", r]:
            if tasks.exists():
                for d in tasks.iterdir():
                    if d.is_dir() and (d / "api_conversation_history.json").exists():
                        dirs.append(d)
    return dirs


def extract(cfg: dict[str, Any]) -> list[Activity]:
    activities: list[Activity] = []
    for task_dir in _candidate_task_dirs(cfg):
        api_hist = _load(task_dir / "api_conversation_history.json") or []
        ui_msgs = _load(task_dir / "ui_messages.json") or []
        if not api_hist:
            continue

        mtime = datetime.fromtimestamp(task_dir.stat().st_mtime, tz=UTC)
        try:
            ctime = datetime.fromtimestamp(task_dir.stat().st_birthtime, tz=UTC)
        except AttributeError:
            ctime = mtime

        user_n = 0
        tool_n = 0
        user_snippets: list[str] = []
        for m in api_hist:
            if m.get("role") == "user":
                user_n += 1
                content = m.get("content")
                if isinstance(content, str) and len(user_snippets) < 5:
                    user_snippets.append(content[:200])
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            user_snippets.append(str(part.get("text", ""))[:200])
                            break
            elif m.get("role") == "assistant":
                content = m.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "tool_use":
                            tool_n += 1

        task_text = ""
        if ui_msgs and isinstance(ui_msgs, list):
            for m in ui_msgs[:5]:
                if m.get("type") == "say" and m.get("say") == "task":
                    task_text = str(m.get("text", ""))[:200]
                    break

        activities.append(
            Activity(
                source=Source.CLINE,
                session_id=task_dir.name,
                timestamp_start=ctime,
                timestamp_end=mtime,
                project=None,
                activity_type=ActivityType.AGENT_RUN,
                user_prompts_count=user_n,
                tool_calls_count=tool_n,
                summary=(task_text or " | ".join(user_snippets[:2]))[:500],
                raw_ref=str(task_dir),
            )
        )
    return activities
