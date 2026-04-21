"""Smoke tests for ``core.company_profiles`` and ``core.levels``.

Verifies schema completeness of every registered profile/level so that new
entries added by /loop iterations cannot silently ship with empty fields.
Also covers the YAML loader's rejection paths (malformed files, unknown
tiers, key/filename mismatch) so a bad profile breaks the build loudly.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from core.company_profiles import (
    COMPANY_PROFILES,
    KNOWN_TIERS,
    STALE_DEFAULT_DAYS,
    TIER_FRONTIER_AI,
    TIER_JP,
    TIER_US_TIER2,
    CompanyProfile,
    ProfileLoadError,
    days_since_verification,
    get_company,
    list_by_tier,
    list_company_keys,
    load_profiles,
    stale_profiles,
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
    # Hallucination-guard metadata — every profile must carry a verifiable date.
    assert p.last_verified_at, f"{key} missing last_verified_at"
    # parseable as ISO date
    assert p.verified_date() is not None
    # verification_sources is optional but must be a tuple (possibly empty)
    assert isinstance(p.verification_sources, tuple)


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
last_verified_at: '2026-04-21'
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


def test_loader_rejects_missing_last_verified_at(tmp_path: Path):
    bad = MINIMAL_VALID_YAML.replace("last_verified_at: '2026-04-21'\n", "")
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="missing required fields"):
        load_profiles(tmp_path)


def test_loader_rejects_malformed_last_verified_at(tmp_path: Path):
    bad = MINIMAL_VALID_YAML.replace(
        "last_verified_at: '2026-04-21'",
        "last_verified_at: 'not-a-date'",
    )
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="not a valid YYYY-MM-DD"):
        load_profiles(tmp_path)


def test_loader_rejects_non_string_last_verified_at(tmp_path: Path):
    bad = MINIMAL_VALID_YAML.replace(
        "last_verified_at: '2026-04-21'",
        "last_verified_at: 20260421",
    )
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="non-empty YYYY-MM-DD"):
        load_profiles(tmp_path)


def test_loader_accepts_verification_sources_optional(tmp_path: Path):
    with_sources = MINIMAL_VALID_YAML + (
        "verification_sources:\n"
        "  - https://example.com/source-1\n"
        "  - https://example.com/source-2\n"
    )
    _write(tmp_path, "fake_co.yaml", with_sources)
    reg = load_profiles(tmp_path)
    assert reg["fake_co"].verification_sources == (
        "https://example.com/source-1",
        "https://example.com/source-2",
    )


def test_loader_rejects_non_list_verification_sources(tmp_path: Path):
    bad = MINIMAL_VALID_YAML + "verification_sources: 'single-string-not-a-list'\n"
    _write(tmp_path, "fake_co.yaml", bad)
    with pytest.raises(ProfileLoadError, match="must be a list"):
        load_profiles(tmp_path)


# -------- staleness helpers --------------------------------------------------


def _profile_with_date(d: str) -> CompanyProfile:
    # Use an actual registered profile as a template, override verification date
    proto = next(iter(COMPANY_PROFILES.values()))
    return CompanyProfile(
        key=proto.key,
        label=proto.label,
        tier=proto.tier,
        locale_hint=proto.locale_hint,
        must_haves=proto.must_haves,
        plus_signals=proto.plus_signals,
        red_flags=proto.red_flags,
        format_rules=proto.format_rules,
        keyword_anchors=proto.keyword_anchors,
        enrich_bias=proto.enrich_bias,
        review_tips=proto.review_tips,
        last_verified_at=d,
    )


def test_days_since_verification_same_day():
    p = _profile_with_date("2026-04-21")
    assert days_since_verification(p, today=date(2026, 4, 21)) == 0


def test_days_since_verification_future_is_negative():
    p = _profile_with_date("2026-05-01")
    # verified "in the future" relative to today — negative
    assert days_since_verification(p, today=date(2026, 4, 21)) == -10


def test_days_since_verification_past():
    p = _profile_with_date("2026-01-21")
    assert days_since_verification(p, today=date(2026, 4, 21)) == 90


def test_stale_profiles_default_threshold_all_fresh():
    # Every currently-registered profile is verified at 2026-04-21, so
    # relative to a date barely past it, none should be stale.
    fresh = date(2026, 4, 22)
    assert stale_profiles(today=fresh) == []


def test_stale_profiles_custom_threshold_detects():
    # Threshold of 0 days means anything older than today is stale.
    old_ref = date(2026, 4, 21) + timedelta(days=1)
    stale = stale_profiles(threshold_days=0, today=old_ref)
    assert len(stale) == len(COMPANY_PROFILES)


def test_stale_profiles_returns_oldest_first():
    fake_registry = {
        "older": _profile_with_date("2025-01-01"),
        "newer": _profile_with_date("2025-06-01"),
        "fresh": _profile_with_date("2026-04-01"),
    }
    # tie-break only needs to work: the "fresh" one should NOT be stale at
    # 180 days; the other two should appear oldest-first.
    stale = stale_profiles(today=date(2026, 4, 21), registry=fake_registry)
    assert len(stale) == 2
    assert stale[0].last_verified_at == "2025-01-01"
    assert stale[1].last_verified_at == "2025-06-01"


def test_stale_default_constant_is_reasonable():
    # Sanity — not zero, not absurdly large
    assert 30 <= STALE_DEFAULT_DAYS <= 365


# -------- enricher prompt injection ------------------------------------------


def _make_demo_group():
    """Copy of the persona-test factory so this file stays self-contained."""
    from datetime import UTC, datetime

    from core.schema import ProjectGroup, Source

    now = datetime(2026, 3, 1, tzinfo=UTC)
    return ProjectGroup(
        name="demo",
        path="/tmp/demo",
        first_activity=now,
        last_activity=now,
        total_sessions=5,
        sources=[Source.CLAUDE_CODE],
        tech_stack=["Python"],
        category_counts={"backend": 5},
        capability_breadth=1,
        activities=[],
    )


def test_build_prompt_injects_company_block_last():
    """Company bias must fire after persona and level so it wins tie-breaks.

    The block ordering is load-bearing: the model re-reads the most-recent
    guidance when emitting YAML, and company is the most specific lens.
    """
    from core.company_profiles import COMPANY_PROFILES
    from core.enricher import _build_prompt
    from render.i18n import get_locale

    c = COMPANY_PROFILES["openai"]
    prompt = _build_prompt(
        _make_demo_group(),
        get_locale("en_US"),
        company=c,
    )
    assert "Target employer — OpenAI" in prompt
    # verified date appears in the header
    assert c.last_verified_at in prompt
    # the block lands after the main template body
    assert prompt.rindex("Target employer") > prompt.index("Project:")


def test_build_prompt_company_block_omitted_when_none():
    from core.enricher import _build_prompt
    from render.i18n import get_locale

    prompt = _build_prompt(_make_demo_group(), get_locale("en_US"))
    assert "Target employer" not in prompt


def test_build_prompt_level_block_contains_lead_signal():
    from core.enricher import _build_prompt
    from core.levels import LEVELS
    from render.i18n import get_locale

    lvl = LEVELS["senior"]
    prompt = _build_prompt(
        _make_demo_group(),
        get_locale("en_US"),
        level=lvl,
    )
    assert f"Career level — {lvl.label}" in prompt
    assert lvl.lead_signal in prompt


def test_build_prompt_block_order_tailor_persona_level_company():
    """Given all four biases, the order from top-to-bottom must be
    tailor → persona → level → company, so the most-specific guidance
    lands nearest the model's YAML emission."""
    from core.company_profiles import COMPANY_PROFILES
    from core.enricher import _build_prompt
    from core.levels import LEVELS
    from core.personas import PERSONAS
    from render.i18n import get_locale

    prompt = _build_prompt(
        _make_demo_group(),
        get_locale("en_US"),
        tailor_keywords=["RAG"],
        persona=PERSONAS["tech_lead"],
        level=LEVELS["senior"],
        company=COMPANY_PROFILES["anthropic"],
    )
    i_tailor = prompt.index("Tailor hint")
    i_persona = prompt.index("Reviewer persona")
    i_level = prompt.index("Career level")
    i_company = prompt.index("Target employer")
    assert i_tailor < i_persona < i_level < i_company


# -------- review_file integration --------------------------------------------


def test_review_file_injects_company_and_level_tips(tmp_path: Path):
    from core.review import review_file

    md = tmp_path / "resume_v001.md"
    md.write_text(
        "# Demo Candidate\n\n"
        "## Experience\n\n"
        "- Built a small demo project with minimal metrics.\n",
        encoding="utf-8",
    )
    report = review_file(md, company="stripe", level="senior")
    text = report.as_markdown()
    assert "Target employer — Stripe" in text
    assert "profile last verified" in text
    assert "Career level — Senior / IC5" in text
    # Unknown keys should simply be ignored (no crash, no fabricated section).
    report2 = review_file(md, company="does_not_exist", level="nope")
    text2 = report2.as_markdown()
    assert "Target employer" not in text2
    assert "Career level" not in text2


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
