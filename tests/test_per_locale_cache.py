"""Tests for per-locale enriched cache (groups_path_for + load_groups)."""
from __future__ import annotations

import orjson


def test_groups_path_for_includes_locale(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    assert aggregator.groups_path_for(None, None).name == "_project_groups.json"
    p1 = aggregator.groups_path_for(None, "en_US")
    assert p1.name == "_project_groups.default.en_US.json"

    p2 = aggregator.groups_path_for("tech_lead", "zh_TW")
    assert p2.name == "_project_groups.tech_lead.zh_TW.json"


def _seed_raw(tmp_path, name="raw"):
    return [{"name": name, "path": None,
            "first_activity": "2026-01-01T00:00:00+00:00",
            "last_activity": "2026-02-01T00:00:00+00:00",
            "sources": ["claude-code"], "total_sessions": 1,
            "tech_stack": [], "category_counts": {}, "capability_breadth": 0,
            "activities": []}]


def test_load_groups_prefers_exact_persona_locale(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    raw = _seed_raw(tmp_path)
    en = [{**raw[0], "name": "from-en", "summary": "en"}]
    (tmp_path / "_project_groups.json").write_bytes(orjson.dumps(raw))
    (tmp_path / "_project_groups.tech_lead.en_US.json").write_bytes(orjson.dumps(en))

    g = aggregator.load_groups(persona="tech_lead", locale="en_US")
    assert g[0].name == "from-en"


def test_load_groups_falls_back_to_default_persona_same_locale(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    raw = _seed_raw(tmp_path)
    default_en = [{**raw[0], "name": "from-default-en"}]
    (tmp_path / "_project_groups.json").write_bytes(orjson.dumps(raw))
    (tmp_path / "_project_groups.default.en_US.json").write_bytes(orjson.dumps(default_en))

    g = aggregator.load_groups(persona="tech_lead", locale="en_US")
    assert g[0].name == "from-default-en"


def test_load_groups_final_fallback_is_raw_aggregator(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    raw = _seed_raw(tmp_path, name="raw-only")
    (tmp_path / "_project_groups.json").write_bytes(orjson.dumps(raw))

    g = aggregator.load_groups(persona=None, locale="en_US")
    assert g[0].name == "raw-only"


def test_load_groups_empty_when_nothing_exists(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    assert aggregator.load_groups(persona="x", locale="en_US") == []
