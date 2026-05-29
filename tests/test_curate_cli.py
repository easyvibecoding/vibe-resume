"""In-process CliRunner tests for the `curate` command (emit + apply).

Cache paths are module-level constants resolved from VIBE_RESUME_ROOT at
import time, so we monkeypatch them directly onto the already-imported
modules rather than via the env var.
"""
from __future__ import annotations

import orjson
from click.testing import CliRunner

from vibe_resume.cli import cli
from vibe_resume.core import aggregator, curate
from vibe_resume.core.schema import ProjectGroup


def _seed(path, specs):
    groups = [
        ProjectGroup(name=n, path=p, first_activity="2026-01-01T00:00:00+00:00",
                     last_activity="2026-01-01T00:00:00+00:00", total_sessions=s)
        for n, p, s in specs
    ]
    path.write_bytes(orjson.dumps([g.model_dump(mode="json") for g in groups]))


def test_curate_emit_then_apply(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(curate, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(curate, "CURATION_YAML", tmp_path / "_curation.yaml")
    monkeypatch.setattr(curate, "CURATED_PATH", tmp_path / "_project_groups.curated.json")

    _seed(tmp_path / "_project_groups.json", [
        ("app", "/dev/app", 5),
        ("scratch", "/Users/me/tmp/scratch", 1),
    ])

    runner = CliRunner()
    r1 = runner.invoke(cli, ["curate"])
    assert r1.exit_code == 0, r1.output
    assert (tmp_path / "_curation.yaml").exists()

    r2 = runner.invoke(cli, ["curate", "--apply"])
    assert r2.exit_code == 0, r2.output
    curated = orjson.loads((tmp_path / "_project_groups.curated.json").read_bytes())
    names = {g["name"] for g in curated}
    assert names == {"app"}      # scratch auto-dropped


def test_curate_no_groups_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setattr(curate, "GROUPS_PATH", tmp_path / "missing.json")
    runner = CliRunner()
    r = runner.invoke(cli, ["curate"])
    assert r.exit_code == 0
    assert "aggregate" in r.output.lower()
