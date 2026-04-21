"""Tests for the small pure helpers extracted from aggregate_from_cache.

Covers: prior-enrichment carry-over, user-metrics loading from profile.yaml,
and the fuzzy project-name → metrics lookup.
"""
from __future__ import annotations

from pathlib import Path

import orjson
import pytest

from core import aggregator
from core.aggregator import _metrics_for_project


def _write_groups(path: Path, groups: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(groups))


# ─────────────────────── _load_prior_enrichment ───────────────────────────


def test_prior_enrichment_returns_empty_when_file_absent(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "does_not_exist.json")
    assert aggregator._load_prior_enrichment() == {}


def test_prior_enrichment_keeps_enriched_groups_only(
    tmp_path, monkeypatch
) -> None:
    """Groups with NO summary and NO achievements shouldn't be carried over —
    otherwise running `aggregate` after deleting the cache but before re-running
    `enrich` would silently resurrect blank entries."""
    p = tmp_path / "_project_groups.json"
    _write_groups(
        p,
        [
            {"name": "filled", "summary": "", "achievements": ["a"]},  # enriched
            {"name": "drafted", "summary": "draft only", "achievements": []},  # enriched
            {"name": "bare", "summary": "", "achievements": []},  # skip
        ],
    )
    monkeypatch.setattr(aggregator, "GROUPS_PATH", p)

    prior = aggregator._load_prior_enrichment()
    assert set(prior) == {"filled", "drafted"}


def test_prior_enrichment_tolerates_corrupt_file(
    tmp_path, monkeypatch
) -> None:
    """A hand-corrupted cache must not abort the whole aggregate pipeline."""
    p = tmp_path / "_project_groups.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"not json at all")
    monkeypatch.setattr(aggregator, "GROUPS_PATH", p)

    assert aggregator._load_prior_enrichment() == {}


# ─────────────────────── _load_user_metrics ───────────────────────────────


def test_user_metrics_absent_profile_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(aggregator, "ROOT", tmp_path)  # no profile.yaml present
    assert aggregator._load_user_metrics() == {}


def test_user_metrics_reads_project_metrics_section(tmp_path, monkeypatch) -> None:
    (tmp_path / "profile.yaml").write_text(
        "project_metrics:\n"
        "  gateway: [\"4.2M req/day\", \"p99 180ms\"]\n"
        "  design-system: [\"86 components migrated\"]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(aggregator, "ROOT", tmp_path)

    metrics = aggregator._load_user_metrics()
    assert metrics["gateway"] == ["4.2M req/day", "p99 180ms"]
    assert metrics["design-system"] == ["86 components migrated"]


def test_user_metrics_non_dict_payload_rejected(tmp_path, monkeypatch) -> None:
    """If a user puts `project_metrics: "oops"` instead of a mapping, we must
    not crash later trying to .items() on a string."""
    (tmp_path / "profile.yaml").write_text(
        "project_metrics: oops\n", encoding="utf-8"
    )
    monkeypatch.setattr(aggregator, "ROOT", tmp_path)
    assert aggregator._load_user_metrics() == {}


def test_user_metrics_malformed_yaml_returns_empty(tmp_path, monkeypatch) -> None:
    (tmp_path / "profile.yaml").write_text(
        "project_metrics:\n  gateway: [\n", encoding="utf-8"  # unclosed list
    )
    monkeypatch.setattr(aggregator, "ROOT", tmp_path)
    assert aggregator._load_user_metrics() == {}


# ─────────────────────── _metrics_for_project ─────────────────────────────


@pytest.mark.parametrize(
    "display_name, metrics_dict, expected",
    [
        # Exact case-insensitive match.
        ("Gateway", {"gateway": ["a"]}, ["a"]),
        # Profile key is a substring of the inferred name.
        ("internal-token-gateway", {"gateway": ["a", "b"]}, ["a", "b"]),
        # Inferred name is a substring of the profile key.
        ("bot", {"ops-runbook-bot": ["c"]}, ["c"]),
        # No match.
        ("other", {"gateway": ["a"]}, []),
        # First match wins — "gateway" hits before "ops-runbook-bot".
        (
            "gateway-runbook",
            {"gateway": ["first"], "runbook": ["second"]},
            ["first"],
        ),
        # Non-list value for the first name match yields [] and does NOT
        # fall through to later keys — this matches the pre-refactor break
        # semantics. If you want fallthrough, change the semantics explicitly,
        # not by tripping over a malformed profile entry.
        (
            "internal-token-gateway",
            {"gateway": "not a list", "internal": ["fallback"]},
            [],
        ),
    ],
)
def test_metrics_lookup_fuzzy(
    display_name: str, metrics_dict: dict, expected: list[str]
) -> None:
    assert _metrics_for_project(display_name, metrics_dict) == expected
