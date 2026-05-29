"""#57 truth-preserving auto-iterate loop."""
from vibe_resume.core.iterate import _budget_ladder, auto_iterate


class _Rep:
    def __init__(self, total, max_total=100):
        self.total = total
        self.max_total = max_total
        self.grade = "B" if total / max_total >= 0.8 else "C"


def _render(b):  # md just encodes the budget for the fake reviewer
    return f"BUDGET={b}"


def test_ladder_tightens_from_target_to_floor():
    lad = _budget_ladder(2.0, floor=1.0, step=0.5)
    assert lad[0] is None              # round 0 = untouched baseline
    assert lad[1] == 2.0 and lad[-1] == 1.0


def test_reaches_bar_by_tightening_truthfully():
    scores = {"None": 70, "2.0": 75, "1.7": 82}

    def review(md):
        return _Rep(scores.get(md.split("=")[1], 70))

    res = auto_iterate(_render, review, page_target=2.0, bar=0.8)
    assert res.reached_bar is True
    assert res.best.grade == "B"
    assert "reached" in res.stop_reason.lower()


def test_stops_honestly_at_ceiling_with_suggestions():
    def review(md):
        return _Rep(70)  # never reaches bar, no matter the budget

    res = auto_iterate(_render, review, page_target=2.0, bar=0.8,
                       suggestion_fn=lambda: ["surface pgvector (backed but omitted)"])
    assert res.reached_bar is False
    assert "ceiling" in res.stop_reason.lower()
    # truthful human-applied suggestions surfaced; never auto-fabricated
    assert any("pgvector" in s for s in res.suggestions)
    assert any("never invent" in s.lower() for s in res.suggestions)


def test_best_round_picks_highest_score():
    seq = {"None": 70, "2.0": 75, "1.7": 72}

    def review(md):
        return _Rep(seq.get(md.split("=")[1], 70))

    res = auto_iterate(_render, review, page_target=2.0, bar=0.99, max_rounds=3)
    assert res.reached_bar is False
    assert res.best.max_pages == 2.0  # round 1 scored highest (75)


def test_cli_iterate_dryrun(tmp_path, monkeypatch):
    from pathlib import Path

    from click.testing import CliRunner

    import vibe_resume.core.aggregator as agg
    import vibe_resume.core.review as rv
    import vibe_resume.render.renderer as rnd
    from vibe_resume.cli import cli

    monkeypatch.setattr(rnd, "_render_md", lambda *a, **k: ("# md\n- did x\n", {"locale": {"_key": "en_US"}}))
    monkeypatch.setattr(rv, "review", lambda md, lk, **k: _Rep(70))
    monkeypatch.setattr(agg, "load_groups", lambda **k: [])
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("config.yaml").write_text("scan:\n  roots: []\n", encoding="utf-8")
        r = runner.invoke(cli, ["iterate", "--locale", "en_US"])
        assert r.exit_code == 0, r.output
        assert "auto-iterate" in r.output
        assert "ceiling" in r.output.lower()        # honest stop, not a fake pass
        assert "dry-run" in r.output.lower()
