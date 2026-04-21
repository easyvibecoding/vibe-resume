"""Tests for core.review.resolve_resume_path.

Previously this lived inline in `cli.py::review` and was tangled with
Click's `UsageError`. Now a pure function raising domain-level
`ValueError` / `FileNotFoundError`, so we can test it without spinning
up a CliRunner.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.review import resolve_resume_path


def _touch(dir_: Path, name: str) -> Path:
    p = dir_ / name
    p.write_text("stub", encoding="utf-8")
    return p


def test_both_version_and_file_rejects() -> None:
    with pytest.raises(ValueError, match="not both"):
        resolve_resume_path(Path("/nonexistent"), version=1, file="some.md")


def test_explicit_file_returned_as_is(tmp_path: Path) -> None:
    """`file=` bypasses the glob — we don't second-guess a user-supplied path,
    letting downstream open-read give the real error message if it's wrong."""
    got = resolve_resume_path(tmp_path, file="/custom/path.md")
    assert got == Path("/custom/path.md")


def test_version_match_returns_lex_first_variant(tmp_path: Path) -> None:
    """With persona variants in play, `resume_v042.md` sorts before
    `resume_v042_en_US.md` and becomes the default — the bare filename
    is the 'canonical' variant when no locale/persona is requested."""
    _touch(tmp_path, "resume_v042.md")
    _touch(tmp_path, "resume_v042_en_US.md")
    _touch(tmp_path, "resume_v042_en_US_tech_lead.md")

    got = resolve_resume_path(tmp_path, version=42)
    assert got.name == "resume_v042.md"


def test_version_zero_pads_to_three_digits(tmp_path: Path) -> None:
    _touch(tmp_path, "resume_v007.md")
    got = resolve_resume_path(tmp_path, version=7)
    assert got.name == "resume_v007.md"


def test_version_not_found_raises(tmp_path: Path) -> None:
    _touch(tmp_path, "resume_v001.md")
    with pytest.raises(FileNotFoundError, match="v042"):
        resolve_resume_path(tmp_path, version=42)


def test_latest_picks_highest_version(tmp_path: Path) -> None:
    """'Latest' means last-in-sorted-order, which for zero-padded filenames
    is the highest version number."""
    for v in (1, 5, 12, 42):
        _touch(tmp_path, f"resume_v{v:03d}.md")
    got = resolve_resume_path(tmp_path)
    assert got.name == "resume_v042.md"


def test_latest_considers_persona_variants(tmp_path: Path) -> None:
    """A persona-suffixed variant can be the 'latest' if its sort key is
    higher — the CLI user gets the most recent file, regardless of suffix."""
    _touch(tmp_path, "resume_v010.md")
    _touch(tmp_path, "resume_v012_ja_JP_tech_lead.md")
    got = resolve_resume_path(tmp_path)
    # Sort is lexical; v012 variants come after v010, and the tech_lead
    # variant sorts after the bare one when both exist, so it wins.
    assert got.name == "resume_v012_ja_JP_tech_lead.md"


def test_latest_empty_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="run `render` first"):
        resolve_resume_path(tmp_path)
