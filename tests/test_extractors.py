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


# ─────────────────────────────── codex ────────────────────────────────────────


@pytest.fixture()
def codex_sessions(tmp_path: Path) -> Path:
    """Fake ~/.codex/sessions tree with one rollout jsonl under YYYY/MM/DD/."""
    root = tmp_path / "sessions"
    rollout = root / "2026" / "04" / "22" / "rollout-2026-04-22T14-30-00-xyz789.jsonl"
    _write_jsonl(
        rollout,
        [
            {
                "timestamp": "2026-04-22T14:30:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "0199bd82-4b9a-76e0-94e9-8d9ddaa39c8c",
                    "cwd": "/Users/test/codex-proj",
                    "originator": "codex_cli",
                    "cli_version": "0.42.0",
                    "git": {"branch": "feat/resume"},
                },
            },
            {
                "timestamp": "2026-04-22T14:30:05.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "refactor extract flow"}],
                },
            },
            {
                "timestamp": "2026-04-22T14:30:10.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "apply_patch",
                    "arguments": '{"file_path": "/Users/test/codex-proj/cli.py"}',
                },
            },
            {
                "timestamp": "2026-04-22T14:30:15.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "apply_patch",
                    "arguments": '{"file_path": "/Users/test/codex-proj/README.md"}',
                },
            },
            {
                "timestamp": "2026-04-22T14:35:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "now add tests"}],
                },
            },
            # event_msg user_message echo — MUST NOT double-count
            {
                "timestamp": "2026-04-22T14:35:01.000Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "now add tests"},
            },
            # response_item with a system-reminder prefix — must be filtered
            {
                "timestamp": "2026-04-22T14:36:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "<system-reminder>stale task</system-reminder>"}],
                },
            },
        ],
    )
    return root


def test_codex_happy_path(codex_sessions: Path) -> None:
    from extractors.local import codex

    acts = codex.extract({"extractors": {"codex": {"path": str(codex_sessions)}}})

    assert len(acts) == 1
    a = acts[0]
    assert a.source == Source.CODEX
    assert a.activity_type == ActivityType.CODING
    # Two genuine user prompts; event_msg echo and system-reminder are excluded.
    assert a.user_prompts_count == 2
    assert a.tool_calls_count == 2
    # session_id pulled from session_meta payload.id
    assert a.session_id == "0199bd82-4b9a-76e0-94e9-8d9ddaa39c8c"
    assert a.project == "/Users/test/codex-proj"
    assert "apply_patch" in a.keywords
    assert "/Users/test/codex-proj/cli.py" in a.files_touched
    assert "/Users/test/codex-proj/README.md" in a.files_touched
    assert a.extra["git_branch"] == "feat/resume"
    assert a.extra["cli_version"] == "0.42.0"
    assert a.timestamp_start == datetime(2026, 4, 22, 14, 30, 0, tzinfo=UTC)
    assert "refactor extract flow" in a.summary
    assert str(codex_sessions) in a.raw_ref


def test_codex_missing_path(tmp_path: Path) -> None:
    from extractors.local import codex

    acts = codex.extract(
        {"extractors": {"codex": {"path": str(tmp_path / "nope")}}}
    )
    assert acts == []


def test_codex_archived_sessions_captured(tmp_path: Path) -> None:
    """Rollouts under archived_sessions/ must be extracted alongside the
    dated sessions/ tree — Codex moves user-archived sessions here.
    """
    from extractors.local import codex

    sessions = tmp_path / "sessions" / "2026" / "04" / "22"
    sessions.mkdir(parents=True)
    _write_jsonl(
        sessions / "rollout-active.jsonl",
        [
            {
                "timestamp": "2026-04-22T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "active-id", "cwd": "/a"},
            },
            {
                "timestamp": "2026-04-22T10:00:01Z",
                "type": "response_item",
                "payload": {"type": "message", "role": "user", "content": "active task"},
            },
        ],
    )

    archived = tmp_path / "archived_sessions"
    archived.mkdir()
    _write_jsonl(
        archived / "rollout-archived.jsonl",
        [
            {
                "timestamp": "2026-02-11T16:23:06Z",
                "type": "session_meta",
                "payload": {"id": "archived-id", "cwd": "/b"},
            },
            {
                "timestamp": "2026-02-11T16:23:07Z",
                "type": "response_item",
                "payload": {"type": "message", "role": "user", "content": "old task"},
            },
        ],
    )

    acts = codex.extract(
        {
            "extractors": {
                "codex": {
                    "path": str(sessions.parent.parent.parent),  # ~/.codex/sessions
                    "archived_path": str(archived),
                }
            }
        }
    )
    session_ids = {a.session_id for a in acts}
    assert session_ids == {"active-id", "archived-id"}


def test_codex_archive_dedupes_on_session_uuid(tmp_path: Path) -> None:
    """If the same session UUID appears in both active and archived trees
    (can happen mid-archive), it should be counted exactly once.
    """
    from extractors.local import codex

    sessions = tmp_path / "sessions" / "2026" / "04" / "22"
    sessions.mkdir(parents=True)
    shared_entries = [
        {
            "timestamp": "2026-04-22T10:00:00Z",
            "type": "session_meta",
            "payload": {"id": "shared-uuid", "cwd": "/dup"},
        },
        {
            "timestamp": "2026-04-22T10:00:01Z",
            "type": "response_item",
            "payload": {"type": "message", "role": "user", "content": "hi"},
        },
    ]
    _write_jsonl(sessions / "rollout-one.jsonl", shared_entries)
    archived = tmp_path / "archived_sessions"
    archived.mkdir()
    _write_jsonl(archived / "rollout-one-archived.jsonl", shared_entries)

    acts = codex.extract(
        {
            "extractors": {
                "codex": {
                    "path": str(sessions.parent.parent.parent),
                    "archived_path": str(archived),
                }
            }
        }
    )
    assert len(acts) == 1
    assert acts[0].session_id == "shared-uuid"


def test_gemini_cli_chats_and_logs_merge(tmp_path: Path) -> None:
    """A project dir with both chats/session-*.json AND logs.json should
    surface one Activity per unique sessionId (chats wins on dedupe).
    """
    from extractors.local import gemini_cli

    hash_dir = tmp_path / "tmp" / "abc123def4567890"
    chats_dir = hash_dir / "chats"
    chats_dir.mkdir(parents=True)

    # chats/ — rich session with assistant turns
    (chats_dir / "session-2026-04-22T10-00-rich.json").write_text(
        json.dumps(
            {
                "sessionId": "session-rich",
                "projectHash": "abc123def4567890",
                "startTime": "2026-04-22T10:00:00Z",
                "lastUpdated": "2026-04-22T10:05:00Z",
                "messages": [
                    {"id": 0, "timestamp": "2026-04-22T10:00:00Z", "type": "user", "content": "set up redis"},
                    {"id": 1, "timestamp": "2026-04-22T10:00:15Z", "type": "gemini", "content": "Sure, I'll help."},
                    {"id": 2, "timestamp": "2026-04-22T10:02:00Z", "type": "user", "content": "verify with redis-cli"},
                ],
            }
        )
    )

    # logs.json — older log-only records, one session overlaps with chats
    (hash_dir / "logs.json").write_text(
        json.dumps(
            [
                {"sessionId": "session-rich", "messageId": 0, "type": "user", "message": "set up redis", "timestamp": "2026-04-22T10:00:00Z"},
                {"sessionId": "session-logs-only", "messageId": 0, "type": "user", "message": "migrate to node 22", "timestamp": "2025-08-06T08:26:14Z"},
                {"sessionId": "session-logs-only", "messageId": 1, "type": "user", "message": "clean old versions", "timestamp": "2025-08-06T08:27:36Z"},
            ]
        )
    )

    acts = gemini_cli.extract({"extractors": {"gemini_cli": {"path": str(tmp_path / "tmp")}}})
    ids = sorted(a.session_id for a in acts)
    assert ids == ["session-logs-only", "session-rich"]

    rich = next(a for a in acts if a.session_id == "session-rich")
    assert rich.source == Source.GEMINI_CLI
    assert rich.user_prompts_count == 2
    assert rich.extra["assistant_turns"] == 1
    assert rich.extra["source_shape"] == "chats"
    assert rich.project == "gemini:abc123def456"
    assert rich.timestamp_start == datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)

    logs_only = next(a for a in acts if a.session_id == "session-logs-only")
    assert logs_only.user_prompts_count == 2
    assert logs_only.extra["source_shape"] == "logs"
    assert "migrate to node 22" in logs_only.summary
    assert logs_only.timestamp_start == datetime(2025, 8, 6, 8, 26, 14, tzinfo=UTC)


def test_gemini_cli_missing_path(tmp_path: Path) -> None:
    from extractors.local import gemini_cli

    acts = gemini_cli.extract(
        {"extractors": {"gemini_cli": {"path": str(tmp_path / "nope")}}}
    )
    assert acts == []


def test_gemini_cli_skips_bin_and_malformed(tmp_path: Path) -> None:
    """bin/ helper dir and malformed json must not break extraction."""
    from extractors.local import gemini_cli

    root = tmp_path / "tmp"
    (root / "bin").mkdir(parents=True)  # should be skipped
    (root / "bin" / "logs.json").write_text("not json")

    good = root / "good-hash"
    good.mkdir()
    (good / "logs.json").write_text(
        json.dumps(
            [
                {"sessionId": "g1", "messageId": 0, "type": "user", "message": "hi", "timestamp": "2026-04-22T10:00:00Z"},
            ]
        )
    )

    bad = root / "bad-hash"
    bad.mkdir()
    (bad / "logs.json").write_text("{ malformed")

    acts = gemini_cli.extract({"extractors": {"gemini_cli": {"path": str(root)}}})
    # Only the good project's session comes through; bin/ and malformed dir
    # are silently skipped.
    assert len(acts) == 1
    assert acts[0].session_id == "g1"


def test_copilot_cli_happy_path(tmp_path: Path) -> None:
    from extractors.local import copilot_cli

    session_dir = tmp_path / "session-state" / "34ea38e6-a566-4d3a-9f22-6b6ebc9e3aae"
    session_dir.mkdir(parents=True)
    _write_jsonl(
        session_dir / "events.jsonl",
        [
            {
                "type": "session.start",
                "timestamp": "2026-04-22T04:47:53.899Z",
                "data": {
                    "sessionId": "34ea38e6-a566-4d3a-9f22-6b6ebc9e3aae",
                    "copilotVersion": "1.0.34",
                    "producer": "copilot-agent",
                    "startTime": "2026-04-22T04:47:53.886Z",
                    "context": {"cwd": "/Users/test/proj"},
                },
            },
            {
                "type": "user.message",
                "timestamp": "2026-04-22T04:48:00.000Z",
                "data": {"content": "refactor the auth module"},
            },
            {
                "type": "assistant.turn_start",
                "timestamp": "2026-04-22T04:48:01.000Z",
                "data": {},
            },
            {
                "type": "assistant.message",
                "timestamp": "2026-04-22T04:48:03.000Z",
                "data": {
                    "content": "I'll start by reading the file.",
                    "toolRequests": [
                        {"name": "read_file", "arguments": {"file_path": "/Users/test/proj/auth.py"}},
                        {"name": "edit_file", "arguments": {"file_path": "/Users/test/proj/auth.py"}},
                    ],
                },
            },
            {
                "type": "user.message",
                "timestamp": "2026-04-22T04:50:00.000Z",
                "data": {"content": "now add a test"},
            },
            {
                "type": "session.shutdown",
                "timestamp": "2026-04-22T04:52:00.000Z",
                "data": {},
            },
        ],
    )

    acts = copilot_cli.extract(
        {"extractors": {"copilot_cli": {"path": str(tmp_path / "session-state")}}}
    )
    assert len(acts) == 1
    a = acts[0]
    assert a.source == Source.COPILOT_CLI
    assert a.session_id == "34ea38e6-a566-4d3a-9f22-6b6ebc9e3aae"
    assert a.user_prompts_count == 2
    assert a.tool_calls_count == 2
    assert a.project == "/Users/test/proj"
    assert "read_file" in a.keywords
    assert "edit_file" in a.keywords
    assert "/Users/test/proj/auth.py" in a.files_touched
    assert a.extra["copilot_version"] == "1.0.34"
    assert a.extra["producer"] == "copilot-agent"
    assert a.timestamp_start == datetime(2026, 4, 22, 4, 47, 53, 886000, tzinfo=UTC)


def test_copilot_cli_missing_path(tmp_path: Path) -> None:
    from extractors.local import copilot_cli

    acts = copilot_cli.extract(
        {"extractors": {"copilot_cli": {"path": str(tmp_path / "nope")}}}
    )
    assert acts == []


def test_copilot_cli_empty_session_dir_skipped(tmp_path: Path) -> None:
    """A session dir without events.jsonl must not break extraction."""
    from extractors.local import copilot_cli

    root = tmp_path / "session-state"
    # One valid session…
    good = root / "good-uuid"
    good.mkdir(parents=True)
    _write_jsonl(
        good / "events.jsonl",
        [
            {
                "type": "session.start",
                "timestamp": "2026-04-22T10:00:00Z",
                "data": {"sessionId": "good-uuid", "context": {"cwd": "/a"}},
            },
            {
                "type": "user.message",
                "timestamp": "2026-04-22T10:00:01Z",
                "data": {"content": "hi"},
            },
        ],
    )
    # …and one stub dir with no events.jsonl.
    (root / "stub-uuid").mkdir()

    acts = copilot_cli.extract({"extractors": {"copilot_cli": {"path": str(root)}}})
    assert len(acts) == 1
    assert acts[0].session_id == "good-uuid"


def test_codex_malformed_lines_dropped(tmp_path: Path) -> None:
    """Non-JSON lines in the middle of a rollout must be skipped, not crash."""
    from extractors.local import codex

    root = tmp_path / "sessions" / "2026" / "04" / "22"
    root.mkdir(parents=True)
    rollout = root / "rollout-corrupt.jsonl"
    rollout.write_text(
        '{"timestamp":"2026-04-22T14:30:00Z","type":"session_meta","payload":{"id":"s1","cwd":"/a"}}\n'
        "this is not json\n"
        '{"timestamp":"2026-04-22T14:30:10Z","type":"response_item","payload":{"type":"message","role":"user","content":"hello"}}\n'
    )

    acts = codex.extract({"extractors": {"codex": {"path": str(tmp_path / "sessions")}}})
    assert len(acts) == 1
    assert acts[0].user_prompts_count == 1


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
