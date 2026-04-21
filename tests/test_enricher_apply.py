"""Behavior tests for core.enricher._apply_parsed_output.

The LLM is upstream-untrusted input: its response can be the wrong type,
over-length, or missing fields entirely. This helper must always leave the
ProjectGroup in a valid state no matter how malformed the `parsed` dict is.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.enricher import (
    ACHIEVEMENT_MAX_LEN,
    ACHIEVEMENTS_MAX_COUNT,
    SUMMARY_MAX_LEN,
    TECH_DOMAIN_MAX_LEN,
    TECH_HARD_MAX_LEN,
    _apply_parsed_output,
)
from core.schema import ProjectGroup, Source


def _blank_group() -> ProjectGroup:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ProjectGroup(
        name="demo",
        path="/tmp/demo",
        total_sessions=5,
        first_activity=now,
        last_activity=now,
        sources=[Source.CLAUDE_CODE],
        tech_stack=["Python", "FastAPI"],  # seed with a canonical hard skill
        category_counts={"backend": 3},
        capability_breadth=1,
        activities=[],
    )


def test_happy_path_fills_every_field() -> None:
    g = _blank_group()
    _apply_parsed_output(
        g,
        {
            "summary": "Backend engineer.",
            "role_label": "Backend + DevOps",
            "achievements": ["Shipped auth", "Migrated to Postgres 16"],
            "tech_stack": ["Python", "FastAPI", "Postgres"],
            "keywords_for_ats": ["Docker", "Kubernetes"],
        },
    )
    assert g.summary == "Backend engineer."
    assert g.achievements == ["Shipped auth", "Migrated to Postgres 16"]
    # ATS keywords merged into the stack before the hard/domain split.
    assert "Docker" in g.tech_stack
    assert "Kubernetes" in g.tech_stack


def test_oversized_strings_and_lists_are_capped() -> None:
    g = _blank_group()
    _apply_parsed_output(
        g,
        {
            "summary": "x" * (SUMMARY_MAX_LEN + 50),
            "achievements": [f"bullet {i}" for i in range(ACHIEVEMENTS_MAX_COUNT + 5)],
            "tech_stack": [f"Tech{i}" for i in range(TECH_HARD_MAX_LEN + 10)],
        },
    )
    assert len(g.summary) == SUMMARY_MAX_LEN
    assert len(g.achievements) == ACHIEVEMENTS_MAX_COUNT
    # Post-canonical cap applies; the raw pre-cap could be larger but the
    # final hard-skill list respects its own ceiling.
    assert len(g.tech_stack) <= TECH_HARD_MAX_LEN
    assert len(g.domain_tags) <= TECH_DOMAIN_MAX_LEN


def test_per_bullet_length_capped() -> None:
    g = _blank_group()
    _apply_parsed_output(
        g,
        {
            "summary": "ok",
            "achievements": ["a" * (ACHIEVEMENT_MAX_LEN + 200)],
        },
    )
    assert len(g.achievements[0]) == ACHIEVEMENT_MAX_LEN


def test_wrong_types_are_silently_ignored_not_crashed() -> None:
    """LLM might emit a string where we expect a list, etc. That must not raise."""
    g = _blank_group()
    # Seed a baseline so we can detect that bad input didn't wipe it out.
    g.achievements = ["baseline"]
    _apply_parsed_output(
        g,
        {
            "summary": None,  # coerced to ""
            "achievements": "this should have been a list",
            "tech_stack": 42,  # not a list
            "keywords_for_ats": None,
        },
    )
    assert g.summary == ""
    # Non-list achievements leaves the existing bullets untouched.
    assert g.achievements == ["baseline"]


def test_role_label_composes_headline_with_category_tail() -> None:
    g = _blank_group()
    g.headline = "Old role / backend 50%, devops 20%"  # aggregator-produced headline
    _apply_parsed_output(g, {"summary": "", "role_label": "Full-stack"})
    # LLM-provided role_label replaces the role slot, keeps the category tail.
    assert g.headline == "Full-stack · backend 50%, devops 20%"


def test_role_label_without_category_tail_becomes_bare_role() -> None:
    g = _blank_group()
    g.headline = "Just a name"  # no " / " separator
    _apply_parsed_output(g, {"summary": "", "role_label": "Backend"})
    assert g.headline == "Backend"


def test_empty_parsed_dict_leaves_group_in_valid_state() -> None:
    """Pydantic `ProjectGroup` requires the core fields already; the helper
    must not make an otherwise-valid group invalid by clearing them."""
    g = _blank_group()
    _apply_parsed_output(g, {})
    assert g.name == "demo"
    assert g.summary == ""
    # Model can still round-trip through pydantic — no invalid state introduced.
    ProjectGroup.model_validate(g.model_dump(mode="json"))


@pytest.mark.parametrize("bad_summary", [None, "", 0, False])
def test_summary_always_coerces_to_string(bad_summary: object) -> None:
    g = _blank_group()
    _apply_parsed_output(g, {"summary": bad_summary})
    assert isinstance(g.summary, str)
