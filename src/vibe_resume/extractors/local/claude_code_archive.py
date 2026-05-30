"""Read JSONL archive created by scripts/backup_claude_projects.sh.

Same parser as claude_code.py but points at an external directory so old
sessions Claude Code would have cleaned stay discoverable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe_resume.core.schema import Activity
from vibe_resume.extractors.local.claude_code import _process_session

NAME = "claude_code_archive"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    archive_cfg = cfg.get("extractors", {}).get("claude_code_archive", {})
    base = Path(archive_cfg.get("path") or "~/ClaudeCodeArchive/current").expanduser()
    if not base.exists():
        return []

    # Mirror claude_code.extract's session-config read + per-run git cache so the
    # shared _process_session gets its full 6-arg signature (#73 — a stale 2-arg
    # call crashed this extractor, silently losing newly-archived sessions).
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
