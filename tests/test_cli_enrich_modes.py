"""Tests for enrich_groups mode dispatch (prompt / subprocess / rule-based)."""
from __future__ import annotations

import orjson
import pytest


@pytest.fixture
def seeded_cache(tmp_path, monkeypatch):
    """Seed raw aggregator output so enrich has something to chew on."""
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    raw = [{"name": "proj-foo", "path": None,
            "first_activity": "2026-01-01T00:00:00+00:00",
            "last_activity": "2026-02-01T00:00:00+00:00",
            "sources": ["claude-code"], "total_sessions": 5,
            "tech_stack": ["FastAPI"], "category_counts": {"backend": 5},
            "capability_breadth": 1, "activities": []}]
    aggregator.GROUPS_PATH.write_bytes(orjson.dumps(raw))
    return tmp_path


def test_default_mode_is_prompt_and_writes_manifest(seeded_cache, monkeypatch, capsys):
    """Calling enrich without --mode/--ingest defaults to emit a manifest."""
    from core import enricher
    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", seeded_cache / "enrich_jobs")

    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, locale="en_US")

    manifest = seeded_cache / "enrich_jobs" / "default" / "en_US" / "manifest.json"
    assert manifest.exists()


def test_subprocess_mode_emits_red_quota_warning(seeded_cache, monkeypatch, capsys):
    from core import enricher
    monkeypatch.setattr(enricher, "_call_claude", lambda *a, **kw: None)
    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, locale="en_US", mode="subprocess")
    import re
    out = re.sub(r"\s+", " ", capsys.readouterr().out)
    assert "Agent SDK" in out and "subprocess" in out


def test_cli_enrich_help_lists_mode_and_ingest():
    """Smoke: --mode and --ingest flags are wired up."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "enrich", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "--mode" in r.stdout
    assert "--ingest" in r.stdout
