"""Additional i18n tests, complementing tests/test_i18n.py.

test_i18n.py already covers the happy-path date formatting + the most
common localized()/resolve_locale cases. This file fills in:
- resolve_locale: alias table coverage, hyphen/underscore, case-insensitive
- get_locale: _key canonicalization + headings deep-merge fallback
- format_date: empty-string edge, whitespace, present-token locale mapping
  variants, unparseable passthrough
- format_date_range: western dash, one-side-empty behaviour
- localized: None passthrough + non-dict object getattr path
"""
from __future__ import annotations

import pytest

from render.i18n import (
    LOCALES,
    format_date,
    format_date_range,
    get_locale,
    localized,
    resolve_locale,
)

# ─────────────────────── resolve_locale — extra coverage ──────────────────


@pytest.mark.parametrize("key", list(LOCALES.keys()))
def test_every_canonical_locale_round_trips(key: str) -> None:
    """Adding a new locale to LOCALES without wiring it through resolve_locale
    would silently break this test."""
    assert resolve_locale(key) == key


@pytest.mark.parametrize(
    "alias, expected",
    [
        ("en", "en_US"),
        ("en-US", "en_US"),
        ("en-GB", "en_GB"),
        ("zh-CN", "zh_CN"),
        ("zh-Hans", "zh_CN"),
        ("zh-HK", "zh_HK"),
        ("zh-Hant-HK", "zh_HK"),
        ("ja-JP", "ja_JP"),
        ("de", "de_DE"),
        ("fr", "fr_FR"),
        ("ko", "ko_KR"),
    ],
)
def test_alias_table_completeness(alias: str, expected: str) -> None:
    """Each alias user agents / IDEs commonly emit must resolve to a
    canonical key. Losing one would surprise users who pass BCP-47 style."""
    assert resolve_locale(alias) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ZH_TW", "zh_TW"),
        ("zh-tw", "zh_TW"),
        ("JA_JP", "ja_JP"),
        ("Ja-JP", "ja_JP"),
        ("DE_DE", "de_DE"),
    ],
)
def test_case_and_separator_folding(raw: str, expected: str) -> None:
    """resolve_locale case-folds AND normalizes `-` → `_` before matching."""
    assert resolve_locale(raw) == expected


def test_empty_string_also_falls_back() -> None:
    """Empty string is the common "user pressed Enter without a value" case;
    must behave like None."""
    assert resolve_locale("") == "en_US"


# ─────────────────────── get_locale ───────────────────────────────────────


def test_get_locale_sets_canonical_key_field() -> None:
    assert get_locale("ja_JP")["_key"] == "ja_JP"
    assert get_locale("zh-TW")["_key"] == "zh_TW"  # alias resolves through


def test_get_locale_unknown_falls_back_to_en_us() -> None:
    loc = get_locale("xx_YY")
    assert loc["_key"] == "en_US"


def test_get_locale_headings_fallback_to_en_us_when_override_missing() -> None:
    """Templates rely on every heading key being non-None. Deep merge must
    backfill any headings a new locale didn't translate yet — otherwise the
    rendered résumé would show a bare `None` above a section."""
    en_headings = set(LOCALES["en_US"]["headings"].keys())
    for locale_key in LOCALES:
        loc = get_locale(locale_key)
        got = set(loc["headings"].keys())
        missing = en_headings - got
        assert not missing, (
            f"{locale_key}: missing heading fallback for {sorted(missing)!r} "
            "— get_locale's deep-merge should have backfilled from en_US"
        )


# ─────────────────────── format_date — extra edge cases ───────────────────


def test_format_date_whitespace_only_is_empty() -> None:
    assert format_date("   ", "en_US") == ""


def test_format_date_full_iso_datetime_strips_time() -> None:
    """Callers sometimes hand us a full ISO timestamp from the Activity
    model (`2026-04-21T10:00:00`); we must not leak the `T00:00:00` tail."""
    got = format_date("2026-04-21T10:00:00", "en_US")
    assert "T" not in got
    assert "2026" in got


def test_format_date_year_only_parses() -> None:
    """`2025` alone should parse as Jan 2025, not fall through as literal."""
    got = format_date("2025", "en_US")
    assert "2025" in got


def test_format_date_slash_separator_parses() -> None:
    """YYYY/MM is a common non-ISO-strict variant (Excel export style)."""
    got = format_date("2026/04", "en_US")
    assert "2026" in got


@pytest.mark.parametrize(
    "present_token",
    ["在職", "現職", "進行中", "現在まで", "재직중", "aktuell", "actuel"],
)
def test_format_date_recognises_native_present_tokens(present_token: str) -> None:
    """Users from any locale can hand-enter "still here" in their own
    language; all map to a valid locale-appropriate output (rather than
    falling through as literal)."""
    # Use en_US as the output locale to get a deterministic "Present" string.
    assert format_date(present_token, "en_US") == "Present"


# ─────────────────────── format_date_range — extra ────────────────────────


def test_range_both_empty_sides_is_empty() -> None:
    assert format_date_range(None, None, "en_US") == ""
    assert format_date_range("", "", "ja_JP") == ""


def test_range_western_locales_use_en_dash() -> None:
    for locale in ["en_US", "en_GB", "de_DE", "fr_FR", "zh_TW"]:
        got = format_date_range("2025-01", "2026-04", locale)
        assert "–" in got, f"{locale} should use en dash"


def test_range_one_side_only_still_renders_both_separators() -> None:
    """Even when one end is empty, we still get a separator — templates
    that write `{{ start | date_range(end) }}` rely on this to detect the
    half-open interval."""
    got = format_date_range("2025-01", "", "en_US")
    assert "2025" in got
    assert "–" in got


# ─────────────────────── localized — extra edge cases ─────────────────────


def test_localized_accepts_none_object() -> None:
    """Template may hand over `None` when a profile field is missing —
    this must not raise AttributeError."""
    assert localized(None, "summary", "ja_JP") is None


def test_localized_non_dict_object_uses_getattr() -> None:
    """Pydantic models that weren't model_dump'd before reaching the
    template still work — we fall through to `getattr(obj, key_<locale>)`."""

    class Prof:
        summary = "default"
        summary_ja_JP = "日本語版"

    assert localized(Prof(), "summary", "ja_JP") == "日本語版"


def test_localized_non_dict_object_missing_attr_returns_none() -> None:
    class Prof:
        summary = "default"

    assert localized(Prof(), "missing", "ja_JP") is None


def test_localized_alias_locale_resolves_before_lookup() -> None:
    """If the caller passes `zh-TW`, we should still find `title_zh_TW`
    override in the dict (resolve_locale normalizes the key first)."""
    d = {"title": "Engineer", "title_zh_TW": "工程師"}
    assert localized(d, "title", "zh-TW") == "工程師"
