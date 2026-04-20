"""Scan filesystem for .git repos; aggregate commits authored by the user.

Produces one Activity per repo per month, to keep volume manageable while
preserving the temporal signal.
"""
from __future__ import annotations

import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "git_repos"

# Wall-clock budget for scanning $HOME. FUSE mounts / broken symlinks can stall
# rglob indefinitely; once the budget is exceeded we return what we have.
SCAN_TIMEOUT_SECONDS = 120


def _git_user_email() -> str | None:
    try:
        out = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _scan_roots(cfg: dict[str, Any]) -> list[Path]:
    mode = cfg.get("scan", {}).get("mode", "full")
    if mode == "full":
        return [Path.home()]
    return [Path(r) for r in (cfg.get("scan", {}).get("roots") or [])]


def _find_repos(
    roots: list[Path],
    excludes: list[str],
    timeout_seconds: float = SCAN_TIMEOUT_SECONDS,
) -> list[Path]:
    deadline = time.monotonic() + timeout_seconds
    repos: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        if time.monotonic() > deadline:
            break
        for git_dir in root.rglob(".git"):
            if time.monotonic() > deadline:
                break
            s = str(git_dir)
            if any(ex.strip("*") in s for ex in excludes):
                continue
            if git_dir.is_dir() or git_dir.is_file():
                repos.add(git_dir.parent)
    return sorted(repos)


def _git_log(repo: Path, emails: list[str]) -> list[tuple[datetime, str, str, int, int]]:
    author_filters: list[str] = []
    for e in emails:
        author_filters += ["--author", e]
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "log",
                "--no-merges",
                "--pretty=format:%H|%aI|%s",
                "--numstat",
                *author_filters,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []

    commits: list[tuple[datetime, str, str, int, int]] = []
    sha = ts = subject = ""
    insertions = deletions = 0
    for line in out.stdout.splitlines():
        if "|" in line and line.count("|") == 2 and not line.startswith("\t"):
            if sha:
                try:
                    dt = datetime.fromisoformat(ts)
                    commits.append((dt, sha, subject, insertions, deletions))
                except ValueError:
                    pass
            sha, ts, subject = line.split("|", 2)
            insertions = deletions = 0
        elif line and line[0].isdigit():
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    insertions += int(parts[0])
                    deletions += int(parts[1])
                except ValueError:
                    pass
    if sha:
        try:
            dt = datetime.fromisoformat(ts)
            commits.append((dt, sha, subject, insertions, deletions))
        except ValueError:
            pass
    return commits


def extract(cfg: dict[str, Any]) -> list[Activity]:
    emails = list(cfg["extractors"]["git_repos"].get("author_emails") or [])
    if not emails:
        auto = _git_user_email()
        if auto:
            emails = [auto]
    if not emails:
        return []

    excludes = cfg.get("scan", {}).get("exclude_globs") or []
    roots = _scan_roots(cfg)
    repos = _find_repos(roots, excludes)

    activities: list[Activity] = []
    for repo in repos:
        commits = _git_log(repo, emails)
        if not commits:
            continue
        # bucket by year-month
        buckets: dict[str, list[tuple[datetime, str, str, int, int]]] = defaultdict(list)
        for c in commits:
            key = c[0].strftime("%Y-%m")
            buckets[key].append(c)

        for ym, items in buckets.items():
            first = min(c[0] for c in items)
            last = max(c[0] for c in items)
            ins = sum(c[3] for c in items)
            dels = sum(c[4] for c in items)
            subjects = [c[2] for c in items][:10]
            activities.append(
                Activity(
                    source=Source.GIT,
                    session_id=f"{repo.name}:{ym}",
                    timestamp_start=first.astimezone(UTC),
                    timestamp_end=last.astimezone(UTC),
                    project=str(repo),
                    activity_type=ActivityType.COMMIT,
                    user_prompts_count=len(items),
                    tool_calls_count=0,
                    summary=" | ".join(s[:80] for s in subjects[:3])[:500],
                    raw_ref=f"{repo}@{ym}",
                    extra={
                        "commits": len(items),
                        "insertions": ins,
                        "deletions": dels,
                        "subjects": subjects,
                    },
                )
            )
    return activities
