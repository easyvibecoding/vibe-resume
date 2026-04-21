"""Tests for core.classifier.classify / tally_categories / capability_breadth.

These drive `category_counts` on every ProjectGroup, which the template
renders as the "backend 40% / frontend 20% / …" headline. Silent drift
here would reshape every rendered résumé without any visible error.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.classifier import (
    Category,
    capability_breadth,
    classify,
    tally_categories,
)
from core.schema import Activity, ActivityType, Source


def _act(
    summary: str = "",
    keywords: list[str] | None = None,
    files_touched: list[str] | None = None,
    project: str = "demo",
) -> Activity:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    return Activity(
        source=Source.CLAUDE_CODE,
        session_id="s",
        timestamp_start=now,
        timestamp_end=now,
        project=project,
        activity_type=ActivityType.CODING,
        summary=summary,
        keywords=keywords or [],
        files_touched=files_touched or [],
    )


# ─────────────────────── classify: single-category rules ──────────────────


@pytest.mark.parametrize(
    "summary, expected_category",
    [
        # English signals
        ("Built a React component with Tailwind", Category.FRONTEND),
        ("Added a FastAPI endpoint", Category.BACKEND),
        ("Wrote a Postgres migration", Category.DATABASE),
        ("Configured Docker and Kubernetes", Category.DEVOPS),
        ("Pushed release to production", Category.DEPLOYMENT),
        ("Fixed a null-pointer bug", Category.BUG_FIX),
        ("Implemented the checkout flow", Category.FEATURE),
        ("Refactored the auth layer", Category.REFACTOR),
        ("Wrote pytest coverage", Category.TESTING),
        ("Built the Figma design system", Category.UI_DESIGN),
        ("Updated the README", Category.DOCS),
        ("Optimized throughput of the hot path", Category.PERFORMANCE),
        ("Added OAuth token validation", Category.SECURITY),
        ("Trained the embedding model", Category.DATA_ML),
        ("Integrated the Stripe webhook", Category.API_INTEGRATION),
        ("Wired up the Claude Code skill", Category.AGENT_TOOLING),
        ("Investigated the latency spike", Category.RESEARCH),
    ],
)
def test_classify_single_english_signal(summary: str, expected_category: str) -> None:
    assert expected_category in classify(_act(summary=summary))


@pytest.mark.parametrize(
    "summary, expected_category",
    [
        # CJK signals that the English version of the rule wouldn't catch
        ("上線到正式環境", Category.DEPLOYMENT),
        ("修正登入壞了的 bug", Category.BUG_FIX),
        ("重構驗證邏輯", Category.REFACTOR),
        ("新增訂單頁面", Category.FEATURE),
        ("寫了 pytest 測試", Category.TESTING),
        ("調整排版與間距", Category.UI_DESIGN),
        ("更新文件與註解", Category.DOCS),
        ("效能最佳化", Category.PERFORMANCE),
        ("加入權限驗證", Category.SECURITY),
        ("研究新框架的可行性", Category.RESEARCH),
    ],
)
def test_classify_cjk_signals(summary: str, expected_category: str) -> None:
    assert expected_category in classify(_act(summary=summary))


# ─────────────────────── classify: multi-surface blob ─────────────────────


def test_classify_reads_keywords_and_files_and_project() -> None:
    """All four surfaces (summary / keywords / files / project) feed the
    blob, so a hit in any one qualifies the activity."""
    a = _act(
        summary="did some work",  # no signal
        keywords=["refactor"],  # signal here
        files_touched=[],
        project="/tmp/demo",
    )
    assert Category.REFACTOR in classify(a)


def test_classify_is_case_insensitive_for_ascii() -> None:
    """The blob is `.lower()`-ed before matching, so whatever case the source
    used, ASCII patterns still hit. CJK patterns don't have a case axis."""
    for variant in ["REACT", "React", "react"]:
        assert Category.FRONTEND in classify(_act(summary=f"built a {variant} app"))


# ─────────────────────── classify: FULLSTACK co-occurrence ────────────────


def test_fullstack_added_only_when_both_frontend_and_backend_present() -> None:
    frontend_only = classify(_act(summary="Built a React component"))
    assert Category.FULLSTACK not in frontend_only

    backend_only = classify(_act(summary="Added a FastAPI endpoint"))
    assert Category.FULLSTACK not in backend_only

    both = classify(_act(summary="Wired the React UI to a new FastAPI endpoint"))
    assert Category.FRONTEND in both
    assert Category.BACKEND in both
    assert Category.FULLSTACK in both


# ─────────────────────── tally_categories ─────────────────────────────────


def test_tally_sums_across_activities() -> None:
    acts = [
        _act(summary="React component"),  # frontend
        _act(summary="React update"),     # frontend
        _act(summary="FastAPI endpoint"), # backend
    ]
    counts = tally_categories(acts)
    assert counts[Category.FRONTEND] == 2
    assert counts[Category.BACKEND] == 1


def test_tally_fullstack_counted_per_activity_not_per_pair() -> None:
    """Fullstack derives from co-occurrence in a SINGLE activity — a
    frontend-only activity plus a backend-only activity does NOT create
    a fullstack count. This is important for the capability-breadth
    accuracy (otherwise a two-sprint stretch would falsely look cross-stack)."""
    acts = [
        _act(summary="React UI work"),     # frontend only
        _act(summary="FastAPI API work"),  # backend only
    ]
    counts = tally_categories(acts)
    assert Category.FULLSTACK not in counts


def test_tally_empty_input_is_empty_dict() -> None:
    assert tally_categories([]) == {}


# ─────────────────────── capability_breadth ───────────────────────────────


def test_capability_breadth_counts_distinct_categories() -> None:
    counts = {
        Category.FRONTEND: 5,
        Category.BACKEND: 3,
        Category.TESTING: 1,
    }
    assert capability_breadth(counts) == 3


def test_capability_breadth_excludes_fullstack_to_avoid_double_count() -> None:
    """`fullstack` is a derived tag — counting it bumps the breadth score
    for every cross-stack session without adding any real new category."""
    counts = {
        Category.FRONTEND: 5,
        Category.BACKEND: 3,
        Category.FULLSTACK: 5,  # would otherwise bump breadth to 3
    }
    assert capability_breadth(counts) == 2


def test_capability_breadth_ignores_zero_counts() -> None:
    counts = {
        Category.FRONTEND: 5,
        Category.BACKEND: 0,  # category present but zero hits → not counted
        Category.TESTING: 2,
    }
    assert capability_breadth(counts) == 2
