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


def test_personas_compare_requires_locale():
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "personas-compare"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode != 0
    combined = (r.stderr + r.stdout).lower()
    assert "locale" in combined


# ---------------------------------------------------------------------------
# Fix #7 — --tailor-keywords / --tailor-keywords-cap / --tailor-keywords-strict
# ---------------------------------------------------------------------------


def test_cli_enrich_help_lists_tailor_overrides():
    """All three --tailor-keywords* flags must appear in --help output."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "enrich", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "--tailor-keywords" in r.stdout
    assert "--tailor-keywords-cap" in r.stdout
    assert "--tailor-keywords-strict" in r.stdout


def test_cli_enrich_help_lists_clean_and_status():
    """--clean, --status and --all-ready flags must appear in --help output."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "enrich", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "--clean" in r.stdout
    assert "--status" in r.stdout
    assert "--all-ready" in r.stdout


def test_tailor_keywords_strict_skips_auto_extraction(seeded_cache, monkeypatch):
    """--tailor-keywords-strict with no --tailor should yield None tailor_keywords."""
    from core import enricher

    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", seeded_cache / "enrich_jobs")

    # strict without any --tailor — override_kw empty, auto_kw skipped → None
    enricher.enrich_groups(
        cfg={}, cache_dir=seeded_cache, locale="en_US",
        tailor_keywords_override=None,
        tailor_keywords_strict=True,
    )

    manifest_path = seeded_cache / "enrich_jobs" / "default" / "en_US" / "manifest.json"
    import json
    m = json.loads(manifest_path.read_text())
    assert m["tailor_keywords"] is None


def test_tailor_keywords_override_injected_without_tailor_file(seeded_cache, monkeypatch):
    """Override keywords alone (no --tailor file) should appear in tailor_keywords."""
    from core import enricher

    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", seeded_cache / "enrich_jobs")

    enricher.enrich_groups(
        cfg={}, cache_dir=seeded_cache, locale="en_US",
        tailor_keywords_override="LangGraph,MCP",
        tailor_keywords_cap=12,
    )

    manifest_path = seeded_cache / "enrich_jobs" / "default" / "en_US" / "manifest.json"
    import json
    m = json.loads(manifest_path.read_text())
    kw = m["tailor_keywords"] or []
    assert "LangGraph" in kw
    assert "MCP" in kw


# ---------------------------------------------------------------------------
# Fix #12 — --status command + --ingest --all-ready
# ---------------------------------------------------------------------------


def test_status_shows_no_jobs_when_empty(seeded_cache, monkeypatch, capsys):
    """enrich_groups(status=True) with no jobs dir prints 'no jobs'."""
    from core import enricher

    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", seeded_cache / "enrich_jobs_empty")

    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, status=True)
    out = capsys.readouterr().out
    assert "no jobs" in out


def test_status_shows_progress_after_emit(seeded_cache, monkeypatch, capsys):
    """After emit + writing the yaml, --status should report 1/1 ready."""
    import json

    from core import enricher

    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", seeded_cache / "enrich_jobs")

    # Emit prompts
    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, locale="en_US")
    _ = capsys.readouterr()  # flush emit output

    # Write the yaml so the batch is "ready"
    jobs_dir = seeded_cache / "enrich_jobs" / "default" / "en_US"
    m = json.loads((jobs_dir / "manifest.json").read_text())
    (jobs_dir / m["groups"][0]["output_path"]).write_text("summary: ok\n")

    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, status=True)
    out = capsys.readouterr().out
    assert "1/1" in out
    assert "ready" in out


def test_all_ready_ingests_completed_batch(seeded_cache, monkeypatch, capsys):
    """--ingest --all-ready triggers _do_ingest for every ready batch."""
    import json

    from core import enricher

    enrich_jobs_dir = seeded_cache / "enrich_jobs"
    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", enrich_jobs_dir)

    # Emit
    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, locale="en_US")
    _ = capsys.readouterr()

    # Mark done by writing yaml
    jobs_dir = enrich_jobs_dir / "default" / "en_US"
    m = json.loads((jobs_dir / "manifest.json").read_text())
    yaml_body = "summary: ready\nrole_label: Backend\nachievements: []\ntech_stack: []\n"
    (jobs_dir / m["groups"][0]["output_path"]).write_text(yaml_body)

    # Patch _load_raw_groups to return the seeded group
    from tests.test_enrich_jobs import _fake_group
    monkeypatch.setattr("core.enrich_jobs._load_raw_groups", lambda: [_fake_group("proj-foo")])

    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, ingest=True, all_ready=True)
    out = capsys.readouterr().out
    assert "ingested" in out
