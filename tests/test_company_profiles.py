"""Smoke tests for ``core.company_profiles`` and ``core.levels``.

Verifies schema completeness of every registered profile/level so that new
entries added by /loop iterations cannot silently ship with empty fields.
Also covers the YAML loader's rejection paths (malformed files, unknown
tiers, key/filename mismatch) so a bad profile breaks the build loudly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.company_profiles import (
    COMPANY_PROFILES,
    KNOWN_TIERS,
    TIER_FRONTIER_AI,
    TIER_JP,
    TIER_US_TIER2,
    CompanyProfile,
    ProfileLoadError,
    get_company,
    list_by_tier,
    list_company_keys,
    load_profiles,
)
from core.levels import (
    LEVELS,
    LevelArchetype,
    get_level,
    infer_level_from_yoe,
    list_level_keys,
)

# -------- company_profiles ---------------------------------------------------


def test_registry_is_not_empty():
    assert len(COMPANY_PROFILES) >= 4, "iter 1 seeds at least 4 profiles"


@pytest.mark.parametrize("key", list(COMPANY_PROFILES.keys()))
def test_every_profile_has_full_schema(key: str):
    p = COMPANY_PROFILES[key]
    assert isinstance(p, CompanyProfile)
    assert p.key == key
    assert p.label
    assert p.tier
    assert p.locale_hint
    assert p.must_haves, f"{key} must_haves empty"
    assert p.plus_signals, f"{key} plus_signals empty"
    assert p.red_flags, f"{key} red_flags empty"
    assert p.format_rules, f"{key} format_rules empty"
    assert p.keyword_anchors, f"{key} keyword_anchors empty"
    assert len(p.enrich_bias) > 60
    assert len(p.review_tips) > 40


def test_get_company_lookup():
    assert get_company("openai") is COMPANY_PROFILES["openai"]
    assert get_company("unknown_xyz") is None
    assert get_company(None) is None


def test_list_by_tier_groups_correctly():
    frontier = {p.key for p in list_by_tier(TIER_FRONTIER_AI)}
    assert {"openai", "anthropic"}.issubset(frontier)
    assert "stripe" in {p.key for p in list_by_tier(TIER_US_TIER2)}
    assert "rakuten" in {p.key for p in list_by_tier(TIER_JP)}


def test_no_duplicate_labels():
    labels = [p.label for p in COMPANY_PROFILES.values()]
    assert len(labels) == len(set(labels))


def test_list_company_keys_matches_registry():
    assert set(list_company_keys()) == set(COMPANY_PROFILES.keys())


def test_every_tier_is_known():
    for p in COMPANY_PROFILES.values():
        assert p.tier in KNOWN_TIERS


# -------- YAML loader rejections --------------------------------------------


MINIMAL_VALID_YAML = """\
key: fake_co
label: Fake Co
tier: frontier_ai
locale_hint: en_US
must_haves:
  - must have one
plus_signals:
  - plus one
red_flags:
  - flag one
format_rules:
  - rule one
keyword_anchors:
  - kw
enrich_bias: a bias string that is long enough to look plausible
review_tips: tips string also long enough to look plausible
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_loader_happy_path(tmp_path: Path):
    _write(tmp_path, "fake_co.yaml", MINIMAL_VALID_YAML)
    reg = load_profiles(tmp_path)
    assert set(reg.keys()) == {"fake_co"}
    assert reg["fake_co"].must_haves == ("must have one",)


def test_loader_rejects_missing_field(tmp_path: Path):
    broken = MINIMAL_VALID_YAML.replace("label: Fake Co\n", "")
    _write(tmp_path, "fake_co.yaml", broken)
    with pytest.raises(ProfileLoadError, match="missing required fields"):
        load_profiles(tmp_path)


def test_loader_rejects_unknown_field(tmp_path: Path):
    bad = MINIMAL_VALID_YAML + "unknown_field: 42\n"
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="unknown fields"):
        load_profiles(tmp_path)


def test_loader_rejects_unknown_tier(tmp_path: Path):
    bad = MINIMAL_VALID_YAML.replace("tier: frontier_ai", "tier: made_up_tier")
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="tier"):
        load_profiles(tmp_path)


def test_loader_rejects_key_filename_mismatch(tmp_path: Path):
    _write(tmp_path, "other_name.yaml", MINIMAL_VALID_YAML)
    with pytest.raises(ProfileLoadError, match="does not match filename"):
        load_profiles(tmp_path)


def test_loader_rejects_empty_tuple_field(tmp_path: Path):
    bad = MINIMAL_VALID_YAML.replace("must_haves:\n  - must have one", "must_haves: []")
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="must be a non-empty list"):
        load_profiles(tmp_path)


def test_loader_rejects_non_mapping_yaml(tmp_path: Path):
    _write(tmp_path, "fake_co.yaml", "- just a list\n")
    with pytest.raises(ProfileLoadError, match="mapping"):
        load_profiles(tmp_path)


def test_loader_rejects_malformed_yaml(tmp_path: Path):
    _write(tmp_path, "fake_co.yaml", "key: openai\n  bad: indent\n garbage:[")
    with pytest.raises(ProfileLoadError, match="YAML parse error"):
        load_profiles(tmp_path)


def test_loader_raises_if_directory_missing(tmp_path: Path):
    with pytest.raises(ProfileLoadError, match="not found"):
        load_profiles(tmp_path / "does_not_exist")


def test_loader_detects_duplicate_keys(tmp_path: Path):
    _write(tmp_path, "fake_co.yaml", MINIMAL_VALID_YAML)
    # second file has matching key but different filename stem — trips the
    # filename-mismatch check before reaching the duplicate check
    dup = MINIMAL_VALID_YAML.replace("fake_co", "fake_co")
    _write(tmp_path, "fake_co_2.yaml", dup)
    with pytest.raises(ProfileLoadError):
        load_profiles(tmp_path)


# -------- levels -------------------------------------------------------------


def test_levels_registered():
    expected = {"new_grad", "junior", "mid", "senior", "staff_plus", "research_scientist"}
    assert expected == set(LEVELS.keys())


@pytest.mark.parametrize("key", list(LEVELS.keys()))
def test_every_level_has_full_schema(key: str):
    lvl = LEVELS[key]
    assert isinstance(lvl, LevelArchetype)
    assert lvl.key == key
    assert lvl.label
    assert 0 <= lvl.yoe_range[0] <= lvl.yoe_range[1]
    assert lvl.page_budget in (1, 2)
    assert lvl.lead_signal
    assert lvl.bullet_density
    assert len(lvl.enrich_bias) > 60
    assert len(lvl.review_tips) > 40


@pytest.mark.parametrize(
    "yoe,expected",
    [
        (0, "new_grad"),
        (1, "junior"),
        (3, "mid"),
        (6, "senior"),
        (10, "staff_plus"),
        (25, "staff_plus"),
    ],
)
def test_infer_level_from_yoe(yoe: float, expected: str):
    assert infer_level_from_yoe(yoe).key == expected


def test_infer_never_returns_research_scientist():
    for yoe in (0, 2, 5, 8, 15, 40):
        assert infer_level_from_yoe(yoe).key != "research_scientist"


def test_get_level_lookup():
    assert get_level("mid") is LEVELS["mid"]
    assert get_level("unknown_xyz") is None
    assert get_level(None) is None


def test_list_level_keys_matches_registry():
    assert set(list_level_keys()) == set(LEVELS.keys())
