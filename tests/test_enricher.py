"""Unit tests for core.enricher prompt + template dispatch."""
from __future__ import annotations

from datetime import datetime

import pytest

from vibe_resume.core.enricher import (
    PROMPT_TEMPLATE_NOUN_PHRASE,
    PROMPT_TEMPLATE_XYZ,
    _build_prompt,
    _fallback_summary,
    _pick_template,
)
from vibe_resume.core.schema import Activity, ProjectGroup, Source
from vibe_resume.render.i18n import get_locale


def _ext_group():
    a = Activity(source=Source.GITHUB, session_id="facebook/react#1",
                 timestamp_start="2026-01-01T00:00:00+00:00",
                 project="facebook/react", summary="fixed a reconciler bug",
                 extra={"repo": "facebook/react", "contribution": "external",
                        "merged": True})
    return ProjectGroup(name="react", first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=1, activities=[a])


def _owned_group():
    a = Activity(source=Source.GITHUB, session_id="me/app#1",
                 timestamp_start="2026-01-01T00:00:00+00:00",
                 project="me/app", summary="built dashboard",
                 extra={"repo": "me/app", "contribution": "owned", "merged": True})
    return ProjectGroup(name="app", first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=1, activities=[a])


def test_external_group_prompt_says_contributed_to():
    assert "contributed to" in _build_prompt(_ext_group()).lower()


def test_owned_group_prompt_has_no_contribution_framing():
    assert "contributed to" not in _build_prompt(_owned_group()).lower()


def _many_act_group(n):
    acts = [Activity(source=Source.GIT, session_id=f"s{i}",
                     timestamp_start="2026-01-01T00:00:00+00:00",
                     summary=f"activity-{i} " + "x" * 400) for i in range(n)]
    return ProjectGroup(name="big", first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=n, activities=acts)


def test_build_prompt_default_window():
    g = _many_act_group(30)
    p = _build_prompt(g)
    assert "activity-11" in p          # first 12 included (0..11)
    assert "activity-12" not in p      # 13th excluded by default cap 12


def test_build_prompt_wider_window():
    g = _many_act_group(30)
    p = _build_prompt(g, max_activities=20, char_budget=500)
    assert "activity-19" in p          # 20 activities now included
    # 500-char budget keeps more of each line than the 200 default
    assert p.count("x" * 300) >= 1


def _sample_group() -> ProjectGroup:
    return ProjectGroup(
        name="rag-search-platform",
        path="~/Code/lumen/rag-search",
        first_activity=datetime(2024, 2, 14, 9, 12),
        last_activity=datetime(2026, 4, 18, 20, 40),
        total_sessions=184,
        tech_stack=["Python", "FastAPI", "PostgreSQL", "pgvector"],
        sources=[Source.CLAUDE_CODE, Source.CURSOR, Source.GIT],
        category_counts={"backend": 78, "frontend": 42, "devops": 26},
        capability_breadth=3,
    )


class TestPickTemplate:
    def test_en_us_uses_xyz_template_and_english_label(self):
        tpl, lang = _pick_template(get_locale("en_US"))
        assert tpl is PROMPT_TEMPLATE_XYZ
        assert lang == "English"

    def test_zh_tw_uses_noun_phrase_and_traditional_chinese_label(self):
        tpl, lang = _pick_template(get_locale("zh_TW"))
        assert tpl is PROMPT_TEMPLATE_NOUN_PHRASE
        assert lang == "繁體中文"

    def test_ja_jp_uses_noun_phrase_and_japanese_label(self):
        tpl, lang = _pick_template(get_locale("ja_JP"))
        assert tpl is PROMPT_TEMPLATE_NOUN_PHRASE
        assert lang == "日本語"

    def test_de_de_uses_noun_phrase_and_german_label(self):
        tpl, lang = _pick_template(get_locale("de_DE"))
        assert tpl is PROMPT_TEMPLATE_NOUN_PHRASE
        assert lang == "Deutsch"

    def test_zh_cn_special_cases_to_simplified_chinese_label(self):
        # Both zh_TW and zh_CN share `language: "zh"` but zh_CN must say 简体
        tpl, lang = _pick_template(get_locale("zh_CN"))
        assert tpl is PROMPT_TEMPLATE_NOUN_PHRASE
        assert lang == "简体中文"


class TestBuildPrompt:
    def test_en_us_prompt_mentions_english(self):
        prompt = _build_prompt(_sample_group(), get_locale("en_US"))
        assert "English" in prompt
        # XYZ prompt has a known header line
        assert "Google XYZ formula" in prompt

    def test_ja_jp_prompt_mentions_japanese_label(self):
        prompt = _build_prompt(_sample_group(), get_locale("ja_JP"))
        # The {lang_label} placeholder must be substituted with actual "日本語"
        assert "日本語" in prompt
        # Anti-leak rule must be present so LLM knows not to output 简体
        assert "全栈" in prompt  # appears in the "禁止" example list
        assert "フルスタック" in prompt

    def test_de_de_prompt_mentions_deutsch(self):
        prompt = _build_prompt(_sample_group(), get_locale("de_DE"))
        assert "Deutsch" in prompt

    def test_prompt_contains_group_metadata(self):
        g = _sample_group()
        prompt = _build_prompt(g, get_locale("en_US"))
        assert g.name in prompt
        # project session count is surfaced as a number in the prompt
        assert "184" in prompt
        # tech stack is listed
        assert "FastAPI" in prompt

    def test_default_locale_is_en_us(self):
        # Passing no locale_meta should default to en_US (XYZ)
        prompt = _build_prompt(_sample_group())
        assert "English" in prompt
        assert "Google XYZ formula" in prompt


class TestFallbackSummary:
    def test_fallback_summary_includes_project_name(self):
        g = _sample_group()
        fb = _fallback_summary(g)
        assert g.name in fb["summary"]
        assert fb["achievements"] == []
        # tech_stack is passed through from the group
        assert fb["tech_stack"] == g.tech_stack


def test_build_prompt_includes_emphasis_block_last():
    from vibe_resume.core.emphasis import EmphasisRecord
    g = _many_act_group(3)
    em = EmphasisRecord(intent="security + agents", keywords=["MCP"],
                        bias_instruction="Lead with the trade-off.")
    p = _build_prompt(g, emphasis=em)
    assert "HIGHEST-PRIORITY EMPHASIS" in p
    assert "security + agents" in p and "MCP" in p


def test_build_prompt_no_emphasis_block_when_absent():
    g = _many_act_group(3)
    assert "HIGHEST-PRIORITY EMPHASIS" not in _build_prompt(g)
