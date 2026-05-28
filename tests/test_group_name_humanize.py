"""#36.3: ID-only CLI group names get humanized, not leaked as titles."""
from vibe_resume.core.aggregator import _humanize_group_name


def test_hex_id_name_humanized():
    out = _humanize_group_name("gemini:a1b2c3d4e5", None)
    assert out != "gemini:a1b2c3d4e5"
    assert "gemini" in out


def test_path_basename_preferred():
    assert _humanize_group_name("gemini:a1b2c3", "/Users/x/my-project") == "my-project"


def test_normal_name_untouched():
    assert _humanize_group_name("rag-platform", None) == "rag-platform"
