"""Tests for the evidence-disclosure layer (#51 P2)."""
from datetime import UTC, datetime

from vibe_resume.core.evidence import disclose_all, disclose_evidence
from vibe_resume.core.schema import Activity, ProjectGroup, Source


def _act(summary, ref="r1", tech=None, kw=None):
    return Activity(
        source=Source.CLAUDE_CODE,
        session_id="s1",
        timestamp_start=datetime(2026, 1, 1, tzinfo=UTC),
        summary=summary,
        raw_ref=ref,
        tech_stack=tech or [],
        keywords=kw or [],
    )


def _group(acts, name="proj", tech=None):
    return ProjectGroup(
        name=name,
        first_activity=datetime(2026, 1, 1, tzinfo=UTC),
        last_activity=datetime(2026, 2, 1, tzinfo=UTC),
        total_sessions=len(acts),
        activities=acts,
        tech_stack=tech or [],
    )


def test_discloses_real_metrics_with_provenance():
    g = _group([
        _act("Cut latency 40% and handled 2k req/s", ref="commit:abc"),
        _act("Refactored the parser", ref="commit:def"),
    ])
    ev = disclose_evidence(g)
    vals = {m.value for m in ev.candidate_metrics}
    assert "40%" in vals
    assert any("2k" in v for v in vals)
    assert all(m.source_ref for m in ev.candidate_metrics)  # provenance present
    assert "commit:abc" in ev.provenance


def test_never_invents_absent_metric():
    g = _group([_act("Improved the build, no numbers here")])
    ev = disclose_evidence(g)
    assert ev.candidate_metrics == []
    assert ev.has_real_metrics is False


def test_backed_terms_and_backs_term():
    g = _group([_act("Built a RAG pipeline", tech=["LlamaIndex"], kw=["pgvector"])],
               tech=["FastAPI"])
    ev = disclose_evidence(g)
    assert ev.backs_term("llamaindex")   # case-insensitive
    assert ev.backs_term("pgvector")
    assert ev.backs_term("FastAPI")
    assert not ev.backs_term("Kubernetes")  # genuinely absent → honest gap (#54)


def test_human_gate_evidence_english_and_locale():
    g_en = _group([_act("Architected the pipeline; reviewed every diff before merge")])
    ev_en = disclose_evidence(g_en)
    assert ev_en.has_human_gate
    assert any(h.term == "reviewed" for h in ev_en.human_gate_evidence)

    g_zh = _group([_act("以 Claude Code 協作,所有產出經人工把關後合併")])
    ev_zh = disclose_evidence(g_zh, lang="zh")
    assert ev_zh.has_human_gate  # #50 locale-aware gate
    # without zh locale, the zh phrase is not in the English base list
    assert disclose_evidence(g_zh, lang=None).has_human_gate is False


def test_disclose_all_and_as_dict():
    evs = disclose_all([_group([_act("Shipped 3x faster")])])
    assert len(evs) == 1
    d = evs[0].as_dict()
    assert d["group"] == "proj" and d["candidate_metrics"]


def test_cli_evidence_json(tmp_path, monkeypatch):
    from pathlib import Path

    from click.testing import CliRunner

    import vibe_resume.cli as cli_mod
    from vibe_resume.cli import cli
    monkeypatch.setattr(cli_mod, "load_groups", lambda: [_group([_act("Cut latency 40%")])], raising=False)
    # patch the symbol used inside the command (imported locally) via aggregator
    import vibe_resume.core.aggregator as agg
    monkeypatch.setattr(agg, "load_groups", lambda: [_group([_act("Cut latency 40%")])])
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("config.yaml").write_text("scan:\n  roots: []\n", encoding="utf-8")
        r = runner.invoke(cli, ["evidence", "--json"])
        assert r.exit_code == 0, r.output
        assert "40%" in r.output and "candidate_metrics" in r.output
