"""Tests for the opt-in research/market-refresh pass (#46)."""
from datetime import date
from pathlib import Path

import pytest

from vibe_resume.core import research as RS
from vibe_resume.core import rubric as R

_VALID = '''
version: 2
refreshed_at: "2026-05-29"
bullet_formula: "verb + tool + scale + delta + gate"
agentic_keywords: [MCP, subagent]
sources:
  - title: "DORA 2025"
    url: "https://dora.dev/research/2025/"
yellow_flag_patterns:
  - kind: stale_stack
    pattern: "(?i)\\\\blangchain\\\\b"
    why: "stale"
'''

_NO_SOURCES = 'version: 2\nrefreshed_at: "2026-05-29"\nagentic_keywords: [MCP]\nsources: []\n'

_BAD_REGEX = '''
refreshed_at: "2026-05-29"
agentic_keywords: [MCP]
sources:
  - title: "x"
    url: "https://x"
yellow_flag_patterns:
  - kind: junior_volume
    pattern: "(?i)\\\\b(unclosed"
    why: "broken regex"
'''


def test_emit_prompt_has_fanout_and_source_rule(tmp_path):
    p = RS.emit_research_prompt(tmp_path, today="2026-05-29")
    body = p.read_text()
    assert "research.result.yaml" in body
    assert "senior" in body.lower() and "ats" in body.lower()
    assert "source" in body.lower()  # every claim needs a source
    assert "2026-05-29" in body


def test_ingest_rejects_no_sources(tmp_path, monkeypatch):
    res = tmp_path / "research.result.yaml"
    res.write_text(_NO_SOURCES, encoding="utf-8")
    monkeypatch.setattr(RS, "_user_root", lambda: tmp_path)
    with pytest.raises(RS.ResearchValidationError):
        RS.ingest_research(res)


def test_ingest_valid_installs_override(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    res = tmp_path / "research.result.yaml"
    res.write_text(_VALID, encoding="utf-8")
    monkeypatch.setattr(RS, "_user_root", lambda: tmp_path)
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    installed, warnings = RS.ingest_research(res)
    assert (tmp_path / "data" / "cache" / "market_rubric.yaml").exists()
    rb = R.load_rubric()
    assert rb.bullet_formula == "verb + tool + scale + delta + gate"
    assert rb.version == 2
    R.load_rubric.cache_clear()


def test_ingest_drops_bad_regex_with_warning(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    res = tmp_path / "research.result.yaml"
    res.write_text(_BAD_REGEX, encoding="utf-8")
    monkeypatch.setattr(RS, "_user_root", lambda: tmp_path)
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    installed, warnings = RS.ingest_research(res)
    assert any("regex" in w.lower() for w in warnings)
    rb = R.load_rubric()
    assert rb.yellow_flags == ()  # the only (bad) flag was dropped
    R.load_rubric.cache_clear()


def test_staleness_note():
    R.load_rubric.cache_clear()
    rb_fresh = R.load_rubric()  # bundled 2026-05-29
    assert RS.staleness_note(rb_fresh, as_of=date(2026, 5, 30)) is None
    assert RS.staleness_note(rb_fresh, as_of=date(2099, 1, 1)) is not None


def test_cli_research_emit(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from vibe_resume.cli import cli
    monkeypatch.setattr("vibe_resume.cli.ROOT", tmp_path)
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("config.yaml").write_text("scan:\n  roots: []\n", encoding="utf-8")
        r = runner.invoke(cli, ["research"])
        assert r.exit_code == 0, r.output
        assert "research.prompt.md" in r.output
