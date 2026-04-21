"""Tests for the smaller helpers in core.review.

Covers parse_jd_keywords (JD tokenization), sparkline (score-history display),
find_previous_review + load_reviews_by_locale (review-history filesystem scan).
"""
from __future__ import annotations

import json
from pathlib import Path

from core.review import (
    ReviewReport,
    Score,
    find_previous_review,
    load_reviews_by_locale,
    parse_jd_keywords,
    sparkline,
)

# ─────────────────────── parse_jd_keywords ────────────────────────────────


def _write_jd(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "jd.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_jd_tech_priority_hits_come_first_ordered_by_appearance(tmp_path: Path) -> None:
    """Tech names from the priority list must precede capitalized fallbacks,
    AND within that pass they're ordered by first appearance in the JD —
    not by the order of _JD_TECH_PRIORITY itself."""
    jd = _write_jd(
        tmp_path,
        "We ship FastAPI services on Kubernetes. Python experience required. "
        "Also: React frontend, PostgreSQL schema work.",
    )
    got = parse_jd_keywords(jd)
    tech_subset = [t for t in got if t in {"FastAPI", "Kubernetes", "Python", "React", "PostgreSQL"}]
    # Appearance order in the JD: FastAPI, Kubernetes, Python, React, PostgreSQL.
    assert tech_subset == ["FastAPI", "Kubernetes", "Python", "React", "PostgreSQL"]


def test_jd_fallback_capitalized_tokens_fill_remaining_slots(tmp_path: Path) -> None:
    """Pass-2 picks capitalized tokens the priority list didn't catch —
    product names, proprietary tools, etc."""
    jd = _write_jd(tmp_path, "Working on Acme Platform with Postgres and internal Frobnicator")
    got = parse_jd_keywords(jd)
    # Postgres is in priority list; Acme/Frobnicator come in via pass-2.
    assert "PostgreSQL" in got or "Postgres" in got
    assert "Acme" in got
    assert "Frobnicator" in got


def test_jd_stopwords_never_leak(tmp_path: Path) -> None:
    """Pass-2 filters structural JD words (About, Requirements, Senior, Remote, …)
    so those don't burn keyword slots."""
    jd = _write_jd(
        tmp_path,
        "About us. Requirements include Senior Engineer, Remote OK, Python.",
    )
    got = parse_jd_keywords(jd)
    assert "About" not in got
    assert "Requirements" not in got
    assert "Senior" not in got
    assert "Remote" not in got
    assert "Engineer" not in got
    assert "Python" in got  # real signal still captured


def test_jd_limit_caps_total_output(tmp_path: Path) -> None:
    jd = _write_jd(
        tmp_path,
        "Python, TypeScript, React, Vue, Django, FastAPI, PostgreSQL, Redis, "
        "Docker, Kubernetes, AWS, GCP, Terraform",
    )
    assert len(parse_jd_keywords(jd, limit=3)) == 3
    # With limit >= real hits, we just get everything.
    assert len(parse_jd_keywords(jd, limit=100)) <= 100


def test_jd_no_duplicates_across_passes(tmp_path: Path) -> None:
    """If a token appears both in the priority list AND as a plain
    capitalized token, it only shows up once."""
    jd = _write_jd(tmp_path, "React React React and more React")
    got = parse_jd_keywords(jd)
    assert got.count("React") == 1


def test_jd_empty_file_returns_empty_list(tmp_path: Path) -> None:
    assert parse_jd_keywords(_write_jd(tmp_path, "")) == []


# ─────────────────────── sparkline ────────────────────────────────────────


def test_sparkline_empty_is_empty_string() -> None:
    assert sparkline([]) == ""


def test_sparkline_constant_series_is_flat_middle_band() -> None:
    """Zero span → don't divide by zero; render a flat band at the middle
    of the 8-char ramp, one glyph per value (up to width)."""
    got = sparkline([5.0, 5.0, 5.0, 5.0])
    assert len(got) == 4
    assert len(set(got)) == 1  # all same character


def test_sparkline_ramp_maps_min_and_max_to_endpoints() -> None:
    got = sparkline([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    # Eight equally-spaced values → one of each of the 8 glyphs, in order.
    assert got[0] == "\u2581"  # lowest block
    assert got[-1] == "\u2588"  # full block


def test_sparkline_downsamples_when_longer_than_width() -> None:
    long_series = list(range(100))
    got = sparkline([float(v) for v in long_series], width=10)
    assert len(got) == 10


def test_sparkline_short_series_keeps_every_point() -> None:
    got = sparkline([1.0, 2.0, 3.0], width=24)
    assert len(got) == 3


# ─────────────────────── load_reviews_by_locale ───────────────────────────


def _stub_report(locale: str) -> ReviewReport:
    return ReviewReport(
        source="resume_v001.md",
        locale=locale,
        total=80,
        max_total=100,
        scores=[Score(name="check", score=8, max=10)],
    )


def _write_review_json(dir_: Path, version: int, locale: str) -> None:
    r = _stub_report(locale)
    r.source = f"resume_v{version:03d}.md"
    (dir_ / f"resume_v{version:03d}_review.json").write_text(
        json.dumps(r.as_dict()), encoding="utf-8"
    )


def test_load_reviews_missing_dir_is_empty_map(tmp_path: Path) -> None:
    assert load_reviews_by_locale(tmp_path / "never_created") == {}


def test_load_reviews_groups_by_locale_and_sorts_ascending(tmp_path: Path) -> None:
    _write_review_json(tmp_path, 3, "en_US")
    _write_review_json(tmp_path, 1, "en_US")
    _write_review_json(tmp_path, 2, "en_US")
    _write_review_json(tmp_path, 5, "zh_TW")

    got = load_reviews_by_locale(tmp_path)
    en_versions = [v for v, _ in got["en_US"]]
    assert en_versions == [1, 2, 3]
    assert [v for v, _ in got["zh_TW"]] == [5]


def test_load_reviews_skips_corrupt_json(tmp_path: Path) -> None:
    """A hand-truncated review file shouldn't abort the whole scan —
    the bar is 'make the trend command not crash on the ugly-but-salvageable
    case'."""
    _write_review_json(tmp_path, 1, "en_US")
    (tmp_path / "resume_v002_review.json").write_text("not json", encoding="utf-8")
    got = load_reviews_by_locale(tmp_path)
    assert [v for v, _ in got["en_US"]] == [1]


# ─────────────────────── find_previous_review ─────────────────────────────


def test_find_previous_missing_dir_returns_none(tmp_path: Path) -> None:
    got = find_previous_review(tmp_path / "nope", "resume_v005.md", "en_US")
    assert got is None


def test_find_previous_picks_highest_smaller_version_same_locale(
    tmp_path: Path,
) -> None:
    _write_review_json(tmp_path, 1, "en_US")
    _write_review_json(tmp_path, 3, "en_US")  # expected match
    _write_review_json(tmp_path, 4, "en_US")  # same version — excluded (strict <)
    _write_review_json(tmp_path, 2, "zh_TW")  # wrong locale

    got = find_previous_review(tmp_path, "resume_v004.md", "en_US")
    assert got is not None
    assert got.source == "resume_v003.md"


def test_find_previous_strictly_less_than_current(tmp_path: Path) -> None:
    """A review for the SAME version number is not a 'previous' review."""
    _write_review_json(tmp_path, 4, "en_US")
    got = find_previous_review(tmp_path, "resume_v004.md", "en_US")
    assert got is None


def test_find_previous_ignores_other_locale(tmp_path: Path) -> None:
    """Trend diffs only make sense within a locale (the 8-point scorecard
    varies by locale-specific red-flag rules)."""
    _write_review_json(tmp_path, 1, "zh_TW")
    _write_review_json(tmp_path, 2, "zh_TW")
    got = find_previous_review(tmp_path, "resume_v003.md", "en_US")
    assert got is None


def test_find_previous_current_source_without_version_number(tmp_path: Path) -> None:
    """If the current source doesn't look like `resume_vNNN.md`, we can't
    compute 'previous' — returns None rather than raising."""
    _write_review_json(tmp_path, 1, "en_US")
    got = find_previous_review(tmp_path, "hand-uploaded.md", "en_US")
    assert got is None
