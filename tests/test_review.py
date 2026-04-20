"""Unit tests for core.review heuristic checks."""
from __future__ import annotations

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
