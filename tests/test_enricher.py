"""Unit tests for core.enricher prompt + template dispatch."""
from __future__ import annotations

from datetime import datetime

import pytest

from core.enricher import (
    PROMPT_TEMPLATE_NOUN_PHRASE,
    PROMPT_TEMPLATE_XYZ,
    _build_prompt,
    _fallback_summary,
    _pick_template,
)
from core.schema import ProjectGroup, Source
from render.i18n import get_locale


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
