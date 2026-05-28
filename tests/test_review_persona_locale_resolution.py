"""review --persona X --locale Y should match the correct résumé file (Issue #2)."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def hist_with_persona_files(tmp_path):
    """Seed several rendered résumés mimicking a real persona × locale batch."""
    (tmp_path / "resume_v001_en_US.md").write_text("# v1 default\n")
    (tmp_path / "resume_v002_zh_TW.md").write_text("# v2 zh\n")
    (tmp_path / "resume_v003_zh_TW_tech_lead.md").write_text("# v3 zh tl\n")
    (tmp_path / "resume_v004_zh_TW_hr.md").write_text("# v4 zh hr\n")
    (tmp_path / "resume_v005_en_US_executive.md").write_text("# v5 en exec\n")
    return tmp_path


def test_resolve_persona_locale_picks_correct_file(hist_with_persona_files):
    from vibe_resume.core.review import resolve_resume_path
    p = resolve_resume_path(hist_with_persona_files, persona="tech_lead", locale="zh_TW")
    assert p.name == "resume_v003_zh_TW_tech_lead.md"


def test_resolve_persona_locale_picks_latest_when_multiple_match(hist_with_persona_files):
    """If multiple versions match (persona, locale), pick the highest version."""
    (hist_with_persona_files / "resume_v007_zh_TW_tech_lead.md").write_text("# v7\n")
    from vibe_resume.core.review import resolve_resume_path
    p = resolve_resume_path(hist_with_persona_files, persona="tech_lead", locale="zh_TW")
    assert p.name == "resume_v007_zh_TW_tech_lead.md"


def test_resolve_persona_locale_errors_when_no_match(hist_with_persona_files):
    from vibe_resume.core.review import resolve_resume_path
    with pytest.raises(FileNotFoundError, match="academic"):
        resolve_resume_path(hist_with_persona_files, persona="academic", locale="zh_TW")


def test_resolve_locale_only_picks_latest_of_that_locale(hist_with_persona_files):
    from vibe_resume.core.review import resolve_resume_path
    p = resolve_resume_path(hist_with_persona_files, locale="zh_TW")
    # latest zh_TW file (any persona)
    assert "zh_TW" in p.name
    # Should be v004 (latest zh_TW) since v003 is older
    assert p.name == "resume_v004_zh_TW_hr.md"
