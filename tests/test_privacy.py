"""Tests for core.privacy.PrivacyFilter.

Security-adjacent: the filter is the last line of defence before project
names, client IDs, and secrets land in rendered résumé output. Every
rule here should be guarded by at least one test.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.privacy import PrivacyFilter
from core.schema import Activity, ActivityType, Source


def _activity(
    project: str = "public-project",
    summary: str = "",
    keywords: list[str] | None = None,
    files_touched: list[str] | None = None,
    extra: dict | None = None,
) -> Activity:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    return Activity(
        source=Source.CLAUDE_CODE,
        session_id="s1",
        timestamp_start=now,
        timestamp_end=now,
        project=project,
        activity_type=ActivityType.CODING,
        summary=summary,
        keywords=keywords or [],
        files_touched=files_touched or [],
        extra=extra or {},
    )


# ─────────────────────── redact_patterns ──────────────────────────────────


def test_empty_text_passes_through() -> None:
    """Neither "" nor None should blow up — the caller passes raw strings
    from extractors that sometimes have missing fields."""
    f = PrivacyFilter({"privacy": {"redact_patterns": [r"secret"]}})
    assert f.redact("") == ""
    assert f.redact(None) is None  # type: ignore[arg-type]  # defensive: tolerated in practice


def test_redact_patterns_replace_with_literal_tag() -> None:
    f = PrivacyFilter({"privacy": {"redact_patterns": [r"SK-[A-Z0-9]+"]}})
    assert f.redact("key SK-ABC123 stored") == "key [REDACTED] stored"


def test_multiple_redact_patterns_all_apply() -> None:
    f = PrivacyFilter(
        {"privacy": {"redact_patterns": [r"token-\w+", r"client-\w+"]}}
    )
    got = f.redact("sent token-abc to client-xyz")
    assert "token-" not in got
    assert "client-" not in got
    assert got.count("[REDACTED]") == 2


def test_no_patterns_means_no_redaction() -> None:
    f = PrivacyFilter({"privacy": {}})
    assert f.redact("untouched text") == "untouched text"


# ─────────────────────── abstract_tech ────────────────────────────────────


def test_abstract_tech_off_by_default() -> None:
    """Shipping stack names in résumé output is the common case — abstraction
    must be opt-in via the config flag, not happen silently."""
    f = PrivacyFilter({"privacy": {}})
    assert f.redact("Built on Postgres and Redis") == "Built on Postgres and Redis"


def test_abstract_tech_replaces_known_names_case_insensitively() -> None:
    f = PrivacyFilter({"privacy": {"abstract_tech": True}})
    got = f.redact("POSTGRES and redis and Next.js")
    assert "relational DB" in got
    assert "in-memory key/value store" in got
    assert "React meta-framework" in got
    # Shouldn't leak the original token.
    assert "POSTGRES" not in got
    assert "redis" not in got


def test_abstract_tech_preserves_surrounding_prose() -> None:
    f = PrivacyFilter({"privacy": {"abstract_tech": True}})
    assert f.redact("chose fastapi for latency") == "chose Python async web framework for latency"


@pytest.mark.parametrize("name", ["fastapi", "FastAPI", "FASTAPI", "fastApi"])
def test_abstract_tech_case_insensitive(name: str) -> None:
    f = PrivacyFilter({"privacy": {"abstract_tech": True}})
    assert f.redact(f"we use {name}") == "we use Python async web framework"


# ─────────────────────── is_blocked ───────────────────────────────────────


def test_is_blocked_none_project_is_false() -> None:
    f = PrivacyFilter({"privacy": {"blocklist": ["client-acme"]}})
    assert f.is_blocked(None) is False


def test_is_blocked_empty_blocklist_never_blocks() -> None:
    f = PrivacyFilter({"privacy": {}})
    assert f.is_blocked("anything") is False


def test_is_blocked_substring_match() -> None:
    """Blocklist entries are substrings, not exact names — so "acme" blocks
    "/Users/x/work/client-acme/frontend" too."""
    f = PrivacyFilter({"privacy": {"blocklist": ["acme"]}})
    assert f.is_blocked("/Users/x/work/client-acme/frontend") is True
    assert f.is_blocked("/Users/x/work/other-project") is False


# ─────────────────────── apply() end-to-end ───────────────────────────────


def test_apply_returns_none_for_blocked_project() -> None:
    """The contract other code depends on: a blocked activity never survives
    the filter, so it never reaches the aggregator / renderer."""
    f = PrivacyFilter({"privacy": {"blocklist": ["client-acme"]}})
    act = _activity(project="/work/client-acme/api", summary="sensitive")
    assert f.apply(act) is None


def test_apply_redacts_every_string_surface() -> None:
    f = PrivacyFilter({"privacy": {"redact_patterns": [r"SECRET-\w+"]}})
    act = _activity(
        project="public-project",
        summary="saw SECRET-abc",
        keywords=["SECRET-def", "normal"],
        files_touched=["/tmp/SECRET-ghi.txt"],
        extra={"note": "SECRET-jkl", "count": 5, "bool": True},
    )
    out = f.apply(act)
    assert out is not None
    assert "SECRET-" not in out.summary
    assert all("SECRET-" not in k for k in out.keywords)
    assert all("SECRET-" not in p for p in out.files_touched)
    # extra: string values redacted, non-string values passed through unchanged.
    assert "SECRET-" not in out.extra["note"]
    assert out.extra["count"] == 5
    assert out.extra["bool"] is True


def test_apply_with_no_rules_is_idempotent() -> None:
    """No blocklist, no patterns, abstraction off: activity passes through
    unchanged. This is the common dev-machine config — shouldn't rewrite data."""
    f = PrivacyFilter({"privacy": {}})
    act = _activity(summary="literal", keywords=["kw"], files_touched=["/x.py"])
    out = f.apply(act)
    assert out is not None
    assert out.summary == "literal"
    assert out.keywords == ["kw"]
    assert out.files_touched == ["/x.py"]


def test_apply_with_abstract_tech_hides_stack_names() -> None:
    """Composed rule: abstraction + block-free project. Summary should end
    up tech-free even without redact patterns."""
    f = PrivacyFilter({"privacy": {"abstract_tech": True}})
    act = _activity(summary="shipped a fastapi + postgres gateway")
    out = f.apply(act)
    assert out is not None
    assert "fastapi" not in out.summary.lower()
    assert "postgres" not in out.summary.lower()
    assert "Python async web framework" in out.summary
    assert "relational DB" in out.summary
