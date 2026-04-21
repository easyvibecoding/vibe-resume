"""Tests for core.stats helpers.

`_longest_active_day_streak` is a pure function so it gets the bulk of the
coverage here — handles empty input, unsorted input, duplicates, singletons,
and non-contiguous runs.
"""
from __future__ import annotations

import pytest

from core.stats import _longest_active_day_streak


def test_empty_input_returns_zero() -> None:
    assert _longest_active_day_streak([]) == 0


def test_singleton_is_streak_of_one() -> None:
    assert _longest_active_day_streak(["2026-04-01"]) == 1


def test_contiguous_run() -> None:
    # Feed in reverse order to also exercise the sort-tolerance contract.
    dates = ["2026-04-03", "2026-04-02", "2026-04-01"]
    assert _longest_active_day_streak(dates) == 3


def test_duplicates_collapse() -> None:
    # Same day listed many times should still count as one active day.
    dates = ["2026-04-01", "2026-04-01", "2026-04-02"]
    assert _longest_active_day_streak(dates) == 2


def test_two_runs_with_gap_keeps_the_longest() -> None:
    # Mar 28–30 is 3 days; Apr 5–6 is 2. Longest wins.
    dates = [
        "2026-03-28", "2026-03-29", "2026-03-30",
        "2026-04-05", "2026-04-06",
    ]
    assert _longest_active_day_streak(dates) == 3


def test_gap_of_one_day_breaks_the_streak() -> None:
    # Mar 30 → Apr 1 is a 1-day gap. The current run resets to 1 at Apr 1.
    dates = ["2026-03-30", "2026-04-01"]
    assert _longest_active_day_streak(dates) == 1


@pytest.mark.parametrize(
    "dates, expected",
    [
        (["2026-04-01"], 1),
        (["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"], 4),
        # Month boundary must be handled by date arithmetic, not string compare.
        (["2026-01-31", "2026-02-01"], 2),
        # Year boundary.
        (["2025-12-31", "2026-01-01"], 2),
    ],
)
def test_streak_boundary_cases(dates: list[str], expected: int) -> None:
    assert _longest_active_day_streak(dates) == expected


def test_window_stats_no_longer_emits_by_category() -> None:
    """The always-empty `by_category` field was dropped in 2026-04. Guard
    against regressions that silently reintroduce the dead field."""
    from core.stats import WindowStats

    fields = {f for f in WindowStats.__dataclass_fields__}
    assert "by_category" not in fields, (
        "by_category was intentionally removed — if you need a categorical "
        "breakdown, design it properly against ProjectGroup.category_counts"
    )
