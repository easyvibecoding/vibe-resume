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
