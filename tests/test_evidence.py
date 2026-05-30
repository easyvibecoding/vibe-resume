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


# --- #53/#54 gap reconciliation ---------------------------------------------

def test_keyword_gap_splits_present_vs_absent():
    from vibe_resume.core.evidence import keyword_gap
    g = _group([_act("Built a RAG pipeline", tech=["LlamaIndex"], kw=["pgvector"])])
    evs = [disclose_evidence(g)]
    # bullets mention pgvector but not LlamaIndex; Kubernetes not backed at all
    gap = keyword_gap(["LlamaIndex", "pgvector", "Kubernetes"], evs,
                      surfaced_text="optimized the pgvector index")
    assert gap.present_but_omitted == ["LlamaIndex"]   # backed, not surfaced → surface
    assert "pgvector" in gap.already_surfaced
    assert gap.genuinely_absent == ["Kubernetes"]      # not backed → honest gap (P1.3)


def test_unsurfaced_metrics_only_real_absent_from_bullets():
    from vibe_resume.core.evidence import unsurfaced_metrics
    g = _group([_act("Cut latency 40% and served 2k req/s")])
    ev = disclose_evidence(g)
    unsurf = unsurfaced_metrics(ev, surfaced_text="reduced latency 40% via caching")
    vals = {m.value for m in unsurf}
    assert any("2k" in v for v in vals)   # real, not yet in bullets → suggest
    assert "40%" not in vals              # already surfaced → not re-suggested
    # never invents: every suggestion traces to a real activity
    assert all(m.source_ref for m in unsurf)


# --- #58 metric-candidate noise filter --------------------------------------

def test_metric_candidates_drop_noise_keep_impact():
    g = _group([_act(
        "Cut latency 40% and 2.0x throughput, saved 256 h; "
        "on 2026-03-16 fixed PR #10171 at 10.0.0.61:443 (ref 4302464412)"
    )])
    ev = disclose_evidence(g)
    vals = {m.value for m in ev.candidate_metrics}
    # impact metrics kept
    assert "40%" in vals and any("2.0" in v and "x" in v.lower() for v in vals)
    assert any("256" in v and "h" in v for v in vals)
    # noise dropped: year, date frags, IP octets, port, PR#, long ID/phone run
    assert not any(v.strip() in {"2026", "03", "16", "10", "61", "443", "10171"} for v in vals)
    assert not any(v.strip() == "4302464412" for v in vals)
    assert not any(len(v.strip()) >= 7 and v.strip().isdigit() for v in vals)


def test_impact_metric_classifier_units():
    from vibe_resume.core.evidence import _is_impact_metric
    for good in ["40%", "2.0x", "1M", "12k", "256 h", "26 d", "$500", "35萬", "3倍"]:
        assert _is_impact_metric(good), good
    for noise in ["2026", "03", "443", "10171", "404", "4302464412", "126"]:
        assert not _is_impact_metric(noise), noise


# --- #62 context-based metric classification (anti-fabrication) -------------

def test_classify_metric_separates_noise_from_real():
    from vibe_resume.core.evidence import classify_metric
    # noise — context reveals it's not a perf metric
    assert classify_metric("89%", "信心閾值色帶 紅 90%+ / 橙 75-89%")[0] == "ui_threshold"
    assert classify_metric("100%", "css max-width: 100%")[0] == "css_value"
    assert classify_metric("1M", "Claude Opus (1M context) co-author")[0] == "model_spec"
    assert classify_metric("96%", "fragment of https://x/%96%85 encoded url")[0] == "url_fragment"
    for noise_ctx in ["信心閾值", "max-width: 100%", "1M context window"]:
        _, _, safe = classify_metric("100%", noise_ctx)
        assert safe is False
    # real — commit-confirmed perf metric
    kind, conf, safe = classify_metric("64%", "Docker image 優化(減少 64%)", "commit:abc")
    assert kind == "real_metric" and conf == "high" and safe is True


def test_unsurfaced_metrics_drops_classified_noise():
    g = _group([_act(
        "fault UI 信心閾值色帶 紅 90%+ 橙 75-89%; css max-width 100%; "
        "Docker image 優化(減少 64%)", ref="commit:abc")])
    ev = disclose_evidence(g)
    from vibe_resume.core.evidence import unsurfaced_metrics
    safe_vals = {m.value for m in unsurfaced_metrics(ev, surfaced_text="")}
    assert any("64" in v for v in safe_vals)            # real metric kept
    assert "100%" not in safe_vals                       # css noise dropped
    assert not any(v.strip() in {"90%", "89%", "75%"} for v in safe_vals)  # ui-threshold dropped
