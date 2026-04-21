"""Windowed activity statistics — aligned with Claude Code's 30-day retention.

Because Claude Code prunes JSONL sessions older than `cleanupPeriodDays`, any
lifetime-scale number derived from those transcripts undersells recent intensity.
Supplement with a rolling 30-day view showing active days, peak day, streak.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from core.schema import Activity, ProjectGroup, Source


@dataclass
class WindowStats:
    window_days: int
    window_start: str  # ISO date
    window_end: str
    sessions: int
    active_days: int
    active_day_ratio_pct: int  # active_days / window_days * 100
    daily_avg: float
    per_active_day_avg: float
    peak_day: str | None
    peak_day_sessions: int
    peak_week_start: str | None
    peak_week_sessions: int
    longest_streak_days: int
    projects_touched: int
    top_projects: list[dict] = field(default_factory=list)
    by_source: dict[str, int] = field(default_factory=dict)
    # `by_category` was serialised as an always-empty dict from an earlier
    # TODO placeholder. Dropped in the 2026-04 quality pass — callers should
    # read `ProjectGroup.category_counts` directly for a category breakdown.
    git_commits: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _iter_window_activities(
    groups: list[ProjectGroup], cutoff: datetime
) -> list[tuple[Activity, ProjectGroup]]:
    out: list[tuple[Activity, ProjectGroup]] = []
    for g in groups:
        for a in g.activities:
            ts = a.timestamp_start
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if ts >= cutoff:
                out.append((a, g))
    return out


def _monday_of(d: datetime) -> datetime:
    return (d - timedelta(days=d.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _longest_active_day_streak(iso_dates: list[str]) -> int:
    """Longest run of consecutive active days, given a set of ISO-date strings.

    Input need not be sorted or deduplicated; empty input returns 0.
    Kept pure and side-effect free so it can be tested without constructing
    a whole ProjectGroup tree.
    """
    if not iso_dates:
        return 0
    unique_sorted = sorted(set(iso_dates))
    longest = current = 1
    prev = datetime.fromisoformat(unique_sorted[0])
    for dstr in unique_sorted[1:]:
        d = datetime.fromisoformat(dstr)
        current = current + 1 if (d - prev).days == 1 else 1
        longest = max(longest, current)
        prev = d
    return longest


def compute_window_stats(
    groups: list[ProjectGroup],
    window_days: int = 30,
    now: datetime | None = None,
) -> WindowStats:
    end = now or _now_utc()
    start = end - timedelta(days=window_days)
    win = _iter_window_activities(groups, start)

    if not win:
        return WindowStats(
            window_days=window_days,
            window_start=start.date().isoformat(),
            window_end=end.date().isoformat(),
            sessions=0,
            active_days=0,
            active_day_ratio_pct=0,
            daily_avg=0.0,
            per_active_day_avg=0.0,
            peak_day=None,
            peak_day_sessions=0,
            peak_week_start=None,
            peak_week_sessions=0,
            longest_streak_days=0,
            projects_touched=0,
        )

    per_day: Counter[str] = Counter()
    per_week: Counter[str] = Counter()
    per_project: Counter[str] = Counter()
    per_source: Counter[str] = Counter()
    git_count = 0

    for a, g in win:
        ts = a.timestamp_start
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        per_day[ts.date().isoformat()] += 1
        per_week[_monday_of(ts).date().isoformat()] += 1
        per_project[g.name] += 1
        per_source[a.source.value] += 1
        if a.source == Source.GIT:
            git_count += a.extra.get("commits", 0) if a.extra else 0

    longest = _longest_active_day_streak(list(per_day.keys()))

    # peak day / week
    peak_day_str, peak_day_n = per_day.most_common(1)[0]
    peak_week_str, peak_week_n = per_week.most_common(1)[0]

    active_days = len(per_day)
    sessions = sum(per_day.values())
    daily_avg = sessions / window_days
    per_active = sessions / active_days if active_days else 0.0

    top_projects = [
        {"name": p, "sessions": n} for p, n in per_project.most_common(5)
    ]

    return WindowStats(
        window_days=window_days,
        window_start=start.date().isoformat(),
        window_end=end.date().isoformat(),
        sessions=sessions,
        active_days=active_days,
        active_day_ratio_pct=int(round(active_days / window_days * 100)),
        daily_avg=round(daily_avg, 1),
        per_active_day_avg=round(per_active, 1),
        peak_day=peak_day_str,
        peak_day_sessions=peak_day_n,
        peak_week_start=peak_week_str,
        peak_week_sessions=peak_week_n,
        longest_streak_days=longest,
        projects_touched=len(per_project),
        top_projects=top_projects,
        by_source=dict(per_source),
        git_commits=git_count,
    )
