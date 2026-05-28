"""templates_dir resilience — stale/invalid override falls back to bundled (#30)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def _patch_render_md_deps(monkeypatch, tmp_path):
    """Patch all I/O dependencies of _render_md so it runs without real disk data."""
    from vibe_resume.render import renderer

    fake_profile = MagicMock()
    fake_profile.model_dump.return_value = {"name": "Test User", "summary": "A dev"}
    fake_profile.model_extra = {}

    monkeypatch.setattr(renderer, "load_profile", lambda path: fake_profile)
    monkeypatch.setattr(renderer, "load_groups", lambda persona=None, locale=None: [])
    monkeypatch.setattr(renderer, "load_observed_summary", lambda: {})
    monkeypatch.setattr(renderer, "load_window_stats", lambda: {})
    monkeypatch.setattr(renderer, "user_root", lambda: tmp_path)
    monkeypatch.setattr(renderer, "ROOT", tmp_path)


def test_stale_templates_dir_falls_back_to_bundled(tmp_path, monkeypatch, capsys):
    """A config templates_dir that doesn't exist must NOT crash render —
    fall back to the package-bundled templates with a warning."""
    from vibe_resume.render import renderer

    _patch_render_md_deps(monkeypatch, tmp_path)

    cfg = {"render": {"templates_dir": "./render/templates"}}  # stale 0.5.x path
    md, ctx = renderer._render_md(cfg, tailor=None, locale="en_US", persona=None)
    assert md  # rendered something
    # Rich may wrap long lines — normalize whitespace before asserting
    out = " ".join(capsys.readouterr().out.split())
    assert "using bundled templates" in out


def test_unset_templates_dir_uses_bundled(tmp_path, monkeypatch):
    from vibe_resume.render import renderer

    _patch_render_md_deps(monkeypatch, tmp_path)

    cfg = {"render": {}}
    md, ctx = renderer._render_md(cfg, tailor=None, locale="en_US", persona=None)
    assert md


def test_config_example_has_no_stale_templates_dir():
    """Guard: config.example.yaml must not ship a templates_dir pointing at the
    pre-0.6.0 ./render/templates path (#30)."""
    import yaml

    repo = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((repo / "config.example.yaml").read_text())
    td = cfg.get("render", {}).get("templates_dir")
    assert td in (None, ""), f"config.example.yaml still ships templates_dir={td!r}"
