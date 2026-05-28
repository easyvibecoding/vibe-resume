"""Trend grouping by (locale, persona) — Issue #15."""
from __future__ import annotations

import json


def _seed(tmp_path, name, total, locale):
    (tmp_path / name).write_text(json.dumps({
        "source": name.replace("_review.json", ".md"),
        "locale": locale, "total": total, "max_total": 70, "scores": [],
    }))


def test_groups_by_locale_persona(tmp_path):
    from core.review import load_reviews_by_locale_persona
    _seed(tmp_path, "resume_v001_en_US_tech_lead_review.json", 60, "en_US")
    _seed(tmp_path, "resume_v002_en_US_hr_review.json", 62, "en_US")
    _seed(tmp_path, "resume_v003_zh_TW_tech_lead_review.json", 55, "zh_TW")
    grouped = load_reviews_by_locale_persona(tmp_path)
    assert ("en_US", "tech_lead") in grouped
    assert ("en_US", "hr") in grouped
    assert ("zh_TW", "tech_lead") in grouped


def test_no_persona_suffix_maps_to_none(tmp_path):
    from core.review import load_reviews_by_locale_persona
    _seed(tmp_path, "resume_v001_en_US_review.json", 50, "en_US")
    grouped = load_reviews_by_locale_persona(tmp_path)
    assert ("en_US", None) in grouped
