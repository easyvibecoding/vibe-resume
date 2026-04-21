"""Company-specific résumé-review profiles — distilled from public hiring signals.

Each ``CompanyProfile`` captures what one named employer's reviewers
consistently weight differently from the generic 8-point rubric in
``core/review.py``. The three dimensions compose:

    enrich bias / review bias  =  persona  ×  level  ×  company

- ``core/personas.py``       → reviewer role (tech_lead / hr / exec / …)
- ``core/levels.py``         → seniority bracket (new_grad … staff_plus)
- ``core/company_profiles.py`` (this file) → target employer

Profile *data* lives one-file-per-company under ``core/profiles/*.yaml``
so that /loop iterations (or external contributors) can add a new
employer by dropping a single YAML file — no Python edit required.

Sources: first-party careers pages, engineering blogs, and published
interview guides collected under the "resume_review_templates_progress"
memory. Each profile is a distillation — treat ``review_tips`` as hints
a user can override per résumé version, not hard filters.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

# Tier groupings used by downstream code to select default format rules
# (e.g. frontier_ai rarely wants a photo; jp often wants 職務経歴書 companion).
TIER_FRONTIER_AI = "frontier_ai"
TIER_AI_UNICORN = "ai_unicorn"
TIER_REGIONAL_AI = "regional_ai"
TIER_TW_LOCAL = "tw_local"
TIER_US_TIER2 = "us_tier2"
TIER_EU = "eu"
TIER_JP = "jp"
TIER_KR = "kr"

KNOWN_TIERS: frozenset[str] = frozenset({
    TIER_FRONTIER_AI, TIER_AI_UNICORN, TIER_REGIONAL_AI, TIER_TW_LOCAL,
    TIER_US_TIER2, TIER_EU, TIER_JP, TIER_KR,
})


@dataclass(frozen=True)
class CompanyProfile:
    key: str
    label: str
    tier: str
    locale_hint: str  # preferred render locale (en_US, ja_JP, ko_KR, zh_TW, …)
    must_haves: tuple[str, ...]
    plus_signals: tuple[str, ...]
    red_flags: tuple[str, ...]
    format_rules: tuple[str, ...]
    keyword_anchors: tuple[str, ...]
    enrich_bias: str
    review_tips: str


# Where YAML profiles live. Override with ``load_profiles(dir=...)`` in tests.
PROFILES_DIR: Path = Path(__file__).parent / "profiles"

_TUPLE_FIELDS: frozenset[str] = frozenset({
    "must_haves", "plus_signals", "red_flags", "format_rules", "keyword_anchors",
})
_REQUIRED_FIELDS: frozenset[str] = frozenset(f.name for f in fields(CompanyProfile))


class ProfileLoadError(ValueError):
    """Raised when a YAML profile is malformed or missing required fields."""


def _profile_from_yaml(path: Path) -> CompanyProfile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileLoadError(f"{path}: YAML parse error: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileLoadError(f"{path}: top-level YAML must be a mapping")

    missing = _REQUIRED_FIELDS - raw.keys()
    if missing:
        raise ProfileLoadError(f"{path}: missing required fields: {sorted(missing)}")

    extra = set(raw.keys()) - _REQUIRED_FIELDS
    if extra:
        raise ProfileLoadError(f"{path}: unknown fields: {sorted(extra)}")

    if raw["tier"] not in KNOWN_TIERS:
        raise ProfileLoadError(
            f"{path}: tier {raw['tier']!r} is not one of {sorted(KNOWN_TIERS)}"
        )

    if raw["key"] != path.stem:
        raise ProfileLoadError(
            f"{path}: key {raw['key']!r} does not match filename stem {path.stem!r}"
        )

    for fname in _TUPLE_FIELDS:
        val = raw[fname]
        if not isinstance(val, list) or not val:
            raise ProfileLoadError(f"{path}: field {fname} must be a non-empty list")
        raw[fname] = tuple(val)

    return CompanyProfile(**raw)


def load_profiles(dir: Path | None = None) -> dict[str, CompanyProfile]:
    """Load every ``*.yaml`` file under *dir* into a keyed registry.

    Filename stem must match the profile's ``key`` field. Duplicate keys or
    malformed files raise :class:`ProfileLoadError` rather than silently
    overwriting, so a broken commit fails loudly at import time.
    """
    src = dir or PROFILES_DIR
    if not src.is_dir():
        raise ProfileLoadError(f"profiles directory not found: {src}")

    registry: dict[str, CompanyProfile] = {}
    for path in sorted(src.glob("*.yaml")):
        prof = _profile_from_yaml(path)
        if prof.key in registry:
            raise ProfileLoadError(
                f"{path}: duplicate key {prof.key!r} already loaded from another file"
            )
        registry[prof.key] = prof
    return registry


# Eager-load at import so downstream callers treat this like a static registry.
# Re-bind at runtime via ``reload_profiles()`` in tests that add/remove files.
COMPANY_PROFILES: dict[str, CompanyProfile] = load_profiles()


def reload_profiles(dir: Path | None = None) -> dict[str, CompanyProfile]:
    """Clear and reload the module-level registry (test support)."""
    global COMPANY_PROFILES
    COMPANY_PROFILES = load_profiles(dir)
    return COMPANY_PROFILES


def get_company(key: str | None) -> CompanyProfile | None:
    if not key:
        return None
    return COMPANY_PROFILES.get(key)


def list_company_keys() -> list[str]:
    return list(COMPANY_PROFILES.keys())


def list_by_tier(tier: str) -> list[CompanyProfile]:
    return [p for p in COMPANY_PROFILES.values() if p.tier == tier]
