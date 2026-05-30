"""#65 per-locale template capability disclosure."""
from vibe_resume.render.template_caps import (
    capabilities,
    capability_matrix,
    renders_metrics,
    template_for,
)


def test_en_us_renders_metrics_but_zh_tw_does_not():
    # en_US template now renders g.metrics (#65 fix); zh_TW does not — that gap
    # is exactly what the capability matrix discloses.
    assert renders_metrics("en_US") is True
    assert renders_metrics("zh_TW") is False
    assert "metrics" in capabilities("en_US")
    assert "metrics" not in capabilities("zh_TW")


def test_template_for_prefers_specific_then_base():
    assert template_for("zh_TW").name == "resume.zh_TW.md.j2"
    assert template_for("en_US").name == "resume.en_US.md.j2"
    # an unregistered locale falls back to the base template
    assert template_for("xx_XX").name == "resume.md.j2"


def test_capability_matrix_discloses_the_cliff():
    m = capability_matrix()
    assert "en_US" in m and "zh_TW" in m
    assert any("metrics" in c for c in m.values())       # some render metrics
    assert any("metrics" not in c for c in m.values())   # some don't — the disclosed cliff
