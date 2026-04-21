"""Tests for extractors.base — the iter_jsonl / save / load primitives.

Every extractor uses these. The lossy JSONL contract (skip blank lines,
fall back to stdlib json, drop lines that fail both parsers) is
particularly important to pin — Claude Code and Cursor occasionally emit
truncated / mixed-encoding rows during crashes, and we don't want a
single bad line to lose the rest of the session.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.schema import Activity, ActivityType, Source
from extractors.base import iter_jsonl, load_activities, save_activities

# ─────────────────────── iter_jsonl ───────────────────────────────────────


def test_iter_jsonl_missing_file_yields_nothing(tmp_path: Path) -> None:
    """Extractors call `iter_jsonl(maybe_path)` without pre-checking
    existence — a missing file must return an empty iterator, not raise."""
    assert list(iter_jsonl(tmp_path / "does_not_exist.jsonl")) == []


def test_iter_jsonl_happy_path_one_object_per_line(tmp_path: Path) -> None:
    p = tmp_path / "a.jsonl"
    p.write_bytes(b'{"id": 1}\n{"id": 2}\n{"id": 3}\n')
    got = list(iter_jsonl(p))
    assert got == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_iter_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "a.jsonl"
    p.write_bytes(b'{"id": 1}\n\n   \n{"id": 2}\n')
    got = list(iter_jsonl(p))
    assert got == [{"id": 1}, {"id": 2}]


def test_iter_jsonl_skips_lines_that_fail_both_parsers(tmp_path: Path) -> None:
    """Truncated JSON lines must not halt the whole stream — subsequent
    valid lines still yield. This is the load-bearing contract for Claude
    Code crash survival."""
    p = tmp_path / "a.jsonl"
    p.write_bytes(
        b'{"id": 1}\n'
        b'{"truncated": \n'            # orjson fails, json fails → skip
        b'totally not json at all\n'   # both fail → skip
        b'{"id": 3}\n'
    )
    got = list(iter_jsonl(p))
    assert got == [{"id": 1}, {"id": 3}]


def test_iter_jsonl_lossy_utf8_falls_back_to_stdlib_json(tmp_path: Path) -> None:
    """orjson is strict about UTF-8 by default; a line with a stray byte
    (common in crashed Claude Code sessions) must still yield via stdlib
    json with `errors="ignore"`. Here we write a line where orjson would
    choke on a latin-1 byte but the JSON structure is otherwise valid."""
    p = tmp_path / "a.jsonl"
    # `\xff` is not valid UTF-8 — orjson rejects the whole line; stdlib
    # json with errors=ignore parses the surviving ASCII payload.
    p.write_bytes(b'{"note": "caf\xff"}\n{"id": 2}\n')
    got = list(iter_jsonl(p))
    # First line survives via the fallback path (without the bad byte),
    # second line via the fast path.
    assert len(got) == 2
    assert got[1] == {"id": 2}


def test_iter_jsonl_works_as_iterator_not_just_list(tmp_path: Path) -> None:
    """The return annotation is Iterator[dict]; callers sometimes take
    the first N and stop. The file handle must close cleanly either way."""
    p = tmp_path / "a.jsonl"
    p.write_bytes(b'{"id": 1}\n{"id": 2}\n{"id": 3}\n')
    it = iter_jsonl(p)
    assert next(it) == {"id": 1}
    # Garbage-collecting the generator here would strand the fd; the `with
    # open` block inside iter_jsonl means Python closes the file when the
    # generator is closed. No assertion — this is a "shouldn't leak" check.
    it.close()


# ─────────────────────── save_activities / load_activities ────────────────


def _act(source: Source = Source.CLAUDE_CODE) -> Activity:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    return Activity(
        source=source,
        session_id="s1",
        timestamp_start=now,
        timestamp_end=now,
        project="/tmp/demo",
        activity_type=ActivityType.CODING,
        summary="test session",
        keywords=["demo"],
        files_touched=["/tmp/demo/foo.py"],
    )


def test_save_then_load_is_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "activities.json"  # nested path → parent must be created
    acts = [_act(Source.CLAUDE_CODE), _act(Source.CURSOR)]
    save_activities(acts, out)
    got = load_activities(out)
    assert len(got) == 2
    assert got[0].source == Source.CLAUDE_CODE
    assert got[1].source == Source.CURSOR
    assert got[0].summary == "test session"


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    """Extractors often write to `data/cache/<name>.json` — the cache dir
    may not exist yet on first run."""
    out = tmp_path / "a" / "b" / "c" / "acts.json"
    save_activities([_act()], out)
    assert out.exists()


def test_load_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert load_activities(tmp_path / "never_saved.json") == []


def test_save_empty_list_produces_empty_array(tmp_path: Path) -> None:
    """No activities for a source shouldn't write `null` or crash —
    the aggregator re-reads every source cache, so an empty file must
    round-trip as an empty list."""
    out = tmp_path / "empty.json"
    save_activities([], out)
    assert load_activities(out) == []
