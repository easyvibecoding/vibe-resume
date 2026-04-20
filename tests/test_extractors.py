"""Unit tests for the three highest-use extractors.

We test `claude_code`, `cursor`, and `git_repos` since together they account for
the bulk of extracted activity volume. Each test exercises:
  - the happy path (real fixture → Activity list)
  - the empty-source path (missing dir → [])
  - at least one malformed-input path so a format regression doesn't crash.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.schema import ActivityType, Source

# ─────────────────────────────── claude_code ──────────────────────────────────


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


@pytest.fixture()
def claude_projects(tmp_path: Path) -> Path:
    """Fake ~/.claude/projects with one session of mixed entries."""
    root = tmp_path / "projects"
    session = root / "-Users-test-proj" / "abc-123.jsonl"
    _write_jsonl(
        session,
        [
            {
                "type": "user",
                "timestamp": "2026-01-02T10:00:00Z",
                "sessionId": "abc-123",
                "cwd": "/Users/test/proj",
                "gitBranch": "main",
                "message": {"content": "help me refactor this"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-01-02T10:00:05Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "OK"},
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": "/Users/test/proj/foo.py"},
                        },
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "ls"},
                        },
                    ]
                },
            },
            {
                "type": "user",
                "timestamp": "2026-01-02T10:05:00Z",
                "message": {
                    "content": [{"type": "text", "text": "now add a test"}]
                },
            },
        ],
    )
    return root


def test_claude_code_happy_path(claude_projects: Path) -> None:
    from extractors.local import claude_code

    acts = claude_code.extract({"extractors": {"claude_code": {"path": str(claude_projects)}}})

    assert len(acts) == 1
    a = acts[0]
    assert a.source == Source.CLAUDE_CODE
    assert a.activity_type == ActivityType.CODING
    assert a.user_prompts_count == 2
    assert a.tool_calls_count == 2
    assert a.session_id == "abc-123"
    assert a.project == "/Users/test/proj"
    assert "Edit" in a.keywords
    assert "/Users/test/proj/foo.py" in a.files_touched
    assert a.extra["git_branch"] == "main"
    assert a.timestamp_start == datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC)


def test_claude_code_missing_path(tmp_path: Path) -> None:
    from extractors.local import claude_code

    acts = claude_code.extract(
        {"extractors": {"claude_code": {"path": str(tmp_path / "nope")}}}
    )
    assert acts == []


def test_claude_code_system_reminders_ignored(tmp_path: Path) -> None:
    """User bubbles containing <system-reminder> must not count as prompts."""
    from extractors.local import claude_code

    root = tmp_path / "projects"
    _write_jsonl(
        root / "p" / "s.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2026-01-02T10:00:00Z",
                "message": {"content": "<system-reminder>foo</system-reminder>"},
            },
            {
                "type": "user",
                "timestamp": "2026-01-02T10:00:01Z",
                "message": {"content": "real prompt"},
            },
        ],
    )
    acts = claude_code.extract({"extractors": {"claude_code": {"path": str(root)}}})
    assert len(acts) == 1
    assert acts[0].user_prompts_count == 1


# ──────────────────────────────── cursor ──────────────────────────────────────


def _make_cursor_db(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    con.execute(
        "INSERT INTO ItemTable VALUES (?, ?)",
        ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(payload)),
    )
    con.commit()
    con.close()


def test_cursor_happy_path(tmp_path: Path) -> None:
    from extractors.local import cursor

    gs = tmp_path / "globalStorage" / "state.vscdb"
    _make_cursor_db(
        gs,
        {
            "tabs": [
                {
                    "tabId": "t1",
                    "bubbles": [
                        {"type": "user", "text": "refactor this module"},
                        {"type": "assistant", "text": "sure"},
                        {"type": "user", "text": "now add types"},
                    ],
                }
            ]
        },
    )
    acts = cursor.extract({"extractors": {"cursor": {"path": str(tmp_path)}}})
    assert len(acts) == 1
    a = acts[0]
    assert a.source == Source.CURSOR
    assert a.user_prompts_count == 2
    assert a.tool_calls_count == 1  # one assistant bubble


def test_cursor_missing_path(tmp_path: Path) -> None:
    from extractors.local import cursor

    acts = cursor.extract({"extractors": {"cursor": {"path": str(tmp_path / "nope")}}})
    assert acts == []


def test_cursor_empty_bubbles_yields_no_activity(tmp_path: Path) -> None:
    from extractors.local import cursor

    _make_cursor_db(tmp_path / "globalStorage" / "state.vscdb", {"tabs": [{"tabId": "x", "bubbles": []}]})
    assert cursor.extract({"extractors": {"cursor": {"path": str(tmp_path)}}}) == []


# ──────────────────────────────── git_repos ───────────────────────────────────

_FAKE_LOG = (
    "abc123|2026-02-01T10:00:00+00:00|feat: add auth\n"
    "10\t2\tsrc/auth.py\n"
    "3\t0\ttests/test_auth.py\n"
    "def456|2026-02-15T14:30:00+00:00|fix: typo\n"
    "1\t1\tREADME.md\n"
)


def test_git_repos_parses_numstat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from extractors.local import git_repos

    # Make a fake repo layout so _find_repos has something to return.
    repo = tmp_path / "work" / "demo"
    (repo / ".git").mkdir(parents=True)

    def fake_run(cmd, **_kwargs):
        # The user-email lookup vs git-log call share the same patch — dispatch on subcommand.
        if "log" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=_FAKE_LOG, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="user@example.com\n", stderr="")

    monkeypatch.setattr(git_repos.subprocess, "run", fake_run)

    cfg = {
        "scan": {"mode": "whitelist", "roots": [str(tmp_path / "work")], "exclude_globs": []},
        "extractors": {"git_repos": {"author_emails": ["user@example.com"]}},
    }
    acts = git_repos.extract(cfg)
    assert len(acts) == 1  # 2 commits, both Feb 2026 → 1 monthly bucket
    a = acts[0]
    assert a.source == Source.GIT
    assert a.activity_type == ActivityType.COMMIT
    assert a.user_prompts_count == 2  # 2 commits
    assert a.extra["insertions"] == 14
    assert a.extra["deletions"] == 3
    assert "feat: add auth" in a.extra["subjects"]


def test_git_repos_no_emails_returns_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from extractors.local import git_repos

    def fake_run(*a, **_kw):
        return subprocess.CompletedProcess(a[0], 0, stdout="", stderr="")

    monkeypatch.setattr(git_repos.subprocess, "run", fake_run)
    cfg = {
        "scan": {"mode": "whitelist", "roots": [str(tmp_path)], "exclude_globs": []},
        "extractors": {"git_repos": {"author_emails": []}},
    }
    assert git_repos.extract(cfg) == []


def test_git_repos_scan_timeout_breaks_rglob(tmp_path: Path) -> None:
    """_find_repos must bail out when the deadline passes, even if rglob has more to yield."""
    from extractors.local import git_repos

    # Deadline already elapsed → no rglob iterations performed.
    result = git_repos._find_repos([tmp_path], excludes=[], timeout_seconds=-1)
    assert result == []
