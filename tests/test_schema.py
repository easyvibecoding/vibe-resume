"""Tests for core.schema — Pydantic model contracts + load_profile.

The UserProfile extra-fields contract is the foundation of the multi-locale
profile mechanism: `summary_zh_TW:` in profile.yaml has to survive through
model_dump() → render-context → template lookup, and it's never listed as
a named field on the dataclass. Silent breakage here would disable every
`<field>_<locale>` override at once.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import orjson
import pytest

from core.schema import (
    Activity,
    ActivityType,
    ProjectGroup,
    Source,
    UserProfile,
    load_profile,
)

# ─────────────────────── UserProfile.extra allowed ───────────────────────


def test_user_profile_allows_extra_fields_not_named_on_the_model() -> None:
    """The whole multi-locale profile mechanism depends on this: drop
    `summary_zh_TW: "…"` in profile.yaml, it must survive to the
    template via model_dump() + model_extra."""
    p = UserProfile(
        name="Alex",
        summary="English summary",
        summary_zh_TW="繁中摘要",  # not a named field — allowed via extra
        summary_ja_JP="日本語版",
        title_de_DE="Entwickler",
    )
    dumped = p.model_dump()
    # model_extra holds the extras; render/renderer merges them back in.
    assert p.model_extra["summary_zh_TW"] == "繁中摘要"
    assert p.model_extra["summary_ja_JP"] == "日本語版"
    assert p.model_extra["title_de_DE"] == "Entwickler"
    # Named fields still present normally.
    assert dumped["name"] == "Alex"
    assert dumped["summary"] == "English summary"


def test_user_profile_minimal_requires_only_name() -> None:
    """Every other field must be optional — the whole point is that a
    brand-new user drops in just `name:` and gets a draft back."""
    p = UserProfile(name="Alex")
    assert p.name == "Alex"
    # All the locale-conditional PII fields default to None / empty.
    assert p.dob is None
    assert p.nationality is None
    assert p.photo_path is None
    assert p.languages == []
    assert p.experience == []


def test_user_profile_rejects_missing_name() -> None:
    """Name is the only required field — a profile without it can't render."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserProfile()  # type: ignore[call-arg]  # deliberate: test the validator


# ─────────────────────── Activity round-trip ─────────────────────────────


def _act() -> Activity:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    return Activity(
        source=Source.CLAUDE_CODE,
        session_id="s1",
        timestamp_start=now,
        timestamp_end=now,
        project="/tmp/demo",
        activity_type=ActivityType.CODING,
        tech_stack=["Python"],
        keywords=["refactor"],
        summary="demo",
        user_prompts_count=3,
        tool_calls_count=5,
        files_touched=["/tmp/demo/a.py"],
        extra={"branch": "main"},
    )


def test_activity_json_roundtrip_preserves_every_field() -> None:
    """`save_activities` dumps via model_dump(mode='json') then orjson; the
    reverse `Activity(**d)` must restore every field including enums and
    UTC-aware datetimes."""
    a = _act()
    payload = orjson.dumps(a.model_dump(mode="json"))
    round_tripped = Activity(**orjson.loads(payload))
    assert round_tripped.source == Source.CLAUDE_CODE
    assert round_tripped.activity_type == ActivityType.CODING
    assert round_tripped.timestamp_start == a.timestamp_start
    assert round_tripped.tech_stack == ["Python"]
    assert round_tripped.extra == {"branch": "main"}


def test_activity_defaults_for_optional_fields() -> None:
    """Minimal Activity must get empty collections, not None — otherwise
    every downstream `for x in acts.tech_stack` breaks with TypeError."""
    a = Activity(
        source=Source.GIT,
        session_id="s",
        timestamp_start=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert a.tech_stack == []
    assert a.keywords == []
    assert a.files_touched == []
    assert a.extra == {}
    assert a.activity_type == ActivityType.OTHER  # default fallback
    assert a.summary == ""
    assert a.user_prompts_count == 0


def test_activity_timestamp_end_optional() -> None:
    """Some sources (git commits) only have a single timestamp."""
    a = Activity(
        source=Source.GIT,
        session_id="s",
        timestamp_start=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert a.timestamp_end is None


# ─────────────────────── Source / ActivityType enum shape ────────────────


def test_source_enum_values_are_strings() -> None:
    """`Source` inherits from (str, Enum) so values serialize cleanly to
    JSON. A switch to plain `Enum` would break every JSON cache file."""
    for member in Source:
        assert isinstance(member.value, str)


def test_activity_type_enum_values_are_strings() -> None:
    for member in ActivityType:
        assert isinstance(member.value, str)


def test_source_enum_includes_all_advertised_extractors() -> None:
    """The README + SKILL.md describe 18+ extractor sources. Dropping one
    from the enum would break the matching extractor silently at model
    validation time."""
    expected = {
        "claude-code", "claude-ai", "chatgpt", "cursor", "cline",
        "continue", "aider", "windsurf", "copilot-vscode", "zed",
        "gemini", "grok", "perplexity", "mistral", "poe",
        "git",
    }
    got = {s.value for s in Source}
    missing = expected - got
    assert not missing, f"Source enum missing advertised keys: {missing}"


# ─────────────────────── ProjectGroup shape ──────────────────────────────


def test_project_group_minimal_fields() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    g = ProjectGroup(
        name="demo",
        first_activity=now,
        last_activity=now,
        total_sessions=1,
    )
    # Every collection defaults to empty (not None).
    assert g.tech_stack == []
    assert g.sources == []
    assert g.activities == []
    assert g.category_counts == {}
    assert g.capability_breadth == 0
    assert g.headline is None
    assert g.domain_tags == []
    assert g.metrics == []


# ─────────────────────── load_profile ────────────────────────────────────


def test_load_profile_reads_yaml_and_builds_user_profile(tmp_path: Path) -> None:
    p = tmp_path / "profile.yaml"
    p.write_text(
        "name: Alex Chen\n"
        "title: Senior Engineer\n"
        "email: alex@example.com\n"
        "summary: English\n"
        "summary_zh_TW: 繁中版\n"
        "languages:\n"
        "  - English (native)\n"
        "  - Mandarin (fluent)\n",
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.name == "Alex Chen"
    assert prof.title == "Senior Engineer"
    assert prof.email == "alex@example.com"
    assert prof.summary == "English"
    # extra="allow" preserves the locale override under model_extra.
    assert prof.model_extra["summary_zh_TW"] == "繁中版"
    assert prof.languages == ["English (native)", "Mandarin (fluent)"]


def test_load_profile_empty_file_raises_on_missing_name(tmp_path: Path) -> None:
    """An empty profile.yaml yields None (or {}) → UserProfile() → raises
    because `name` is required. This is the expected user-facing error —
    don't silently ship a nameless draft."""
    from pydantic import ValidationError

    p = tmp_path / "profile.yaml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_profile(p)


def test_load_profile_missing_file_raises(tmp_path: Path) -> None:
    """`load_profile` doesn't swallow missing-file errors — caller sees a
    FileNotFoundError and can handle it (e.g. CLI shows a bootstrap hint)."""
    with pytest.raises(FileNotFoundError):
        load_profile(tmp_path / "never_saved.yaml")
