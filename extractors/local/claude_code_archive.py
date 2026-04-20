"""Read JSONL archive created by scripts/backup_claude_projects.sh.

Same parser as claude_code.py but points at an external directory so old
sessions Claude Code would have cleaned stay discoverable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.schema import Activity
from extractors.local.claude_code import _process_session

NAME = "claude_code_archive"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    archive_cfg = cfg.get("extractors", {}).get("claude_code_archive", {})
    base = Path(archive_cfg.get("path") or "~/ClaudeCodeArchive/current").expanduser()
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
