"""Git-backed snapshots for resume drafts.

Each `render` call writes an output file into data/resume_history/ and creates
a commit in that directory's own git repo. `list-versions` walks the log.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("VIBE_RESUME_ROOT") or Path(__file__).parent.parent)


def _history_dir(cfg: dict[str, Any]) -> Path:
    p = Path(cfg.get("render", {}).get("output_dir") or "data/resume_history")
    if not p.is_absolute():
        p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, timeout=30)


def ensure_repo(cfg: dict[str, Any]) -> Path:
    repo = _history_dir(cfg)
    if not (repo / ".git").exists():
        _run(["git", "init", "-q"], repo)
        _run(["git", "config", "user.name", "ai-used-resume"], repo)
        _run(["git", "config", "user.email", "noreply@ai-used-resume.local"], repo)
        gi = repo / ".gitignore"
        if not gi.exists():
            gi.write_text("*.tmp\n")
    return repo


def snapshot(cfg: dict[str, Any], file_paths: list[Path], message: str) -> str:
    repo = ensure_repo(cfg)
    for fp in file_paths:
        if fp.exists():
            _run(["git", "add", fp.name], repo)
    st = _run(["git", "status", "--porcelain"], repo)
    if not st.stdout.strip():
        return ""
    _run(["git", "commit", "-q", "-m", message], repo)
    sha = _run(["git", "rev-parse", "--short", "HEAD"], repo).stdout.strip()
    ts_tag = datetime.now().strftime("v%Y%m%d-%H%M%S")
    try:
        _run(["git", "tag", ts_tag], repo)
    except subprocess.CalledProcessError:
        pass
    return sha


def list_history(cfg: dict[str, Any]) -> list[dict[str, str]]:
    repo = ensure_repo(cfg)
    try:
        r = _run(
            ["git", "log", "--pretty=format:%h|%ad|%s", "--date=iso"],
            repo,
            check=False,
        )
    except subprocess.CalledProcessError:
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            out.append({"version": parts[0], "date": parts[1], "subject": parts[2]})
    return out


def _resolve(repo: Path, ref: str) -> str:
    """Resolve '1'/'v1'/'v001' to the commit that introduced resume_v001.md."""
    if ref.startswith("v"):
        ref = ref[1:]
    if ref.isdigit():
        name = f"resume_v{int(ref):03d}.md"
        r = _run(["git", "log", "--diff-filter=A", "-1", "--pretty=format:%H", "--", name], repo, check=False)
        if r.stdout.strip():
            return r.stdout.strip()
    return ref


def diff_versions(cfg: dict[str, Any], v1: str, v2: str) -> str:
    repo = ensure_repo(cfg)
    s1 = _resolve(repo, v1)
    s2 = _resolve(repo, v2)
    r = _run(["git", "diff", s1, s2], repo, check=False)
    return r.stdout or r.stderr or "(no diff)"


def rollback(cfg: dict[str, Any], version: str) -> None:
    repo = ensure_repo(cfg)
    _run(["git", "checkout", version, "--", "."], repo)
