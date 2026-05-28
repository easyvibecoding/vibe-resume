"""Render filename suffix consistency across locales (Issue #4)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture
def fake_render(tmp_path, monkeypatch):
    """Render two single-page markdowns at en_US and zh_TW for the same persona."""
    from render import renderer
    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    # Patch _render_md so we don't depend on profile/groups disk state
    def _fake_md(cfg, tailor, locale=None, persona=None):
        locale_key = locale or "en_US"
        return ("# fake\n", {"locale": {"_key": locale_key}, "_tpl_name": "fake.j2",
                              "profile": {}, "groups": []})
    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    # Patch snapshot (imported directly into renderer namespace) so we don't
    # need a real git repo in tmp_path
    monkeypatch.setattr(renderer, "snapshot", lambda cfg, files, msg: None)
    return tmp_path


def test_en_US_filename_includes_locale_suffix(fake_render):
    """en_US render must include locale in filename (was dropped in 0.4.0)."""
    from render.renderer import render_draft
    render_draft({}, fmt="md", locale="en_US", persona="tech_lead")
    files = sorted(fake_render.glob("resume_v*_en_US_tech_lead.md"))
    assert len(files) == 1, f"expected resume_v001_en_US_tech_lead.md; got {list(fake_render.iterdir())}"


def test_locales_other_than_en_US_still_include_suffix(fake_render):
    from render.renderer import render_draft
    render_draft({}, fmt="md", locale="zh_TW", persona="tech_lead")
    files = sorted(fake_render.glob("resume_v*_zh_TW_tech_lead.md"))
    assert len(files) == 1


def test_no_locale_no_persona_still_works(fake_render):
    """Backward compat: locale=None falls back to en_US, no persona → only locale suffix."""
    from render.renderer import render_draft
    render_draft({}, fmt="md")
    files = sorted(fake_render.glob("resume_v*_en_US.md"))
    assert len(files) == 1
