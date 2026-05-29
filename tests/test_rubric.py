"""Tests for the bundled AI-proficiency market rubric loader (#47)."""
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
