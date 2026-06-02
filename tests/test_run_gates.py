"""Interactive Gate Mode wiring into `run` (#71).

Drives the gated `run` state machine through ``click.testing.CliRunner`` with a
stub config and monkeypatched heavy-pipeline functions, so no extractor /
aggregator / enricher / renderer / reviewer actually runs. Asserts:

- active-set resolution + ledger written;
- a `checkpoints` run stops at G1 first (emits G1.gate.json, exit 0, message);
- `--resume-from G5` computes render→review and prints a review-diff;
- plain `run` (no gate flags) is unchanged (no ledger, no pause);
- the G5 emit still rejects a non-safe metric (core P1 guard, exercised here).
"""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner


@pytest.fixture
def gated_root(tmp_path, monkeypatch):
    """Point cli.ROOT at a tmp dir and stub every heavy pipeline call to a no-op."""
    import vibe_resume.cli as cli_mod
    import vibe_resume.core.runner as runner_mod

    monkeypatch.setattr(cli_mod, "ROOT", tmp_path)
    (tmp_path / "data" / "cache").mkdir(parents=True)

    monkeypatch.setattr(runner_mod, "run_extractors", lambda cfg, **kw: None)
    monkeypatch.setattr(runner_mod, "run_aggregator", lambda cfg: None)
    monkeypatch.setattr(runner_mod, "run_enricher", lambda cfg, **kw: None)
    monkeypatch.setattr(runner_mod, "run_render", lambda cfg, **kw: [])
    return tmp_path


def _invoke(args):
    return CliRunner().invoke(
        __import__("vibe_resume.cli", fromlist=["cli"]).cli,
        args,
        obj={"config": {"render": {"locale": "en_US", "all_locales_formats": ["md"]}}},
    )


# ---- active-set resolution + ledger ----------------------------------------


def test_resolve_active_gates_checkpoints_default():
    from vibe_resume.core.gates import Gate
    from vibe_resume.core.run_gates import resolve_active_gates

    assert resolve_active_gates(interactive=True, preset=None, gates=None) == [
        Gate.G1_FRESHNESS, Gate.G2_GROUPING, Gate.G8_ACCEPTANCE,
    ]


def test_resolve_active_gates_explicit_overrides_preset():
    from vibe_resume.core.gates import Gate
    from vibe_resume.core.run_gates import resolve_active_gates

    out = resolve_active_gates(interactive=True, preset="full_review", gates="G5,G8,G5")
    assert out == [Gate.G5_METRICS, Gate.G8_ACCEPTANCE]  # de-duped, order preserved


def test_no_gate_flags_is_autopilot_empty():
    from vibe_resume.core.run_gates import resolve_active_gates

    assert resolve_active_gates(interactive=False, preset=None, gates=None) == []
    assert resolve_active_gates(interactive=False, preset="autopilot", gates=None) == []


def test_checkpoints_run_writes_ledger_with_active_set(gated_root):
    result = _invoke(["run", "--interactive", "--locales", "en_US"])
    assert result.exit_code == 0, result.output
    ledger = gated_root / "data" / "run_ledger.json"
    assert ledger.exists(), result.output
    data = json.loads(ledger.read_text())
    armed = data["decisions"][0]["decision"]["__active_set__"]
    assert armed == ["G1", "G2", "G8"]


# ---- pause at G1 -----------------------------------------------------------


def test_checkpoints_run_pauses_at_g1_first(gated_root):
    result = _invoke(["run", "--interactive", "--locales", "en_US"])
    assert result.exit_code == 0, result.output
    assert "paused at G1" in result.output
    gate_file = gated_root / "data" / "gates" / "G1.gate.json"
    assert gate_file.exists()
    gf = json.loads(gate_file.read_text())
    assert gf["gate"] == "G1"
    assert gf["status"] == "pending"
    # render must NOT have happened — we stopped at the first gate
    assert "render matrix" not in result.output


def test_continue_records_g1_decision_and_advances_to_g2(gated_root):
    # initial run pauses at G1
    _invoke(["run", "--interactive", "--locales", "en_US"])
    # fill in G1 decision
    gfp = gated_root / "data" / "gates" / "G1.gate.json"
    gf = json.loads(gfp.read_text())
    gf["decision"] = {"choice": "reuse"}
    gf["status"] = "decided"
    gfp.write_text(json.dumps(gf))

    result = _invoke(["run", "--interactive", "--locales", "en_US", "--continue"])
    assert result.exit_code == 0, result.output
    assert "recorded" in result.output and "G1" in result.output
    # now it should pause at G2 (next armed gate)
    assert "paused at G2" in result.output
    ledger = json.loads((gated_root / "data" / "run_ledger.json").read_text())
    g1 = next(d for d in ledger["decisions"] if d["gate"] == "G1")
    assert g1["decision"]["choice"] == "reuse"
    assert g1["timestamp"]  # CLI stamped it


# ---- full_review arms G3, which must pause (regression #74) -----------------


def _decide(gated_root, gate_id, decision):
    """Helper: write a decided gate file so the next --continue records it."""
    gfp = gated_root / "data" / "gates" / f"{gate_id}.gate.json"
    gf = json.loads(gfp.read_text())
    gf["decision"] = decision
    gf["status"] = "decided"
    gfp.write_text(json.dumps(gf))


def test_full_review_pauses_at_g3_after_g1_g2(gated_root):
    """#74: full_review arms G3 (overwrite). After G1+G2 are decided the run
    must PAUSE at G3 — not skip the enrich emit and render from raw output."""
    args = ["run", "--preset", "full_review", "--locales", "en_US"]
    # 1) initial → pause at G1
    _invoke(args)
    _decide(gated_root, "G1", {"choice": "reuse"})
    # 2) continue → pause at G2
    _invoke(args + ["--continue"])
    _decide(gated_root, "G2", {"choice": "top_n", "top_n": 20})
    # 3) continue → MUST pause at G3 (the bug rendered from raw + reported success)
    result = _invoke(args + ["--continue"])
    assert result.exit_code == 0, result.output
    assert "paused at G3" in result.output, result.output
    assert (gated_root / "data" / "gates" / "G3.gate.json").exists()
    # the silent-failure tells: enrich must NOT have been emitted, nothing rendered,
    # and the run must NOT claim completion.
    assert "render matrix" not in result.output
    assert "enrich manifest" not in result.output
    assert "gated run complete" not in result.output


def test_full_review_emits_enrich_and_pauses_at_g4_after_g3(gated_root):
    """Once G3 is decided, the next --continue emits enrich + pauses at G4."""
    args = ["run", "--preset", "full_review", "--locales", "en_US"]
    _invoke(args)
    _decide(gated_root, "G1", {"choice": "reuse"})
    _invoke(args + ["--continue"])
    _decide(gated_root, "G2", {"choice": "top_n", "top_n": 20})
    _invoke(args + ["--continue"])  # pause at G3
    _decide(gated_root, "G3", {"choice": "clean"})
    result = _invoke(args + ["--continue"])
    assert result.exit_code == 0, result.output
    assert "enrich manifest" in result.output  # emit happened
    assert "paused at G4" in result.output
    assert "render matrix" not in result.output


# ---- #83: don't replay extract on every --continue when cache is fresh ------


def test_g1_reextract_skips_extract_when_cache_fresh(gated_root, monkeypatch):
    import vibe_resume.core.curate as curate_mod
    import vibe_resume.core.runner as runner_mod
    from vibe_resume.core.gates import Gate, GateLedger
    from vibe_resume.core.run_gates import ledger_path

    # neutralize the #85 re-apply hook (no curation file in this scenario)
    monkeypatch.setattr(curate_mod, "CURATION_YAML",
                        gated_root / "data" / "cache" / "_nope.yaml")
    calls = {"extract": 0, "aggregate": 0}
    monkeypatch.setattr(runner_mod, "run_extractors",
                        lambda cfg, **kw: calls.__setitem__("extract", calls["extract"] + 1))
    monkeypatch.setattr(runner_mod, "run_aggregator",
                        lambda cfg: calls.__setitem__("aggregate", calls["aggregate"] + 1))
    # a FRESH extract cache marker (mtime = now)
    (gated_root / "data" / "cache" / "_project_groups.json").write_text("[]")
    led = GateLedger()
    led.record(Gate.G1_FRESHNESS,
               {"choice": "reextract", "__active_set__": ["G1", "G2", "G8"]}, "T1")
    led.save(ledger_path(gated_root / "data"))

    result = _invoke(["run", "--continue", "--preset", "checkpoints", "--locales", "en_US"])
    assert result.exit_code == 0, result.output
    assert calls["extract"] == 0, "fresh cache → extract must be skipped on replay (#83)"
    assert calls["aggregate"] == 1, "aggregate (cheap) still re-runs"


# ---- #85: gate recompute re-applies curation after aggregate ----------------


def test_recompute_reapplies_curation_after_aggregate(gated_root, monkeypatch):
    import vibe_resume.core.curate as curate_mod
    from vibe_resume.core.gates import Gate, GateLedger
    from vibe_resume.core.run_gates import ledger_path

    cur_yaml = gated_root / "data" / "cache" / "_curation.yaml"
    cur_yaml.write_text("version: 1\ngenerated_at: t\ngroups: []\n")
    monkeypatch.setattr(curate_mod, "CURATION_YAML", cur_yaml)
    applied = {"n": 0}

    def spy_run_curate(cfg, *, apply, now):
        if apply:
            applied["n"] += 1
        return "stub-curated"

    monkeypatch.setattr(curate_mod, "run_curate", spy_run_curate)
    # no fresh cache marker → reextract branch runs extract+aggregate → reapply fires
    led = GateLedger()
    led.record(Gate.G1_FRESHNESS,
               {"choice": "reextract", "__active_set__": ["G1", "G2", "G8"]}, "T1")
    led.save(ledger_path(gated_root / "data"))

    result = _invoke(["run", "--continue", "--preset", "checkpoints", "--locales", "en_US"])
    assert result.exit_code == 0, result.output
    assert applied["n"] >= 1, "curation must be re-applied after the recompute aggregate (#85)"


# ---- #90: machine-readable run state ---------------------------------------


def test_run_state_machine_readable():
    """#90: an agent must be able to read armed/wired/decision/pending/recompute
    deterministically instead of parsing prose."""
    from vibe_resume.core.gates import Gate, GateLedger
    from vibe_resume.core.run_gates import run_state

    led = GateLedger()
    led.record(Gate.G1_FRESHNESS, {"choice": "reextract"}, "T1")
    armed = [Gate.G1_FRESHNESS, Gate.G2_GROUPING, Gate.G7_VARIANTS, Gate.G8_ACCEPTANCE]
    st = run_state(armed, led)

    assert st["armed"] == ["G1", "G2", "G7", "G8"]
    # G7 is emit-only (not fully wired); G1/G2/G8 are fully wired
    assert set(st["fully_wired"]) == {"G1", "G2", "G8"}
    assert st["emit_only"] == ["G7"]
    # first undecided armed gate
    assert st["pending"] == "G2"
    g1 = st["gates"]["G1"]
    assert g1["decided"] is True and g1["decision"]["choice"] == "reextract"
    assert g1["fully_wired"] is True
    g7 = st["gates"]["G7"]
    assert g7["decided"] is False and g7["fully_wired"] is False
    # recompute suffix is a list of stage names (machine-readable, not prose)
    assert isinstance(g7["recompute_suffix"], list)


# ---- #94: G4 not armed → emit when no jobs, not silent un-enriched render ---


def test_g4_not_armed_emits_when_no_jobs_instead_of_rendering_raw(gated_root, monkeypatch):
    import vibe_resume.core.curate as curate_mod
    import vibe_resume.core.runner as runner_mod
    from vibe_resume.core.gates import Gate, GateLedger
    from vibe_resume.core.run_gates import ledger_path

    monkeypatch.setattr(curate_mod, "CURATION_YAML",
                        gated_root / "data" / "cache" / "_nope.yaml")
    calls = {"enrich": 0, "render": 0}
    monkeypatch.setattr(runner_mod, "run_enricher",
                        lambda cfg, **kw: calls.__setitem__("enrich", calls["enrich"] + 1))
    monkeypatch.setattr(runner_mod, "run_render",
                        lambda cfg, **kw: calls.__setitem__("render", calls["render"] + 1) or [])
    # fresh cache so G1=reextract doesn't re-extract; G1+G2 decided, pending G7.
    (gated_root / "data" / "cache" / "_project_groups.json").write_text("[]")
    led = GateLedger()
    led.record(Gate.G1_FRESHNESS,
               {"choice": "reuse", "__active_set__": ["G1", "G2", "G7", "G8"]}, "T1")
    led.record(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 18}, "T2")
    led.save(ledger_path(gated_root / "data"))

    result = _invoke(["run", "--continue", "--gates", "G1,G2,G7,G8", "--locales", "en_US"])
    assert result.exit_code == 0, result.output
    # emitted (not silently ingested-empty + rendered raw)
    assert "no enrich jobs" in result.output and "emitting" in result.output
    assert calls["enrich"] >= 1          # emit happened
    assert calls["render"] == 0          # did NOT render un-enriched groups
    assert "render matrix" not in result.output


# ---- plain run unchanged ---------------------------------------------------


def test_plain_run_no_gate_flags_no_ledger_no_pause(gated_root):
    result = _invoke(["run", "--locales", "en_US"])
    assert result.exit_code == 0, result.output
    assert "Phase A done" in result.output
    assert "paused at" not in result.output
    assert not (gated_root / "data" / "run_ledger.json").exists()


# ---- resume-from G5 → render,review + diff ---------------------------------


def test_resume_from_g5_renders_then_reviews_and_diffs(gated_root, monkeypatch):
    import vibe_resume.cli as cli_mod
    from vibe_resume.core import review as review_mod

    # seed a ledger so resume_plan has context (G5 alone → render,review)
    from vibe_resume.core.gates import Gate, GateLedger
    from vibe_resume.core.run_gates import ledger_path
    led = GateLedger()
    led.record(Gate.G5_METRICS, {"choice": "confirm"}, "2026-01-01T00:00:00+00:00")
    led.save(ledger_path(gated_root / "data"))

    calls = {"render": 0, "review": 0, "as_markdown": 0}

    def fake_render(cfg, **kw):
        calls["render"] += 1
        return []

    monkeypatch.setattr("vibe_resume.core.runner.run_render", fake_render)

    fake_path = gated_root / "resume_v001_en_US.md"
    fake_path.write_text("# resume\n")
    monkeypatch.setattr(review_mod, "resolve_resume_path", lambda *a, **kw: fake_path)

    class FakeReport:
        source = "resume_v001_en_US.md"
        locale = "en_US"

        def as_markdown(self, previous=None):
            calls["as_markdown"] += 1
            return "DIFF-RENDER"

    monkeypatch.setattr(review_mod, "review_file", lambda *a, **kw: FakeReport())
    monkeypatch.setattr(review_mod, "find_previous_review", lambda *a, **kw: None)
    monkeypatch.setattr(review_mod, "write_report", lambda *a, **kw: (None, None))

    result = CliRunner().invoke(
        cli_mod.cli,
        ["run", "--resume-from", "G5", "--locales", "en_US"],
        obj={"config": {"render": {"locale": "en_US", "all_locales_formats": ["md"]}}},
    )
    assert result.exit_code == 0, result.output
    assert "resume-from G5" in result.output
    assert "render" in result.output.lower() and "review" in result.output.lower()
    assert calls["render"] == 1          # render stage ran
    assert calls["as_markdown"] == 1     # review-diff printed
    assert "DIFF-RENDER" in result.output


# ---- G5 P1 fabrication guard still holds -----------------------------------


def test_g5_emit_rejects_non_safe_metric(tmp_path):
    from vibe_resume.core.gates import Gate, emit_gate

    bad_ctx = {"groups": [{"group": "x", "candidate_metrics": [
        {"value": "z-index:9999", "safe_to_surface": False},
    ]}]}
    with pytest.raises(ValueError, match="non-safe_to_surface"):
        emit_gate(Gate.G5_METRICS, tmp_path, context=bad_ctx)


def test_build_g5_context_filters_to_safe_only(monkeypatch):
    """build_gate_context(G5) only ever carries safe_to_surface metrics, so the
    emit guard cannot trip on tool-generated context."""
    from vibe_resume.core import run_gates

    class M:
        def __init__(self, value, safe):
            self.value, self.safe_to_surface = value, safe

        def as_dict(self):
            return {"value": self.value, "safe_to_surface": self.safe_to_surface}

    class E:
        group = "g1"
        candidate_metrics = [M("40%", True), M("z-index:9999", False)]

    # disclose_all is imported lazily inside build_gate_context; patch the source.
    import vibe_resume.core.evidence as ev
    monkeypatch.setattr(ev, "disclose_all", lambda *a, **kw: [E()])
    import vibe_resume.core.aggregator as agg
    monkeypatch.setattr(agg, "load_groups", lambda **kw: [])

    from vibe_resume.core.gates import Gate
    ctx = run_gates.build_gate_context(Gate.G5_METRICS, cfg={}, locale="en_US")
    metrics = ctx["groups"][0]["candidate_metrics"]
    assert all(m["safe_to_surface"] for m in metrics)
    assert [m["value"] for m in metrics] == ["40%"]
