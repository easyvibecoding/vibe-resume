"""Tests for core.enrich_jobs — emit/ingest of session-driven enrich prompts."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from core.enrich_jobs import EnrichJobEntry, EnrichJobManifest


def test_manifest_requires_locale():
    """Locale is a first-class dimension — emit must always know which locale."""
    with pytest.raises(ValidationError):
        EnrichJobManifest(
            version=1,
            created_at=datetime.now(UTC),
            persona=None,
            tailor_keywords=None,
            company=None,
            level=None,
            groups=[],
        )  # missing locale=


def test_manifest_round_trips_via_json():
    m = EnrichJobManifest(
        version=1,
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
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


def test_manifest_rejects_naive_created_at():
    """AwareDatetime guards against silent timezone loss on round-trip."""
    with pytest.raises(ValidationError):
        EnrichJobManifest(
            version=1,
            created_at=datetime(2026, 5, 27, 12, 0),  # naive — no tzinfo
            locale="en_US",
            persona=None,
            tailor_keywords=None,
            company=None,
            level=None,
            groups=[],
        )


# ---------------------------------------------------------------------------
# emit_jobs tests (T2)
# ---------------------------------------------------------------------------
from pathlib import Path  # noqa: E402

from core.enrich_jobs import emit_jobs  # noqa: E402
from core.schema import ProjectGroup, Source  # noqa: E402


def _fake_group(name: str = "proj-foo") -> ProjectGroup:
    """Minimal ProjectGroup good enough for prompt emission."""
    return ProjectGroup(
        name=name,
        path=None,
        first_activity=datetime(2026, 1, 1, tzinfo=UTC),
        last_activity=datetime(2026, 2, 1, tzinfo=UTC),
        sources=[Source.CLAUDE_CODE],
        total_sessions=5,
        tech_stack=["FastAPI", "PostgreSQL"],
        category_counts={"backend": 3, "frontend": 2},
        capability_breadth=2,
        activities=[],
    )


def test_emit_writes_manifest_and_prompt_per_group(tmp_path: Path):
    groups = [_fake_group("proj-foo"), _fake_group("proj-bar")]
    jobs_dir = emit_jobs(
        groups=groups,
        out_root=tmp_path,
        persona=None,
        locale="en_US",
        tailor_keywords=None,
        company=None,
        level=None,
    )

    assert jobs_dir == tmp_path / "default" / "en_US"
    manifest_path = jobs_dir / "manifest.json"
    assert manifest_path.exists()

    from core.enrich_jobs import EnrichJobManifest
    m = EnrichJobManifest.model_validate_json(manifest_path.read_text())
    assert m.locale == "en_US"
    assert m.persona is None
    assert len(m.groups) == 2
    assert m.groups[0].status == "pending"

    for entry in m.groups:
        p = jobs_dir / entry.prompt_path
        assert p.exists() and p.stat().st_size > 0


def test_emit_separates_locales_under_same_persona(tmp_path: Path):
    """zh_TW and en_US runs must not stomp each other."""
    groups = [_fake_group("proj-foo")]
    en_dir = emit_jobs(groups, tmp_path, persona="tech_lead", locale="en_US",
                       tailor_keywords=None, company=None, level=None)
    zh_dir = emit_jobs(groups, tmp_path, persona="tech_lead", locale="zh_TW",
                       tailor_keywords=None, company=None, level=None)
    assert en_dir != zh_dir
    assert (en_dir / "manifest.json").exists()
    assert (zh_dir / "manifest.json").exists()


def test_emit_preserves_existing_yaml_on_re_emit(tmp_path: Path):
    """Re-running emit must NOT delete *.yaml the session has already written."""
    groups = [_fake_group("proj-foo")]
    out = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                    tailor_keywords=None, company=None, level=None)

    yaml_path = out / "001_proj-foo.yaml"
    yaml_path.write_text("summary: hi\n")

    emit_jobs(groups, tmp_path, persona=None, locale="en_US",
              tailor_keywords=None, company=None, level=None)
    assert yaml_path.exists(), "re-emit should not delete user-written yaml"
