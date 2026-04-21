"""End-to-end tests for core.review.review() — the 8-point scorer that
produces the user-visible A/B/C grade on every render.

These exercise the public API (markdown in → ReviewReport out) rather
than internal `_check_*` functions, so they pin the composition rules
that users actually see.
"""
from __future__ import annotations

import pytest

from core.review import ReviewReport, review


def _score(report: ReviewReport, name: str):
    """Helper: find a Score by name in the report."""
    for s in report.scores:
        if s.name == name:
            return s
    raise KeyError(f"no score named {name!r}; have {[s.name for s in report.scores]}")


# ─────────────────────── happy path ───────────────────────────────────────


GOOD_RESUME_EN_US = """# Alex Chen
_Senior Software Engineer_

**Target role**: Staff Engineer — Platform

- Built auth service handling 4.2M requests/day with p99 latency 180ms.
- Migrated monolith to 12 microservices, cutting deploy time from 42 min to 6 min.
- Led 4-engineer team on AI-assisted review workflow, reducing PR rounds by 35%.
- Designed rate limiter saving $12k/mo in upstream API costs.

## Technical skills

Go, Python, TypeScript, Kubernetes, PostgreSQL
"""


def test_good_en_us_resume_grades_b_or_higher() -> None:
    """A résumé that hits every contract (H1, target role, metric in top fold,
    verb-first bullets, metric-per-bullet) should clear the B/80% bar."""
    report = review(GOOD_RESUME_EN_US, "en_US")
    assert report.grade in ("A", "B"), f"got {report.grade} with scores {[(s.name, s.score, s.max) for s in report.scores]}"
    assert report.total / report.max_total >= 0.75


def test_minimal_resume_grades_poorly() -> None:
    """A one-line 'resume' can't hit any of the 8 rubrics."""
    report = review("Alex Chen\n\n(contact me)\n", "en_US")
    assert report.grade in ("D", "F", "C")


# ─────────────────────── top-fold contract ───────────────────────────────


def test_missing_h1_name_loses_top_fold_points() -> None:
    """No H1 → reviewer can't find the candidate name at a glance."""
    md = """Alex Chen (plain text, no heading)

**Target role**: Staff Engineer

- Shipped feature with 80% adoption.
"""
    s = _score(review(md, "en_US"), "Top fold")
    assert "H1 name not found" in " ".join(s.notes)


def test_missing_target_role_loses_top_fold_points() -> None:
    md = """# Alex Chen
_Senior Engineer_

- Shipped feature with 80% adoption in the first week.
"""
    s = _score(review(md, "en_US"), "Top fold")
    assert any("target-role" in n for n in s.notes)


def test_no_metrics_in_top_fold_loses_points() -> None:
    """Even with H1 + target role, the top fold needs ONE concrete outcome —
    otherwise a reviewer's 10-second skim sees nothing measurable."""
    md = """# Alex Chen

**Target role**: Staff Engineer

- Worked on the auth service.
- Collaborated with teams.
"""
    s = _score(review(md, "en_US"), "Top fold")
    assert any("no measurable outcome" in n for n in s.notes)


# ─────────────────────── numbers-per-bullet ──────────────────────────────


def test_all_metric_less_bullets_scores_zero() -> None:
    md = """# Alex Chen

**Target role**: SWE

## Experience

- Worked on auth.
- Contributed to the deploy system.
- Collaborated with product.
"""
    s = _score(review(md, "en_US"), "Numbers per bullet")
    assert s.score == 0
    assert "0/3 bullets" in " ".join(s.notes)


def test_all_bullets_with_metrics_scores_max() -> None:
    md = """# Alex Chen

**Target role**: SWE

## Experience

- Built system handling 4.2M/day.
- Cut deploy time 42min to 6min.
- Reduced PR rounds by 35%.
"""
    s = _score(review(md, "en_US"), "Numbers per bullet")
    assert s.score == 10


# ─────────────────────── keyword echo (JD) ───────────────────────────────


def test_keyword_echo_skipped_when_no_jd() -> None:
    """Without a JD we can't score keyword echo; the check should report
    max=0 (skipped) rather than max=10 score=0 (failed)."""
    s = _score(review(GOOD_RESUME_EN_US, "en_US"), "Keyword echo (JD)")
    assert s.max == 0


def test_keyword_echo_counts_case_insensitive_hits() -> None:
    s = _score(
        review(GOOD_RESUME_EN_US, "en_US", jd_keywords=["Python", "Go", "PostgreSQL", "Rust"]),
        "Keyword echo (JD)",
    )
    # Python, Go, PostgreSQL present (3/4) → 75% → 8/10
    assert s.score >= 7
    assert s.max == 10
    assert "Rust" in " ".join(s.notes)  # flagged as missing


def test_keyword_echo_all_missing_scores_zero() -> None:
    s = _score(
        review(GOOD_RESUME_EN_US, "en_US", jd_keywords=["Kotlin", "Haskell", "Lisp"]),
        "Keyword echo (JD)",
    )
    assert s.score == 0


# ─────────────────────── action-verb vs density by locale ────────────────


def test_action_verb_check_only_fires_for_xyz_locales() -> None:
    """zh_TW is noun_phrase; action-verb must be skipped (max=0), not
    score zero against rules that don't apply to the locale."""
    md = "# 陳柏翰\n\n**應徵職位**: 資深工程師\n\n- 整合支付閘道,QPS 3k/s。\n"
    report = review(md, "zh_TW")
    action = _score(report, "Action-verb first")
    density = _score(report, "Density (noun-phrase)")
    assert action.max == 0, "action-verb should be n/a for zh_TW"
    assert density.max == 10, "density SHOULD score for zh_TW"


def test_density_check_only_fires_for_noun_phrase_locales() -> None:
    report = review(GOOD_RESUME_EN_US, "en_US")
    action = _score(report, "Action-verb first")
    density = _score(report, "Density (noun-phrase)")
    assert action.max == 10, "en_US is xyz → action-verb should score"
    assert density.max == 0, "density n/a for en_US"


def test_action_verb_flags_non_verb_openers() -> None:
    md = """# Alex

**Target role**: SWE

- The auth service shipped successfully with 80% adoption.
- A new deployment pipeline cut time by 40%.
- It handles 4M requests per day.
"""
    s = _score(review(md, "en_US"), "Action-verb first")
    # None of the bullets start with a verb (the / a / it) → low score.
    assert s.score <= 3
    assert "non-verb openers:" in " ".join(s.notes)


def test_density_flags_dangling_pronouns_in_zh_tw() -> None:
    md = """# 陳柏翰

**應徵職位**: 資深工程師

## 工作經歷

- 這個系統處理 4M/天的請求。
- 那次重構讓部署時間從 42 分降到 6 分。
"""
    s = _score(review(md, "zh_TW"), "Density (noun-phrase)")
    # Both bullets start with a pronoun (這 / 那).
    assert "dangling pronoun" in " ".join(s.notes) or s.score < 5


# ─────────────────────── red flags ───────────────────────────────────────


def test_red_flag_fires_for_references_upon_request() -> None:
    md = GOOD_RESUME_EN_US + "\n\nReferences available upon request.\n"
    s = _score(review(md, "en_US"), "Red flags")
    # Score is out of 10; a red flag pulls it down below max.
    assert s.score < 10
    assert any("references" in n.lower() for n in s.notes)


# ─────────────────────── ReviewReport API ────────────────────────────────


@pytest.mark.parametrize(
    "total, maximum, grade",
    [
        (100, 100, "A"),
        (95, 100, "A"),
        (90, 100, "A"),
        (89, 100, "B"),
        (80, 100, "B"),
        (79, 100, "C"),
        (70, 100, "C"),
        (69, 100, "D"),
        (60, 100, "D"),
        (59, 100, "F"),
        (0, 100, "F"),
    ],
)
def test_grade_thresholds(total: int, maximum: int, grade: str) -> None:
    r = ReviewReport(source="t", locale="en_US", total=total, max_total=maximum, scores=[])
    assert r.grade == grade


def test_grade_returns_na_for_zero_max_total() -> None:
    """An all-skipped scorecard shouldn't divide by zero — the `.grade`
    accessor handles it gracefully."""
    r = ReviewReport(source="t", locale="en_US", total=0, max_total=0, scores=[])
    assert r.grade == "n/a"


def test_as_dict_roundtrips_through_from_dict() -> None:
    """Reviews are persisted as JSON and re-read for trend display; the
    dataclass must round-trip losslessly."""
    original = review(GOOD_RESUME_EN_US, "en_US")
    reconstructed = ReviewReport.from_dict(original.as_dict())
    assert reconstructed.total == original.total
    assert reconstructed.locale == original.locale
    assert len(reconstructed.scores) == len(original.scores)
    assert reconstructed.scores[0].name == original.scores[0].name


def test_review_excludes_skipped_checks_from_grade_math() -> None:
    """Only `max > 0` scores count toward the denominator, so locale-specific
    checks (action-verb / density) never falsely lower the grade when they
    don't apply."""
    report = review(GOOD_RESUME_EN_US, "en_US")  # no JD → keyword echo skipped
    max_total_by_included = sum(s.max for s in report.scores if s.max > 0)
    assert report.max_total == max_total_by_included
