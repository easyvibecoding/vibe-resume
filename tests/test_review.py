"""Unit tests for core.review heuristic checks."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.review import (
    _check_numbers_per_bullet,
    _check_red_flags,
    _check_top_fold,
    review,
)
from render.i18n import get_locale

GOOD_HEAD = """\
# Alex Chen
Senior Full-stack Engineer

Taipei, Taiwan | alex@example.com | +886-912-345-678

**Target role:** Senior Full-stack Engineer

## Summary
Compressed design-to-deploy cycles by ~40% across the last three launches.
"""

NO_METRIC_HEAD = """\
# Alex Chen
Senior Full-stack Engineer

Taipei, Taiwan | alex@example.com

**Target role:** Senior Full-stack Engineer

## Summary
Full-stack engineer who ships end-to-end features.
"""


class TestTopFold:
    def test_full_score_with_name_role_metric(self):
        s = _check_top_fold(GOOD_HEAD)
        assert s.score == 10

    def test_partial_when_no_metric_in_head(self):
        s = _check_top_fold(NO_METRIC_HEAD)
        # name (3) + target role (3) — but no metric → 6/10
        assert s.score == 6
        assert any("metric" in n.lower() or "outcome" in n.lower() for n in s.notes)

    def test_partial_when_no_target_role(self):
        md = "# Alex Chen\nFull-stack\n\nLatency cut 40%."
        s = _check_top_fold(md)
        # name (3) + metric (4) — but no target role line → 7/10
        assert s.score == 7


class TestNumbersPerBullet:
    def test_full_score_when_all_bullets_metric(self):
        md = """## Experience

- Reduced query latency from 1.8s to 620ms.
- Cut MTTR by 35% across pilot teams.
- Grew GitHub stars to 1.2k in 9 months.
"""
        s = _check_numbers_per_bullet(md)
        assert s.score == 10
        assert "100%" in s.notes[0]

    def test_low_score_when_few_bullets_have_metrics(self):
        md = """## Experience

- Worked on the search feature.
- Helped the platform team.
- Cut latency by 40%.
"""
        s = _check_numbers_per_bullet(md)
        # 1/3 = 33% of 60% target → score = round(33/60 * 10) = 6 (heuristic)
        assert s.score < 10
        # examples should surface bullet line numbers
        assert any("L" in n for n in s.notes)

    def test_irrelevant_section_bullets_excluded(self):
        # Bullets under "Awards" / "Certifications" should not count
        md = """## Experience

- Reduced query latency from 1.8s to 620ms.

## Awards
- COSCUP 2024 Best Lightning Talk.

## Certifications
- AWS Certified Solutions Architect.
"""
        s = _check_numbers_per_bullet(md)
        # only 1 in-scope bullet, and it has a metric → 100%
        assert "1/1" in s.notes[0]


class TestRedFlags:
    def test_photo_forbidden_with_image_loses_points(self):
        md = "# Alex\n\n![photo](headshot.png)\n\n## Experience\n- Did stuff\n"
        loc = get_locale("en_US")  # photo: forbidden
        s = _check_red_flags(md, loc)
        assert s.score < 10
        assert any("photo" in n.lower() for n in s.notes)

    def test_references_phrase_loses_points(self):
        md = "# Alex\n\n## Experience\n- Did stuff\n\nReferences available upon request.\n"
        loc = get_locale("en_US")
        s = _check_red_flags(md, loc)
        assert s.score < 10
        assert any("reference" in n.lower() for n in s.notes)

    def test_clean_resume_full_score(self):
        md = "# Alex\n\n## Summary\nGreat engineer.\n\n## Experience\n- Reduced latency 40%.\n"
        loc = get_locale("en_US")
        s = _check_red_flags(md, loc)
        assert s.score == 10

    def test_photo_expected_locale_warns_when_missing(self):
        md = "# Alex\n\n## Summary\nGreat engineer.\n"
        loc = get_locale("ja_JP")  # photo: expected
        s = _check_red_flags(md, loc)
        assert s.score < 10
        assert any("photo" in n.lower() for n in s.notes)


class TestJdKeywords:
    def test_stopwords_excluded(self, tmp_path):
        from core.review import parse_jd_keywords

        jd = tmp_path / "jd.txt"
        jd.write_text(
            "About the role\nWe are hiring a Senior Full-stack Engineer — Remote / Taipei.\n"
            "Stack: React, FastAPI, PostgreSQL, Docker.\n"
        )
        kws = parse_jd_keywords(jd)
        # structural / seniority / geography words must NOT show up
        for bad in ("About", "Remote", "Senior", "Engineer", "Taipei"):
            assert bad not in kws, f"stopword {bad!r} leaked into {kws}"

    def test_tech_priority_ordered_by_first_appearance(self, tmp_path):
        from core.review import parse_jd_keywords

        jd = tmp_path / "jd.txt"
        # Docker appears first in prose, then FastAPI, then React
        jd.write_text("Deploy with Docker to AWS. Use FastAPI on the backend. React on the client.\n")
        kws = parse_jd_keywords(jd, limit=6)
        # Docker should come before FastAPI before React (first-appearance order)
        assert kws.index("Docker") < kws.index("FastAPI") < kws.index("React")

    def test_respects_limit(self, tmp_path):
        from core.review import parse_jd_keywords

        jd = tmp_path / "jd.txt"
        jd.write_text("React FastAPI PostgreSQL Docker Kubernetes Redis AWS Stripe pgvector RAG\n")
        kws = parse_jd_keywords(jd, limit=3)
        assert len(kws) == 3


class TestFindPreviousReview:
    def _write_review(self, path: Path, version: int, locale: str, total: int = 50, max_total: int = 60) -> None:
        import json

        path.write_text(
            json.dumps(
                {
                    "source": f"resume_v{version:03d}_{locale}.md" if locale != "en_US" else f"resume_v{version:03d}.md",
                    "locale": locale,
                    "total": total,
                    "max_total": max_total,
                    "grade": "B",
                    "scores": [],
                }
            )
        )

    def test_returns_most_recent_previous_same_locale(self, tmp_path):
        from core.review import find_previous_review

        # v005 zh_TW, v007 zh_TW — finding prior for v010_zh_TW should return v007
        self._write_review(tmp_path / "resume_v005_zh_TW_review.json", 5, "zh_TW", total=40)
        self._write_review(tmp_path / "resume_v007_zh_TW_review.json", 7, "zh_TW", total=48)
        self._write_review(tmp_path / "resume_v009_zh_TW_review.json", 9, "zh_TW", total=55)

        prev = find_previous_review(tmp_path, "resume_v010_zh_TW.md", "zh_TW")
        assert prev is not None
        assert prev.total == 55  # v009 is the most recent earlier version

    def test_ignores_other_locales(self, tmp_path):
        from core.review import find_previous_review

        self._write_review(tmp_path / "resume_v005_zh_TW_review.json", 5, "zh_TW", total=40)
        self._write_review(tmp_path / "resume_v007_review.json", 7, "en_US", total=60)
        # asking for en_US previous of v010 should ignore v005 zh_TW
        prev = find_previous_review(tmp_path, "resume_v010.md", "en_US")
        assert prev is not None
        assert prev.total == 60
        assert prev.locale == "en_US"

    def test_returns_none_when_nothing_prior(self, tmp_path):
        from core.review import find_previous_review

        # only a *later* version exists
        self._write_review(tmp_path / "resume_v020_zh_TW_review.json", 20, "zh_TW")
        prev = find_previous_review(tmp_path, "resume_v010_zh_TW.md", "zh_TW")
        assert prev is None


class TestReviewReportGrade:
    def test_grade_boundaries(self):
        from core.review import ReviewReport, Score

        def mk(total: int, max_total: int = 60) -> ReviewReport:
            return ReviewReport(source="x", locale="en_US", total=total, max_total=max_total, scores=[])

        assert mk(60).grade == "A"   # 100%
        assert mk(54).grade == "A"   # 90%
        assert mk(53).grade == "B"   # 88%
        assert mk(48).grade == "B"   # 80%
        assert mk(47).grade == "C"   # 78%
        assert mk(36).grade == "D"   # 60%
        assert mk(29).grade == "F"   # 48%


class TestEndToEnd:
    def test_review_produces_grade_a_for_well_formed_resume(self):
        md = (
            GOOD_HEAD
            + "\n## Experience\n"
            + "- Reduced query latency from 1.8s to 620ms via pgvector HNSW.\n"
            + "- Cut MTTR by 35% by deploying Sentry triage agent.\n"
            + "- Lifted Recall@10 by 14% via prompt-ensemble rerank.\n"
        )
        report = review(md, "en_US")
        # Top fold + numbers + verbs + clean = ≥80% (B or better)
        assert report.total / report.max_total >= 0.8
        assert report.grade in {"A", "B"}
