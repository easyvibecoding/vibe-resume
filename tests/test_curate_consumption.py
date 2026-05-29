import orjson

from vibe_resume.core import aggregator
from vibe_resume.core.schema import ProjectGroup


def _dump(path, names):
    groups = [ProjectGroup(name=n, first_activity="2026-01-01T00:00:00+00:00",
                           last_activity="2026-01-01T00:00:00+00:00", total_sessions=1)
              for n in names]
    path.write_bytes(orjson.dumps([g.model_dump(mode="json") for g in groups]))


def test_load_groups_prefers_curated(tmp_path, monkeypatch):
    # #42: monkeypatching ONLY GROUPS_PATH must also redirect the curated
    # lookup (derived as a sibling), so the suite stays hermetic.
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    _dump(aggregator.GROUPS_PATH, ["raw1", "raw2"])
    _dump(tmp_path / "_project_groups.curated.json", ["curated1"])
    got = aggregator.load_groups()
    assert [g.name for g in got] == ["curated1"]       # curated (sibling) wins over raw


def test_load_groups_no_curated_uses_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    _dump(aggregator.GROUPS_PATH, ["raw1"])
    got = aggregator.load_groups()
    assert [g.name for g in got] == ["raw1"]


def test_load_groups_no_curated_flag_ignores_curated(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    _dump(aggregator.GROUPS_PATH, ["raw1"])
    _dump(tmp_path / "_project_groups.curated.json", ["curated1"])
    got = aggregator.load_groups(use_curated=False)
    assert [g.name for g in got] == ["raw1"]


def test_load_groups_empty_when_nothing_exists(tmp_path, monkeypatch):
    # #42 regression: only GROUPS_PATH patched, no files at all → [] (no leak
    # from a real on-disk curated cache).
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    assert aggregator.load_groups() == []
