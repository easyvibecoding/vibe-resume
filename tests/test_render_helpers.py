"""Tests for the pure helpers pulled out of render.renderer._render_md.

Exercises the four extractions: timespan, AI overview, top capabilities,
and headline humanization. All are format-shape contracts the templates
depend on; a silent drift here would break every locale simultaneously.
"""
from __future__ import annotations

from datetime import UTC, datetime

from core.schema import ProjectGroup, Source
from render.renderer import (
    HEADLINE_MAP,
    _build_ai_overview,
    _compute_timespan,
    _humanize_headlines,
    _top_capabilities,
)


def _group(
    name: str = "demo",
    *,
    sources: list[Source] | None = None,
    category_counts: dict[str, int] | None = None,
    sessions: int = 5,
) -> ProjectGroup:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    return ProjectGroup(
        name=name,
        path=f"/tmp/{name}",
        total_sessions=sessions,
        first_activity=now,
        last_activity=now,
        sources=sources or [Source.CLAUDE_CODE],
        tech_stack=["Python"],
        category_counts=category_counts or {"backend": sessions},
        capability_breadth=1,
        activities=[],
    )


# ─────────────────────── _compute_timespan ────────────────────────────────


def test_timespan_empty_falls_back_to_today() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    assert _compute_timespan([]) == (today, today)


def test_timespan_spans_min_first_to_max_last() -> None:
    groups = [
        {"first_activity": "2025-09-15T10:00:00+00:00", "last_activity": "2025-12-01T10:00:00+00:00"},
        {"first_activity": "2026-02-01T10:00:00+00:00", "last_activity": "2026-04-18T10:00:00+00:00"},
    ]
    start, end = _compute_timespan(groups)
    assert start == "2025-09-15"
    assert end == "2026-04-18"


def test_timespan_slices_to_ten_chars() -> None:
    """Should take just the YYYY-MM-DD prefix of the ISO timestamp, never the
    full timezone-offsetted string."""
    g = [{"first_activity": "2026-04-18T10:00:00+00:00", "last_activity": "2026-04-18T22:00:00+00:00"}]
    start, end = _compute_timespan(g)
    assert start == "2026-04-18"
    assert end == "2026-04-18"
    assert len(start) == 10


# ─────────────────────── _build_ai_overview ───────────────────────────────


def test_ai_overview_empty_is_empty() -> None:
    assert _build_ai_overview([]) == []


def test_ai_overview_counts_distinct_groups_not_sessions() -> None:
    """A long-running project with 100 sessions shouldn't dominate — we
    count project-groups-per-source, not raw activity count."""
    groups = [
        _group("a", sources=[Source.CLAUDE_CODE], sessions=100),
        _group("b", sources=[Source.CURSOR], sessions=1),
        _group("c", sources=[Source.CLAUDE_CODE, Source.CURSOR], sessions=1),
    ]
    overview = _build_ai_overview(groups)
    # 3 groups total → claude-code in 2, cursor in 2 → each at 66%.
    by_tool = {o["tool"]: o for o in overview}
    assert by_tool["Claude Code"]["projects"] == 2
    assert by_tool["Claude Code"]["percent"] == 66
    assert by_tool["Cursor"]["projects"] == 2


def test_ai_overview_sorted_most_common_first() -> None:
    groups = [
        _group("a", sources=[Source.CURSOR]),
        _group("b", sources=[Source.CLAUDE_CODE]),
        _group("c", sources=[Source.CLAUDE_CODE]),
        _group("d", sources=[Source.CLAUDE_CODE]),
    ]
    overview = _build_ai_overview(groups)
    # 3 claude_code > 1 cursor, so claude-code lands first.
    assert overview[0]["projects"] >= overview[-1]["projects"]
    assert overview[0]["tool"] == "Claude Code"


# ─────────────────────── _top_capabilities ────────────────────────────────


def test_top_capabilities_excludes_fullstack_derived_tag() -> None:
    """`fullstack` is always a superset of the real categories — including
    it in the top list would crowd out actual signal."""
    groups = [
        _group("a", category_counts={"fullstack": 999, "backend": 10, "frontend": 8}),
    ]
    assert "fullstack" not in [c.lower() for c in _top_capabilities(groups)]


def test_top_capabilities_respects_limit() -> None:
    groups = [
        _group(
            "a",
            category_counts={
                "backend": 10,
                "frontend": 9,
                "devops": 8,
                "testing": 7,
                "refactor": 6,
                "docs": 5,
                "security": 4,
                "performance": 3,
            },
        ),
    ]
    assert len(_top_capabilities(groups, limit=3)) == 3
    assert len(_top_capabilities(groups, limit=100)) <= 8  # can't exceed input


# ─────────────────────── _humanize_headlines ──────────────────────────────


def test_humanize_replaces_known_slugs() -> None:
    gs = [{"headline": "backend 50%, frontend 30%"}]
    _humanize_headlines(gs)
    assert gs[0]["headline"] == "Backend 50%, Frontend 30%"


def test_humanize_trailing_space_requirement() -> None:
    """Mapping deliberately replaces `slug ` (with trailing space) so a slug
    that appears as a substring of a longer word isn't accidentally mangled
    (e.g. don't rewrite 'backends' into 'Backends')."""
    gs = [{"headline": "backends team"}]  # backends + space
    _humanize_headlines(gs)
    # 'backend ' isn't present (it's 'backends '), so nothing changes.
    assert gs[0]["headline"] == "backends team"


def test_humanize_missing_headline_becomes_empty_string() -> None:
    gs = [{"name": "x"}]  # no headline key
    _humanize_headlines(gs)
    assert gs[0]["headline"] == ""


def test_humanize_unknown_slugs_pass_through() -> None:
    gs = [{"headline": "some-new-thing 100%"}]
    _humanize_headlines(gs)
    assert gs[0]["headline"] == "some-new-thing 100%"


def test_headline_map_covers_the_expected_categories() -> None:
    """If the classifier adds a new category, extend HEADLINE_MAP so the
    template doesn't end up displaying the raw slug."""
    expected = {"frontend", "backend", "devops", "testing", "security", "data-ml"}
    assert expected.issubset(HEADLINE_MAP.keys())
