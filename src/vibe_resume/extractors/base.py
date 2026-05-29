"""Common extractor helpers."""
from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import orjson

from vibe_resume.core.schema import Activity


class ExtractorError(Exception):
    pass


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield parsed JSON objects from a .jsonl file; skip malformed lines.

    Tries the fast orjson path first, then falls back to stdlib json with
    lossy UTF-8 decoding for lines that orjson rejects (Claude Code, Cursor,
    and friends occasionally emit truncated / mixed-encoding rows during
    crashes). A line that fails both parsers is dropped silently — lossy
    JSONL is a documented tradeoff, not a bug.
    """
    try:
        with open(path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield orjson.loads(line)
                except (orjson.JSONDecodeError, ValueError):
                    try:
                        yield json.loads(line.decode("utf-8", errors="ignore"))
                    except (json.JSONDecodeError, ValueError):
                        continue
    except FileNotFoundError:
        return


def sample_spread(items: list[str], k: int) -> list[str]:
    """Dedupe (keeping first occurrence) then return up to k items spread
    evenly across the list, always including the first and last."""
    seen: set[str] = set()
    uniq: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            uniq.append(it)
    if k <= 0:
        return []
    if len(uniq) <= k:
        return uniq
    if k == 1:
        return uniq[:1]
    last = len(uniq) - 1
    idxs = sorted({round(i * last / (k - 1)) for i in range(k)})
    return [uniq[i] for i in idxs]


_SKILL_BASE_RE = re.compile(r"Base directory for this skill:\s*(\S+)")


def skill_uses_in(text: str) -> list[str]:
    """Skill names (basename of the announced base dir) found in session text,
    e.g. 'Base directory for this skill: …/skills/foo' → 'foo'."""
    return [m.rstrip("/").split("/")[-1] for m in _SKILL_BASE_RE.findall(text or "")]


def _normalize_remote(url: str) -> str:
    """Collapse the many spellings of one git remote into a single key:
    strip scheme / userinfo, turn the scp-style `host:owner/repo` colon into
    a slash, drop a trailing `.git`, lowercase. So
    `git@github.com:Acme/Repo.git` and `https://github.com/acme/repo` both
    become `github.com/acme/repo`."""
    u = url.strip()
    for scheme in ("https://", "http://", "ssh://", "git://"):
        if u.startswith(scheme):
            u = u[len(scheme):]
            break
    else:
        if u.startswith("git@"):
            u = u[len("git@"):]
    head = u.split("/", 1)[0]
    # ssh:// form may leave `user@host`; scp form leaves `host:owner`
    if "@" in head:
        u = u.split("@", 1)[1]
        head = u.split("/", 1)[0]
    if ":" in head:
        u = u.replace(":", "/", 1)
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/").lower()


def _run_git(args: list[str]) -> str | None:
    """Run a git subcommand; return stripped stdout on rc 0, else None.
    Never raises (missing git / timeout / non-zero → None)."""
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    s = out.stdout.strip()
    return s or None


def git_identity(
    path: str | Path,
    cache: dict[str, tuple[str | None, str | None]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve (normalized origin remote, work-tree toplevel) for `path`.

    - Not a git work-tree (or path gone / git missing) → (None, None).
    - Work-tree with no `origin` remote → (None, toplevel).
    Memoized per path when a `cache` dict is supplied (sessions often share
    a cwd)."""
    key = str(path)
    if cache is not None and key in cache:
        return cache[key]
    if not Path(path).exists():
        result: tuple[str | None, str | None] = (None, None)
    else:
        toplevel = _run_git(["-C", key, "rev-parse", "--show-toplevel"])
        if toplevel is None:
            result = (None, None)
        else:
            raw = _run_git(["-C", key, "remote", "get-url", "origin"])
            remote = _normalize_remote(raw) if raw else None
            result = (remote, toplevel)
    if cache is not None:
        cache[key] = result
    return result


def save_activities(activities: list[Activity], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = [a.model_dump(mode="json") for a in activities]
    out_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))


def load_activities(path: Path) -> list[Activity]:
    if not path.exists():
        return []
    raw = orjson.loads(path.read_bytes())
    return [Activity(**item) for item in raw]
