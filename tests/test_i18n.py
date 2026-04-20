"""Unit tests for render.i18n: format_date + localized."""
from __future__ import annotations

import pytest

from render.i18n import format_date, format_date_range, localized, resolve_locale


class TestFormatDate:
    def test_iso_yyyy_mm_to_en_us_returns_month_name(self):
        # en_US uses "%b %Y" → "Feb 2024"
        assert format_date("2024-02", "en_US") == "Feb 2024"

    def test_iso_yyyy_mm_dd_to_zh_tw_uses_slash(self):
        # zh_TW uses "%Y/%m" → "2024/02"
        assert format_date("2024-02-14", "zh_TW") == "2024/02"

    def test_iso_yyyy_mm_to_ja_jp_uses_kanji(self):
        # ja_JP uses "%Y年%m月" → "2024年02月"
        assert format_date("2024-02", "ja_JP") == "2024年02月"

    def test_present_token_normalized_per_language(self):
        # All locales should map "Present" to their native equivalent
        assert format_date("Present", "en_US") == "Present"
        assert format_date("Present", "zh_TW") == "現在"
        assert format_date("Present", "ja_JP") == "現在"
        assert format_date("Present", "de_DE") == "heute"

    def test_chinese_present_token_normalized(self):
        # Already-native token should pass through unchanged
        assert format_date("現在", "zh_TW") == "現在"

    def test_unparseable_returns_original(self):
        # No silent loss of content
        assert format_date("not-a-date", "en_US") == "not-a-date"
        assert format_date("", "en_US") == ""
        assert format_date(None, "en_US") == ""

    def test_format_date_range_uses_locale_separator(self):
        # ja_JP separator is "～"
        out = format_date_range("2024-02", "Present", "ja_JP")
        assert "2024年02月" in out
        assert "現在" in out
        assert "～" in out


class TestLocalized:
    def test_returns_locale_specific_when_present(self):
        obj = {"title": "Engineer", "title_zh_TW": "工程師"}
        assert localized(obj, "title", "zh_TW") == "工程師"

    def test_falls_back_to_canonical_when_missing(self):
        obj = {"title": "Engineer"}
        assert localized(obj, "title", "zh_TW") == "Engineer"

    def test_falls_back_when_locale_value_is_empty_string(self):
        # Empty string is falsy → falls through to canonical
        obj = {"title": "Engineer", "title_zh_TW": ""}
        assert localized(obj, "title", "zh_TW") == "Engineer"

    def test_returns_none_when_neither_key_present(self):
        obj = {"name": "Alex"}
        assert localized(obj, "title", "zh_TW") is None

    def test_aliases_resolve(self):
        # zh-TW alias should map to zh_TW canonical
        assert resolve_locale("zh-TW") == "zh_TW"
        assert resolve_locale("zh-Hant") == "zh_TW"
        assert resolve_locale("ja") == "ja_JP"
        assert resolve_locale(None) == "en_US"
        assert resolve_locale("nonsense") == "en_US"
