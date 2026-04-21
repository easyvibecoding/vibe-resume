"""Tests for core.tech_canonical — canonical display names + category grouping.

This module shapes every résumé's Skills section. Two contracts that silent
drift would break without a user-facing error:

1. Order preservation — templates display tech in input order, so a
   dedupe step that accidentally used a set() would scramble output.
2. Hard-vs-domain partition — the rendered résumé splits canonical tech
   (React, PostgreSQL, ...) from domain tags (SEO, Agent Workflow, ...).
   Anything that lands in the wrong bucket ends up in the wrong section.
"""
from __future__ import annotations

import pytest

from core.tech_canonical import (
    CATEGORIES,
    HARD_SKILLS,
    canonical_list,
    canonicalize,
    category_label,
    group_by_category,
    source_display,
    split_hard_skills,
)

# ─────────────────────── canonicalize ────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgres", "PostgreSQL"),         # alias → canonical
        ("postgresql", "PostgreSQL"),       # exact key
        ("POSTGRES", "PostgreSQL"),         # uppercase
        ("  postgres  ", "PostgreSQL"),     # whitespace tolerated
        ("node", "Node.js"),                # alias
        ("nodejs", "Node.js"),              # second alias
        ("k8s", "Kubernetes"),
        ("kubernetes", "Kubernetes"),
        ("claude code", "Claude Code"),     # multi-word key
    ],
)
def test_canonicalize_known_aliases(raw: str, expected: str) -> None:
    assert canonicalize(raw) == expected


def test_canonicalize_unknown_passthrough_stripped() -> None:
    """Unknown values are trimmed but otherwise preserved — the enricher
    might legitimately emit a fresh stack name (e.g. a 2026 framework we
    haven't added to CANONICAL yet), and we shouldn't drop it."""
    assert canonicalize("  SomeNewFramework  ") == "SomeNewFramework"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n", "\n   \t"])
def test_canonicalize_whitespace_only_returns_empty(raw: str) -> None:
    """Regression: before 2026-04 this returned the whitespace as-is, so
    blank rows from the enricher would leak through split_hard_skills and
    render as an empty bullet in the Skills section."""
    assert canonicalize(raw) == ""


# ─────────────────────── HARD_SKILLS invariant ────────────────────────────


def test_hard_skills_contains_every_categories_member() -> None:
    """HARD_SKILLS is built from CATEGORIES at import; if someone adds to a
    CATEGORIES bucket and the derivation code silently regresses, every
    render would start mis-partitioning the new entry into domain-tags."""
    for bucket, members in CATEGORIES.items():
        for m in members:
            assert m in HARD_SKILLS, f"{m!r} in CATEGORIES[{bucket!r}] missing from HARD_SKILLS"


# ─────────────────────── split_hard_skills ───────────────────────────────


def test_split_partitions_known_vs_unknown() -> None:
    """Known canonical tech → hard bucket; genuinely unknown tokens →
    domain bucket."""
    hard, domain = split_hard_skills(
        ["postgres", "React", "Content Curation"]
    )
    assert "PostgreSQL" in hard
    assert "React" in hard
    # "Content Curation" isn't in CANONICAL or any CATEGORIES bucket → domain.
    assert "Content Curation" in domain


def test_split_preserves_input_order_within_each_bucket() -> None:
    """Templates render tech in input order, so the partition must preserve
    it — no silent sorting, no set-based dedupe."""
    hard, domain = split_hard_skills(
        ["FastAPI", "Content Curation", "PostgreSQL", "Strategy", "React"]
    )
    assert hard == ["FastAPI", "PostgreSQL", "React"]
    assert domain == ["Content Curation", "Strategy"]


def test_split_hard_dedupe_via_canonical_key() -> None:
    """Both `postgres` and `postgresql` canonicalize to `PostgreSQL`; the
    second must not reappear."""
    hard, _ = split_hard_skills(["postgres", "postgresql", "node", "nodejs"])
    assert hard == ["PostgreSQL", "Node.js"]


def test_split_domain_dedupe_case_insensitive() -> None:
    """Domain tags aren't in CANONICAL, so the dedupe key is the lowercase
    display. Three case-variants of an unknown token collapse to one entry."""
    _, domain = split_hard_skills(
        ["Content Curation", "content curation", "CONTENT CURATION"]
    )
    assert len(domain) == 1


def test_split_empty_inputs_dropped() -> None:
    """Blank / whitespace-only entries must be skipped, not counted as
    empty-string domain tags (which would render as an odd gap). Exercises
    the canonicalize() whitespace-folding contract."""
    hard, domain = split_hard_skills(["", "  ", "\t\n", "React"])
    assert hard == ["React"]
    assert domain == []


def test_split_known_domain_names_still_land_in_hard_when_categorised() -> None:
    """`SEO`, `Automation`, and `Agent Workflow` look like domain tags by
    name but ARE listed in CATEGORIES buckets, so they correctly land in
    hard. If a future edit moves them out of CATEGORIES, this test will
    flip — pin the current truth so the change is deliberate."""
    hard, domain = split_hard_skills(["SEO", "Agent Workflow", "Automation"])
    # All three are in HARD_SKILLS by virtue of their CATEGORIES membership.
    assert "SEO" in hard
    assert "Agent Workflow" in hard
    assert "Automation" in hard
    assert domain == []


def test_split_empty_list() -> None:
    assert split_hard_skills([]) == ([], [])


# ─────────────────────── canonical_list ──────────────────────────────────


def test_canonical_list_dedupes_via_canonical_key() -> None:
    """Dedupe happens at the canonical layer — aliasing counts as duplicate."""
    got = canonical_list(["postgres", "postgresql", "React", "react"])
    assert got == ["PostgreSQL", "React"]


def test_canonical_list_preserves_first_seen_order() -> None:
    got = canonical_list(["Docker", "Python", "Docker", "Redis"])
    assert got == ["Docker", "Python", "Redis"]


# ─────────────────────── group_by_category ───────────────────────────────


def test_group_by_category_buckets_known_canonical_names() -> None:
    buckets = group_by_category(["React", "PostgreSQL", "Docker"])
    assert "React" in buckets["Frontend"]
    assert "PostgreSQL" in buckets["Database"]
    assert "Docker" in buckets["DevOps / Cloud"]


def test_group_by_category_unknowns_land_in_other_bucket() -> None:
    buckets = group_by_category(["React", "SomeExoticNewThing"])
    assert buckets["Other"] == ["SomeExoticNewThing"]


def test_group_by_category_drops_empty_buckets() -> None:
    """Template iterates buckets and renders a heading per one — empty ones
    would show up as blank subsections."""
    buckets = group_by_category(["React"])
    assert "Frontend" in buckets
    # Buckets with no members are not returned at all.
    assert "Database" not in buckets
    assert "Other" not in buckets


def test_group_by_category_empty_input_is_empty_dict() -> None:
    assert group_by_category([]) == {}


def test_group_by_category_first_match_wins() -> None:
    """`Python` appears in the Backend bucket. A future edit that added it to
    a second bucket should only place it once — this pins the behaviour."""
    buckets = group_by_category(["Python"])
    hits = [cat for cat, members in buckets.items() if "Python" in members]
    assert len(hits) == 1


# ─────────────────────── source_display / category_label ──────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("claude-code", "Claude Code"),
        ("chatgpt", "ChatGPT"),
        ("copilot-vscode", "GitHub Copilot (VS Code)"),
        ("git", "Git Commits"),
        ("other", "Other"),
    ],
)
def test_source_display_known(raw: str, expected: str) -> None:
    assert source_display(raw) == expected


def test_source_display_unknown_passthrough() -> None:
    """An as-yet-unmapped source enum shouldn't break rendering — it falls
    back to the raw key."""
    assert source_display("brand-new-agent") == "brand-new-agent"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("frontend", "Frontend"),
        ("devops", "DevOps / Infrastructure"),
        ("bug-fix", "Bug fixes"),
        ("data-ml", "Data / ML"),
    ],
)
def test_category_label_known(raw: str, expected: str) -> None:
    assert category_label(raw) == expected


def test_category_label_unknown_passthrough() -> None:
    assert category_label("mystery-slug") == "mystery-slug"
