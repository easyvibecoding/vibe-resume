import orjson

from vibe_resume.core import aggregator
from vibe_resume.core.schema import ProjectGroup


def _dump(path, names):
    groups = [ProjectGroup(name=n, first_activity="2026-01-01T00:00:00+00:00",
                           last_activity="2026-01-01T00:00:00+00:00", total_sessions=1)
              for n in names]
    path.write_bytes(orjson.dumps([g.model_dump(mode="json") for g in groups]))


def test_load_groups_prefers_curated(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    _dump(aggregator.GROUPS_PATH, ["raw1", "raw2"])
    _dump(aggregator.CURATED_PATH, ["curated1"])
    got = aggregator.load_groups()
    assert [g.name for g in got] == ["curated1"]       # curated wins over raw


def test_load_groups_no_curated_uses_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    _dump(aggregator.GROUPS_PATH, ["raw1"])
    got = aggregator.load_groups()
    assert [g.name for g in got] == ["raw1"]


def test_load_groups_no_curated_flag_ignores_curated(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    _dump(aggregator.GROUPS_PATH, ["raw1"])
    _dump(aggregator.CURATED_PATH, ["curated1"])
    got = aggregator.load_groups(use_curated=False)
    assert [g.name for g in got] == ["raw1"]
