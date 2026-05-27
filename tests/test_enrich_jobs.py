"""Tests for core.enrich_jobs — emit/ingest of session-driven enrich prompts."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.enrich_jobs import EnrichJobEntry, EnrichJobManifest


def test_manifest_requires_locale():
    """Locale is a first-class dimension — emit must always know which locale."""
    with pytest.raises(ValidationError):
        EnrichJobManifest(
            version=1,
            created_at=datetime.now(timezone.utc),
            persona=None,
            tailor_keywords=None,
            company=None,
            level=None,
            groups=[],
        )  # missing locale=


def test_manifest_round_trips_via_json():
    m = EnrichJobManifest(
        version=1,
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
        locale="zh_TW",
        persona="tech_lead",
        tailor_keywords=["FastAPI", "RAG"],
        company=None,
        level="senior",
        groups=[
            EnrichJobEntry(
                id="001",
                name="proj-foo",
                prompt_path="001_proj-foo.prompt.md",
                output_path="001_proj-foo.yaml",
                status="pending",
            )
        ],
    )
    restored = EnrichJobManifest.model_validate_json(m.model_dump_json())
    assert restored.locale == "zh_TW"
    assert restored.groups[0].status == "pending"


def test_entry_status_must_be_pending_or_done():
    with pytest.raises(ValidationError):
        EnrichJobEntry(
            id="001",
            name="x",
            prompt_path="a",
            output_path="b",
            status="in-progress",  # not allowed
        )
