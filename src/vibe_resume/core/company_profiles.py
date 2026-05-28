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

import re
from dataclasses import dataclass, field, fields
from datetime import date, datetime
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
    # Hallucination-guard metadata: when this profile was last fact-checked,
    # and optional pointers to the sources consulted. ``verification_sources``
    # is optional (defaults to empty) so new profiles can be staged without
    # a full citation list, but ``last_verified_at`` is mandatory so every
    # profile carries a visible age — stale entries can then be surfaced by
    # ``stale_profiles(...)`` / ``vibe-resume company audit``.
    last_verified_at: str = ""  # ISO 8601 date, YYYY-MM-DD
    verification_sources: tuple[str, ...] = field(default_factory=tuple)

    def verified_date(self) -> date:
        """Parse ``last_verified_at`` to a :class:`datetime.date`.

        Loader has already validated the format, so this cannot fail for any
        profile registered in :data:`COMPANY_PROFILES`.
        """
        return datetime.strptime(self.last_verified_at, "%Y-%m-%d").date()


# Where YAML profiles live. Override with ``load_profiles(dir=...)`` in tests.
PROFILES_DIR: Path = Path(__file__).parent / "profiles"

_TUPLE_FIELDS: frozenset[str] = frozenset({
    "must_haves", "plus_signals", "red_flags", "format_rules", "keyword_anchors",
})
# Fields that may be omitted from YAML (loader supplies a default).
_OPTIONAL_FIELDS: frozenset[str] = frozenset({"verification_sources"})
_REQUIRED_FIELDS: frozenset[str] = (
    frozenset(f.name for f in fields(CompanyProfile)) - _OPTIONAL_FIELDS
)
_ALL_FIELDS: frozenset[str] = frozenset(f.name for f in fields(CompanyProfile))


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

    extra = set(raw.keys()) - _ALL_FIELDS
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

    # Validate ``last_verified_at`` is an ISO 8601 calendar date (YYYY-MM-DD)
    # so every registered profile can be compared against today without
    # runtime parsing surprises elsewhere in the codebase.
    lva = raw["last_verified_at"]
    if not isinstance(lva, str) or not lva:
        raise ProfileLoadError(
            f"{path}: last_verified_at must be a non-empty YYYY-MM-DD string"
        )
    try:
        datetime.strptime(lva, "%Y-%m-%d")
    except ValueError as exc:
        raise ProfileLoadError(
            f"{path}: last_verified_at {lva!r} is not a valid YYYY-MM-DD date: {exc}"
        ) from exc

    # verification_sources is optional — normalise to tuple when present.
    if "verification_sources" in raw:
        vs = raw["verification_sources"]
        if not isinstance(vs, list):
            raise ProfileLoadError(
                f"{path}: verification_sources must be a list (may be empty or omitted)"
            )
        raw["verification_sources"] = tuple(vs)

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


def days_since_verification(profile: CompanyProfile, today: date | None = None) -> int:
    """Days elapsed between a profile's last fact-check date and *today*.

    Pass ``today`` to freeze the reference point in tests; otherwise uses
    the local system date. Negative values are theoretically possible if a
    YAML declares a future verification date — the loader does not block
    that, so callers that care should guard with ``max(0, …)``.
    """
    ref = today or date.today()
    return (ref - profile.verified_date()).days


# 90-day default — the AI/tech hiring market currently rebrands products,
# restructures interview processes, and shifts tech-stack expectations on
# roughly quarterly cadence (e.g. Kolr was renamed from KOL Radar within
# a single year, LINE-Naver tech ties were severed end-2024, Anthropic's
# AI-in-application policy flipped twice in 2025). A 90-day ceiling keeps
# bundled profiles close to that rhythm without forcing verification on
# every résumé run. Override via ``--stale-days`` for looser checks.
STALE_DEFAULT_DAYS = 90


def is_stale(
    profile: CompanyProfile,
    threshold_days: int = STALE_DEFAULT_DAYS,
    today: date | None = None,
) -> bool:
    """Convenience predicate — profile age exceeds the staleness threshold.

    Used both at CLI level (print a warning whenever a stale profile is
    applied via ``--company``) and inside the verify workflow to decide
    whether an auto-refresh is due. Default threshold tracks
    :data:`STALE_DEFAULT_DAYS` (90 days) to match the current AI-hiring
    market's quarterly rebrand / restack cadence.
    """
    return days_since_verification(profile, today) > threshold_days


def stale_profiles(
    threshold_days: int = STALE_DEFAULT_DAYS,
    today: date | None = None,
    registry: dict[str, CompanyProfile] | None = None,
) -> list[CompanyProfile]:
    """Return all profiles older than *threshold_days* since last verified.

    The 90-day default matches the quarterly cadence at which AI-company
    products, interview processes, and stack expectations visibly shift in
    the 2025-2026 market. Tighten via the argument when a specific workflow
    needs fresher guarantees (e.g. 30-day for frontier-lab profiles), or
    loosen for lower-churn enterprise employers. Sorted oldest-first so
    callers can print a "fix these next" list directly.
    """
    reg = registry or COMPANY_PROFILES
    ref = today or date.today()
    aged = [
        (days_since_verification(p, ref), p)
        for p in reg.values()
    ]
    stale = [p for d, p in aged if d > threshold_days]
    stale.sort(key=lambda p: p.verified_date())
    return stale


# ---------------------------------------------------------------------------
# Persistent date-update helper — used by ``vibe-resume company mark-verified``
# after a human (or a ``company verify`` claude-agent call) confirms a profile
# is current. We rewrite only the ``last_verified_at`` line in place so any
# folded-string blocks, comments, or user hand-edits elsewhere in the YAML
# survive unchanged. Full YAML dump-reload would lose formatting.
# ---------------------------------------------------------------------------

_LAST_VERIFIED_LINE_RE = re.compile(
    r"^last_verified_at:\s*.*$",
    re.MULTILINE,
)


def update_last_verified_at(
    key: str,
    new_date: date | str,
    dir: Path | None = None,
) -> Path:
    """Rewrite one profile YAML's ``last_verified_at`` line to *new_date*.

    Accepts either a ``date`` or a YYYY-MM-DD string; validates the string
    form. Returns the updated file path. Raises :class:`ProfileLoadError`
    if the profile is unknown or the YAML does not contain an existing
    ``last_verified_at:`` line to replace.
    """
    src = dir or PROFILES_DIR
    path = src / f"{key}.yaml"
    if not path.exists():
        raise ProfileLoadError(f"profile not found: {path}")

    if isinstance(new_date, str):
        try:
            datetime.strptime(new_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ProfileLoadError(
                f"new_date {new_date!r} is not a valid YYYY-MM-DD date: {exc}"
            ) from exc
        date_str = new_date
    else:
        date_str = new_date.isoformat()

    text = path.read_text(encoding="utf-8")
    replacement = f"last_verified_at: '{date_str}'"
    new_text, n = _LAST_VERIFIED_LINE_RE.subn(replacement, text)
    if n == 0:
        raise ProfileLoadError(
            f"{path}: no existing last_verified_at line to rewrite"
        )
    if n > 1:
        raise ProfileLoadError(
            f"{path}: unexpectedly matched last_verified_at {n} times"
        )
    path.write_text(new_text, encoding="utf-8")
    return path
