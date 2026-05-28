"""Tests for core.enrich_jobs — emit/ingest of session-driven enrich prompts."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vibe_resume.core.enrich_jobs import EnrichJobEntry, EnrichJobManifest


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

REPO_ROOT = Path(__file__).resolve().parent.parent

from vibe_resume.core.enrich_jobs import emit_jobs  # noqa: E402
from vibe_resume.core.schema import ProjectGroup, Source  # noqa: E402


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

    from vibe_resume.core.enrich_jobs import EnrichJobManifest
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


def test_emit_carries_forward_done_status_for_existing_yaml(tmp_path: Path):
    """Re-emit preserves done status when yaml file is still present."""
    groups = [_fake_group("proj-foo")]
    out = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                    tailor_keywords=None, company=None, level=None)

    # Mark the entry as done by writing yaml + patching the manifest
    yaml_path = out / "001_proj-foo.yaml"
    yaml_path.write_text("summary: from session\n")
    m = EnrichJobManifest.model_validate_json((out / "manifest.json").read_text())
    m.groups[0].status = "done"
    (out / "manifest.json").write_bytes(m.model_dump_json().encode())

    # Re-emit should not flip status back to pending
    emit_jobs(groups, tmp_path, persona=None, locale="en_US",
              tailor_keywords=None, company=None, level=None)
    m2 = EnrichJobManifest.model_validate_json((out / "manifest.json").read_text())
    assert m2.groups[0].status == "done"


def test_emit_resets_to_pending_when_yaml_gone(tmp_path: Path):
    """If user deletes yaml, re-emit should reset status to pending."""
    groups = [_fake_group("proj-foo")]
    out = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                    tailor_keywords=None, company=None, level=None)
    m = EnrichJobManifest.model_validate_json((out / "manifest.json").read_text())
    m.groups[0].status = "done"
    (out / "manifest.json").write_bytes(m.model_dump_json().encode())
    # Note: no yaml file written → done status should NOT be carried forward

    emit_jobs(groups, tmp_path, persona=None, locale="en_US",
              tailor_keywords=None, company=None, level=None)
    m2 = EnrichJobManifest.model_validate_json((out / "manifest.json").read_text())
    assert m2.groups[0].status == "pending"


def test_slug_strips_trailing_dash_after_truncation():
    from vibe_resume.core.enrich_jobs import _slug
    # 59 chars of 'a' + dash-producing char → 60th char would be the dash
    name = "a" * 59 + " b"  # space becomes dash
    s = _slug(name)
    assert not s.endswith("-")
    assert len(s) <= 60


# ---------------------------------------------------------------------------
# ingest_jobs tests (T3)
# ---------------------------------------------------------------------------
from vibe_resume.core.enrich_jobs import ingest_jobs  # noqa: E402


def test_ingest_applies_yaml_back_into_groups(tmp_path: Path, monkeypatch):
    groups = [_fake_group("proj-foo")]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)

    yaml_body = """
summary: "Built RAG pipeline cutting latency 30%"
role_label: "Backend"
achievements:
  - "Designed FastAPI service handling 1k qps"
  - "Optimized pgvector index, p95 latency 300ms→200ms"
tech_stack: ["FastAPI", "PostgreSQL", "pgvector"]
keywords_for_ats: ["RAG"]
"""
    (jobs_dir / "001_proj-foo.yaml").write_text(yaml_body)

    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: groups)

    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert warnings == []
    assert len(enriched) == 1
    assert enriched[0].summary.startswith("Built RAG pipeline")
    assert "Designed FastAPI" in enriched[0].achievements[0]


def test_ingest_skips_missing_yaml_with_warning(tmp_path: Path, monkeypatch):
    groups = [_fake_group("proj-foo"), _fake_group("proj-bar")]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)
    (jobs_dir / "001_proj-foo.yaml").write_text(
        'summary: ok\nachievements: ["Built X"]\ntech_stack: []\n'
    )
    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: groups)

    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert len(enriched) == 2
    assert enriched[0].summary == "ok"
    assert any("002" in w or "proj-bar" in w for w in warnings)


def test_ingest_warns_on_invalid_yaml(tmp_path: Path, monkeypatch):
    groups = [_fake_group("proj-foo")]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)
    (jobs_dir / "001_proj-foo.yaml").write_text("not: valid: yaml: at: all:\n  - x")
    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: groups)

    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert any("proj-foo" in w for w in warnings)


# ---------------------------------------------------------------------------
# fixture sanity (T14)
# ---------------------------------------------------------------------------


def test_sample_fixture_manifest_parses():
    """Sanity: the shipped sample fixture stays in sync with the schema."""
    fixture = REPO_ROOT / "tests" / "fixtures" / "enrich_jobs_sample" / "manifest.json"
    m = EnrichJobManifest.model_validate_json(fixture.read_text())
    assert m.locale == "en_US"
    assert m.groups[0].status == "done"
    assert (fixture.parent / m.groups[0].prompt_path).exists()
    assert (fixture.parent / m.groups[0].output_path).exists()


# ---------------------------------------------------------------------------
# Fix #8 — manifest records JD sha+mtime; ingest warns on drift
# ---------------------------------------------------------------------------

from vibe_resume.core.enrich_jobs import EnrichTailorInfo  # noqa: E402


def test_manifest_schema_accepts_tailor_info():
    """EnrichTailorInfo round-trips through EnrichJobManifest.model_dump_json."""
    m = EnrichJobManifest(
        created_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        locale="en_US",
        tailor=EnrichTailorInfo(
            path="data/imports/jd.txt",
            sha256="a" * 64,
            mtime=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
            extracted_keywords=["FastAPI", "RAG"],
        ),
        groups=[],
    )
    assert m.tailor is not None
    assert m.tailor.sha256.startswith("a")
    # round-trip
    restored = EnrichJobManifest.model_validate_json(m.model_dump_json())
    assert restored.tailor is not None
    assert restored.tailor.extracted_keywords == ["FastAPI", "RAG"]
    assert restored.tailor.strict is False


def test_ingest_warns_on_jd_sha_mismatch(tmp_path: Path, monkeypatch):
    """ingest_jobs emits a warning when the JD file content changed since emit."""
    import hashlib

    jd = tmp_path / "jd.txt"
    jd.write_text("original JD content")
    orig_sha = hashlib.sha256(jd.read_bytes()).hexdigest()

    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    manifest = EnrichJobManifest(
        created_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        locale="en_US",
        tailor=EnrichTailorInfo(
            path=str(jd),
            sha256=orig_sha,
            mtime=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
            extracted_keywords=["X"],
        ),
        groups=[],
    )
    (jobs_dir / "manifest.json").write_text(manifest.model_dump_json())

    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: [])

    # JD unchanged — no sha-mismatch warning
    _, w1 = ingest_jobs(jobs_dir / "manifest.json")
    assert not any("sha mismatch" in s for s in w1)

    # Edit JD — should trigger the warning
    jd.write_text("EDITED JD content")
    _, w2 = ingest_jobs(jobs_dir / "manifest.json")
    assert any("sha mismatch" in s for s in w2)


def test_ingest_no_tailor_no_warning(tmp_path: Path, monkeypatch):
    """When manifest.tailor is None (no --tailor flag), no sha warning is produced."""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    manifest = EnrichJobManifest(
        created_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        locale="en_US",
        tailor=None,
        groups=[],
    )
    (jobs_dir / "manifest.json").write_text(manifest.model_dump_json())
    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: [])

    _, w = ingest_jobs(jobs_dir / "manifest.json")
    assert not any("sha mismatch" in s for s in w)


# ---------------------------------------------------------------------------
# Fix #20 — --clean flag + re-emit yaml warning
# ---------------------------------------------------------------------------


def test_emit_clean_flag_clears_old_yaml(tmp_path: Path):
    """--clean deletes pre-existing *.yaml files before writing fresh prompts."""
    groups = [_fake_group("proj-foo")]
    out = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                    tailor_keywords=None, company=None, level=None)
    (out / "001_proj-foo.yaml").write_text("old\n")

    emit_jobs(groups, tmp_path, persona=None, locale="en_US",
              tailor_keywords=None, company=None, level=None, clean=True)

    assert not (out / "001_proj-foo.yaml").exists()


def test_emit_no_clean_preserves_old_yaml(tmp_path: Path):
    """Without --clean, existing *.yaml survive a re-emit."""
    groups = [_fake_group("proj-foo")]
    out = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                    tailor_keywords=None, company=None, level=None)
    (out / "001_proj-foo.yaml").write_text("kept\n")

    emit_jobs(groups, tmp_path, persona=None, locale="en_US",
              tailor_keywords=None, company=None, level=None)

    assert (out / "001_proj-foo.yaml").exists()
    assert (out / "001_proj-foo.yaml").read_text() == "kept\n"
