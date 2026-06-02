"""Tests for the bundled AI-proficiency market rubric loader (#47)."""
from dataclasses import replace
from datetime import date

from vibe_resume.core import rubric as R


def test_bundled_rubric_loads():
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    assert rb.bullet_formula
    assert "MCP" in rb.agentic_keywords
    assert any(y.kind == "stale_stack" for y in rb.yellow_flags)
    assert rb.metric_hints.get("review")


def test_user_cache_override_wins(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    (cache / "market_rubric.yaml").write_text(
        'version: 9\nrefreshed_at: "2099-01-01"\nbullet_formula: "OVERRIDE"\n'
        "agentic_keywords: [ZZZ]\n", encoding="utf-8")
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    rb = R.load_rubric()
    assert rb.bullet_formula == "OVERRIDE"
    assert rb.agentic_keywords == ["ZZZ"]
    R.load_rubric.cache_clear()


def test_malformed_override_falls_back(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    (cache / "market_rubric.yaml").write_text("{ not: valid: yaml ::", encoding="utf-8")
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    rb = R.load_rubric()
    assert "MCP" in rb.agentic_keywords  # bundled baseline used
    R.load_rubric.cache_clear()


def test_is_stale_boundary():
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    assert rb.is_stale(as_of=date(2099, 1, 1)) is True
    assert rb.is_stale(as_of=date(2026, 5, 30)) is False


def test_gate_terms_full_locale_resolves_to_base_family():
    """Regression for #82: full locale codes (zh_TW/ja_JP/de_DE) must resolve to
    the base-family key in human_gate_verbs_by_locale, not miss it."""
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    # Real verbs that live in market_rubric.yaml under each family.
    assert "審查" in R.gate_terms(rb, "zh_TW")
    assert "検証" in R.gate_terms(rb, "ja_JP")
    assert "geprüft" in R.gate_terms(rb, "de_DE")


def test_gate_terms_exact_base_key_still_works():
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    assert "審查" in R.gate_terms(rb, "zh")


def test_gate_terms_unknown_lang_returns_english_base_only():
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    terms = R.gate_terms(rb, "xx_YY")
    assert terms == [t.lower() for t in rb.human_gate_verbs]


def test_gate_terms_no_double_add_when_base_and_full_present():
    """If both 'zh' and 'zh_TW' keys exist, prefer exact then break — no dupes."""
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    custom = dict(rb.human_gate_verbs_by_locale)
    custom["zh_TW"] = ["臺灣專用"]
    rb2 = replace(rb, human_gate_verbs_by_locale=custom)
    terms = R.gate_terms(rb2, "zh_TW")
    assert "臺灣專用" in terms
    assert "審查" not in terms  # exact key wins, family not also added
