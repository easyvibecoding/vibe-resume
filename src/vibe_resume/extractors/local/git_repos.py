"""Scan filesystem for .git repos; aggregate commits authored by the user.

Produces one Activity per repo per month, to keep volume manageable while
preserving the temporal signal.
"""
from __future__ import annotations

import re
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from vibe_resume.core.schema import Activity, ActivityType, Source

NAME = "git_repos"

# Wall-clock budget for scanning $HOME. FUSE mounts / broken symlinks can stall
# rglob indefinitely; once the budget is exceeded we return what we have.
SCAN_TIMEOUT_SECONDS = 120

# Record/unit separators delimit the pretty-format fields so commit bodies (which
# contain arbitrary newlines and pipes) survive parsing intact. `--numstat` lines
# trail each record and are peeled off by matching _NUMSTAT_RE from the end.
_RS = "\x1e"
_US = "\x1f"
_NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")
_MAX_FILES_PER_MONTH = 20
_MAX_BODIES_PER_MONTH = 5
_BODY_EXCERPT = 500
_SUMMARY_MAX = 4000


class Commit(NamedTuple):
    dt: datetime
    sha: str
    subject: str
    body: str
    insertions: int
    deletions: int
    files: list[str]


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


def _git_log(repo: Path, emails: list[str]) -> list[Commit]:
    author_filters: list[str] = []
    for e in emails:
        author_filters += ["--author", e]
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--no-merges",
             f"--pretty=format:{_RS}%H{_US}%aI{_US}%s{_US}%b",
             "--numstat", *author_filters],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []

    commits: list[Commit] = []
    for rec in out.stdout.split(_RS):
        if not rec.strip():
            continue
        parts = rec.split(_US, 3)
        if len(parts) < 4:
            continue
        sha, ts, subject, tail = parts
        lines = tail.split("\n")
        i = len(lines)
        # Peel trailing numstat (and blank separator) lines off the body. git's
        # --numstat block trails the %b body, with a record-terminating newline
        # (and sometimes a blank line) between them.
        while i > 0 and (not lines[i - 1].strip() or _NUMSTAT_RE.match(lines[i - 1])):
            i -= 1
        body = "\n".join(lines[:i]).strip()
        ins = dels = 0
        files: list[str] = []
        for nl in lines[i:]:
            m = _NUMSTAT_RE.match(nl)
            if not m:
                continue
            a, d, path = m.group(1), m.group(2), m.group(3)
            if a != "-":
                ins += int(a)
            if d != "-":
                dels += int(d)
            files.append(path)
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        commits.append(Commit(dt, sha, subject, body, ins, dels, files))
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
        buckets: dict[str, list[Commit]] = defaultdict(list)
        for c in commits:
            key = c.dt.strftime("%Y-%m")
            buckets[key].append(c)

        for ym, items in buckets.items():
            first = min(c.dt for c in items)
            last = max(c.dt for c in items)
            ins = sum(c.insertions for c in items)
            dels = sum(c.deletions for c in items)
            subjects = [c.subject for c in items][:10]
            bodies = [c.body for c in items if c.body][:_MAX_BODIES_PER_MONTH]
            files: list[str] = []
            for c in items:
                for f in c.files:
                    if f not in files:
                        files.append(f)
                if len(files) >= _MAX_FILES_PER_MONTH:
                    break
            files = files[:_MAX_FILES_PER_MONTH]
            summary = " | ".join(s[:80] for s in subjects[:3])
            if bodies:
                summary = f"{summary} ‖ {bodies[0].replace(chr(10), ' ')}"
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
                    summary=summary[:_SUMMARY_MAX],
                    files_touched=files,
                    raw_ref=f"{repo}@{ym}",
                    extra={
                        "commits": len(items),
                        "insertions": ins,
                        "deletions": dels,
                        "subjects": subjects,
                        "commit_bodies": [b[:_BODY_EXCERPT] for b in bodies],
                    },
                )
            )
    return activities
