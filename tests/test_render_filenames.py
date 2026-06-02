"""Render filename suffix consistency across locales (Issue #4)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture
def fake_render(tmp_path, monkeypatch):
    """Render two single-page markdowns at en_US and zh_TW for the same persona."""
    from vibe_resume.render import renderer
    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    # Patch _render_md so we don't depend on profile/groups disk state
    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
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
    from vibe_resume.render.renderer import render_draft
    render_draft({}, fmt="md", locale="en_US", persona="tech_lead")
    files = sorted(fake_render.glob("resume_v*_en_US_tech_lead.md"))
    assert len(files) == 1, f"expected resume_v001_en_US_tech_lead.md; got {list(fake_render.iterdir())}"


def test_locales_other_than_en_US_still_include_suffix(fake_render):
    from vibe_resume.render.renderer import render_draft
    render_draft({}, fmt="md", locale="zh_TW", persona="tech_lead")
    files = sorted(fake_render.glob("resume_v*_zh_TW_tech_lead.md"))
    assert len(files) == 1


def test_no_locale_no_persona_still_works(fake_render):
    """Backward compat: locale=None falls back to en_US, no persona → only locale suffix."""
    from vibe_resume.render.renderer import render_draft
    render_draft({}, fmt="md")
    files = sorted(fake_render.glob("resume_v*_en_US.md"))
    assert len(files) == 1


def test_render_all_locales_with_persona_list_expands_matrix(tmp_path, monkeypatch):
    """--all-locales × --persona X,Y → renders one file per (locale, persona)."""
    from vibe_resume.render import renderer

    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)

    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        return (
            "# fake\n",
            {
                "locale": {"_key": locale or "en_US"},
                "_tpl_name": "fake.j2",
                "profile": {},
                "groups": [],
            },
        )

    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    monkeypatch.setattr(renderer, "snapshot", lambda cfg, files, msg: None)

    from click.testing import CliRunner

    from vibe_resume.cli import cli

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["render", "--all-locales", "--format", "md", "--persona", "tech_lead,hr"],
        obj={"config": {}},
    )
    assert result.exit_code == 0, result.output

    files = sorted(tmp_path.glob("resume_v*.md"))
    names = [f.name for f in files]
    # Verify both personas appear
    assert any("tech_lead" in n for n in names), f"tech_lead missing from {names}"
    assert any("hr" in n for n in names), f"hr missing from {names}"
    # Verify multiple locales appear
    assert any("zh_TW" in n for n in names), f"zh_TW missing from {names}"
    assert any("ja_JP" in n for n in names), f"ja_JP missing from {names}"
    # 10 locales × 2 personas = 20 files
    from vibe_resume.render.i18n import LOCALES
    assert len(files) == len(LOCALES) * 2, f"expected {len(LOCALES) * 2}, got {len(files)}: {names}"


def test_render_warns_on_empty_profile_summary(tmp_path, monkeypatch, capsys):
    from vibe_resume.render import renderer
    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        return ("# fake\n", {
            "locale": {"_key": "en_US"}, "_tpl_name": "fake.j2",
            "profile": {"summary": ""},
            "groups": [],
        })
    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)
    renderer.render_draft({}, fmt="md", locale="en_US")
    assert "summary is empty" in capsys.readouterr().out


def test_render_no_warning_when_summary_present(tmp_path, monkeypatch, capsys):
    from vibe_resume.render import renderer
    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        return ("# fake\n", {
            "locale": {"_key": "en_US"}, "_tpl_name": "fake.j2",
            "profile": {"summary": "Senior FS engineer"},
            "groups": [],
        })
    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)
    renderer.render_draft({}, fmt="md", locale="en_US")
    assert "summary is empty" not in capsys.readouterr().out


def test_default_template_dir_is_package_relative(monkeypatch, tmp_path):
    """Default templates must resolve inside the package, not the user CWD (#27)."""
    monkeypatch.delenv("VIBE_RESUME_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD with no render/templates
    from pathlib import Path as _P

    from vibe_resume.render import renderer
    bundled = _P(renderer.__file__).parent / "templates"
    assert bundled.exists() and (bundled / "resume.en_US.md.j2").exists()


def test_render_draft_multi_format_single_version(tmp_path, monkeypatch):
    """fmt='md,docx' must produce ONE version with both outputs, not two versions (#31)."""
    from vibe_resume.render import renderer

    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)

    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        return ("# fake\n", {
            "locale": {"_key": "en_US"},
            "_tpl_name": "f.j2",
            "profile": {"summary": "x"},
            "groups": [],
        })

    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    # Stubs must touch the output file so globs can find them
    monkeypatch.setattr(renderer, "_render_docx", lambda md, ctx, path: path.touch())
    monkeypatch.setattr(renderer, "_render_pdf", lambda md_path, out_path: out_path.touch() or True)

    renderer.render_draft({}, fmt="md,docx", locale="en_US")

    md_files = list(tmp_path.glob("resume_v*.md"))
    docx_files = list(tmp_path.glob("resume_v*.docx"))
    # Both formats must land under the same version number
    assert len(md_files) == 1, f"expected 1 md file, got {md_files}"
    assert len(docx_files) == 1, f"expected 1 docx file, got {docx_files}"
    assert md_files[0].stem.split("_")[:2] == docx_files[0].stem.split("_")[:2], (
        "md and docx must share the same version prefix"
    )


def test_render_draft_all_string_still_works(tmp_path, monkeypatch):
    """fmt='all' (legacy string) must still produce md+docx+pdf on ONE version (#31)."""
    from vibe_resume.render import renderer

    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)

    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        return ("# fake\n", {
            "locale": {"_key": "en_US"},
            "_tpl_name": "f.j2",
            "profile": {"summary": "x"},
            "groups": [],
        })

    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    monkeypatch.setattr(renderer, "_render_docx", lambda md, ctx, path: path.touch())
    monkeypatch.setattr(renderer, "_render_pdf", lambda md_path, out_path: out_path.touch() or True)

    renderer.render_draft({}, fmt="all", locale="en_US")

    md_files = list(tmp_path.glob("resume_v*.md"))
    docx_files = list(tmp_path.glob("resume_v*.docx"))
    pdf_files = list(tmp_path.glob("resume_v*.pdf"))
    assert len(md_files) == 1
    assert len(docx_files) == 1
    assert len(pdf_files) == 1


def test_top_n_threaded_into_context(tmp_path, monkeypatch):
    from vibe_resume.render import renderer
    captured = {}
    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)

    def spy(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        captured["top_n"] = top_n
        return ("# x\n", {"locale": {"_key": "en_US"}, "_tpl_name": "f.j2",
                           "profile": {"summary": "s"}, "groups": [], "top_n": top_n or 6})

    monkeypatch.setattr(renderer, "_render_md", spy)
    renderer.render_draft({}, fmt="md", locale="en_US", top_n=12)
    assert captured["top_n"] == 12


def test_composite_rank_prefers_deep_over_broad_shallow():
    from datetime import UTC, datetime

    from vibe_resume.core.schema import ProjectGroup, Source
    from vibe_resume.render.renderer import _rank_score

    def g(name, sessions, breadth, achievements):
        return ProjectGroup(
            name=name, path=None,
            first_activity=datetime(2026, 1, 1, tzinfo=UTC),
            last_activity=datetime(2026, 2, 1, tzinfo=UTC),
            sources=[Source.CLAUDE_CODE], total_sessions=sessions,
            tech_stack=["python"], category_counts={"backend": sessions},
            capability_breadth=breadth,
            achievements=achievements,
        )

    deep = g("deep", 90, 1, ["a", "b", "c", "d"])   # focused, many sessions, rich bullets
    broad = g("broad", 10, 5, ["a"])                  # broad but shallow

    assert _rank_score(deep) > _rank_score(broad)


def test_variants_emit_ats_and_detailed_from_same_cache(tmp_path, monkeypatch):
    """#55: --variants emits _ats + _detailed, same enriched cache, just selection."""
    from click.testing import CliRunner

    from vibe_resume.cli import cli
    from vibe_resume.render import renderer

    captured = []

    def _fake_md(cfg, tailor, locale=None, persona=None, top_n=None, max_pages=None, **kwargs):
        captured.append({"top_n": top_n, "max_pages": max_pages})
        return ("# x\n", {"locale": {"_key": locale or "en_US"}, "_tpl_name": "f.j2",
                          "profile": {"summary": "s"}, "groups": []})

    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    monkeypatch.setattr(renderer, "_render_md", _fake_md)
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)

    r = CliRunner().invoke(cli, ["render", "--variants", "--locale", "en_US"], obj={"config": {}})
    assert r.exit_code == 0, r.output
    names = sorted(p.name for p in tmp_path.glob("*.md"))
    assert any(n.endswith("_en_US_ats.md") for n in names), names
    assert any(n.endswith("_en_US_detailed.md") for n in names), names
    # ATS variant carries a page budget; detailed does not — same cache, different length
    assert {"top_n": 4, "max_pages": 2.0} in captured
    assert any(c["max_pages"] is None and c["top_n"] == 14 for c in captured)


def test_render_draft_returns_dropped_pdf(tmp_path, monkeypatch):
    """#66: render_draft reports a dropped requested format."""
    from vibe_resume.render import renderer
    monkeypatch.setattr(renderer, "_history_path", lambda cfg: tmp_path)
    monkeypatch.setattr(renderer, "_render_md", lambda *a, **k: (
        "# x\n", {"locale": {"_key": "en_US"}, "_tpl_name": "f.j2",
                  "profile": {"summary": "s"}, "groups": []}))
    monkeypatch.setattr(renderer, "snapshot", lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_render_pdf", lambda *a, **k: False)
    dropped = renderer.render_draft({}, fmt="pdf", locale="en_US")
    assert dropped == ["pdf"]


def test_render_cli_exits_nonzero_on_dropped_format(monkeypatch):
    """#66: CI/agent gating — dropped format → non-zero (unless --allow-partial)."""
    from click.testing import CliRunner

    import vibe_resume.core.runner as runner
    from vibe_resume.cli import cli
    monkeypatch.setattr(runner, "run_render", lambda *a, **k: ["pdf"])
    r = CliRunner().invoke(cli, ["render", "-f", "pdf", "--locale", "en_US"], obj={"config": {}})
    assert r.exit_code != 0
    assert "dropped" in r.output.lower()
    r2 = CliRunner().invoke(cli, ["render", "-f", "pdf", "--locale", "en_US", "--allow-partial"],
                            obj={"config": {}})
    assert r2.exit_code == 0
