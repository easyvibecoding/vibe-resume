from vibe_resume.core import emphasis as em
from vibe_resume.core.emphasis import EmphasisRecord


def test_record_defaults():
    r = EmphasisRecord()
    assert r.intent == "" and r.keywords == [] and r.spotlight == [] and r.demote == []


def test_rank_delta_spotlight_demote_none():
    r = EmphasisRecord(spotlight=["A"], demote=["B"])
    assert em.rank_delta("A", r) == em._BOOST
    assert em.rank_delta("B", r) == -em._BOOST
    assert em.rank_delta("C", r) == 0
    assert em.rank_delta("A", None) == 0


def test_emphasis_block_contains_intent_keywords():
    r = EmphasisRecord(intent="security focus", keywords=["MCP", "guardrails"],
                       bias_instruction="Lead with the trade-off.")
    blk = em.emphasis_block(r)
    assert "security focus" in blk
    assert "MCP" in blk and "guardrails" in blk
    assert "Lead with the trade-off." in blk


def test_write_then_load_and_carry_forward(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    r = em.write_emphasis("first intent")
    assert r.intent == "first intent"
    # user edits keywords/spotlight by hand
    import yaml
    data = yaml.safe_load(em.EMPHASIS_PATH.read_text())
    data["keywords"] = ["agents"]
    data["spotlight"] = ["proj-x"]
    em.EMPHASIS_PATH.write_text(yaml.safe_dump(data))
    # re-running emphasis updates intent but keeps edits
    r2 = em.write_emphasis("second intent")
    assert r2.intent == "second intent"
    assert r2.keywords == ["agents"]
    assert r2.spotlight == ["proj-x"]


def test_load_respects_config_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    em.write_emphasis("x")
    assert em.load_emphasis({}) is not None
    assert em.load_emphasis({"emphasis": {"enabled": False}}) is None


def test_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    em.write_emphasis("x")
    assert em.clear_emphasis() is True
    assert em.load_emphasis({}) is None
    assert em.clear_emphasis() is False        # already gone
