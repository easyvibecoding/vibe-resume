"""#33: duplicate-named groups must not collide on ingest (matched by index)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vibe_resume.core.enrich_jobs import emit_jobs, ingest_jobs
from vibe_resume.core.schema import ProjectGroup, Source


def _grp(name: str, sessions: int) -> ProjectGroup:
    return ProjectGroup(
        name=name, path=None,
        first_activity=datetime(2026, 1, 1, tzinfo=UTC),
        last_activity=datetime(2026, 2, 1, tzinfo=UTC),
        sources=[Source.CLAUDE_CODE], total_sessions=sessions,
        tech_stack=["FastAPI"], category_counts={"backend": sessions},
        capability_breadth=1, activities=[],
    )


def test_duplicate_names_do_not_collide(tmp_path, monkeypatch):
    # Two groups with the SAME name but different session counts
    groups = [_grp("proj", 30), _grp("proj", 5)]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)

    # Distinct YAML content per entry (001 = the rich one, 002 = the thin one)
    (jobs_dir / "001_proj.yaml").write_text(
        'summary: "rich group"\nachievements: ["Built the big thing"]\ntech_stack: []\n'
    )
    (jobs_dir / "002_proj.yaml").write_text(
        'summary: "thin group"\nachievements: ["Small fix"]\ntech_stack: []\n'
    )

    # ingest must see the SAME two raw groups in the same order
    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: groups)
    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")

    assert len(enriched) == 2
    # Each entry's YAML landed on its OWN group — no overwrite
    assert enriched[0].summary == "rich group"
    assert enriched[0].achievements == ["Built the big thing"]
    assert enriched[1].summary == "thin group"
    assert enriched[1].achievements == ["Small fix"]
    # No spurious warnings (names match raw order)
    assert not [w for w in warnings if "mismatch" in w]


def test_index_out_of_range_warns_not_crashes(tmp_path, monkeypatch):
    groups = [_grp("a", 10), _grp("b", 10)]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)
    (jobs_dir / "001_a.yaml").write_text('summary: ok\nachievements: []\ntech_stack: []\n')
    (jobs_dir / "002_b.yaml").write_text('summary: ok\nachievements: []\ntech_stack: []\n')
    # raw shrank since emit (only 1 group now) → entry 002 out of range
    monkeypatch.setattr("vibe_resume.core.enrich_jobs._load_raw_groups", lambda: [groups[0]])
    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert len(enriched) == 1
    assert any("out of range" in w for w in warnings)
