"""#70 interactive gate-mode core: definitions, invalidation graph, ledger, files."""
from __future__ import annotations

import json

from vibe_resume.core.gates import (
    CANONICAL_ORDER,
    GATE_DEFS,
    INVALIDATION,
    PRESETS,
    Gate,
    GateFile,
    GateLedger,
    Stage,
    emit_gate,
    g5_safe_metric_values,
    gate_file_path,
    invalidated_stages,
    preset_gates,
    read_gate_decision,
    resume_plan,
)

# ---- definitions / presets -------------------------------------------------


def test_eight_gates_defined_with_choices():
    assert len(Gate) == 8
    for g in Gate:
        d = GATE_DEFS[g]
        assert d.short and d.description and d.choices


def test_presets():
    assert preset_gates("autopilot") == []
    assert preset_gates("checkpoints") == [
        Gate.G1_FRESHNESS, Gate.G2_GROUPING, Gate.G8_ACCEPTANCE
    ]
    assert preset_gates("full_review") == list(Gate)
    assert set(PRESETS) == {"autopilot", "checkpoints", "full_review"}


# ---- invalidation graph (the priority: ordered recompute suffix) -----------


def _names(stages):
    return [s.value for s in stages]


def test_g1_invalidates_everything_in_order():
    assert invalidated_stages(Gate.G1_FRESHNESS) == list(CANONICAL_ORDER)
    assert _names(invalidated_stages(Gate.G1_FRESHNESS)) == [
        "extract", "aggregate", "enrich", "metrics", "render", "review"
    ]


def test_g2_grouping_keeps_extract():
    # #70 item 7: grouping change re-derives AGGREGATE onward; only EXTRACT kept.
    assert _names(invalidated_stages(Gate.G2_GROUPING)) == [
        "aggregate", "enrich", "metrics", "render", "review"
    ]
    assert Stage.EXTRACT not in invalidated_stages(Gate.G2_GROUPING)


def test_g4_bullets_keeps_enrich_starts_at_metrics():
    out = invalidated_stages(Gate.G4_BULLETS)
    assert Stage.ENRICH not in out
    assert _names(out) == ["metrics", "render", "review"]


def test_g5_metrics_render_review_only():
    assert _names(invalidated_stages(Gate.G5_METRICS)) == ["render", "review"]


def test_g6_g7_keep_enrich_and_metrics():
    for g in (Gate.G6_REDACTION, Gate.G7_VARIANTS):
        out = invalidated_stages(g)
        assert Stage.ENRICH not in out and Stage.METRICS not in out
        assert _names(out) == ["render", "review"]


def test_g8_terminal_recomputes_nothing():
    assert invalidated_stages(Gate.G8_ACCEPTANCE) == []
    assert INVALIDATION[Gate.G8_ACCEPTANCE].terminal


def test_every_recompute_set_is_a_canonical_suffix_minus_keeps():
    """Robustness invariant: a recompute list is always in canonical order and
    never reorders or skips relative to CANONICAL_ORDER (#70)."""
    order = list(CANONICAL_ORDER)
    for g in Gate:
        out = invalidated_stages(g)
        # ordered exactly as canonical
        assert out == [s for s in order if s in set(out)]
        # contiguity check: removing 'keep' stages, the rest is a true suffix
        inv = INVALIDATION[g]
        if inv.terminal or inv.start is None:
            continue
        start_i = order.index(inv.start)
        assert out == [s for s in order[start_i:] if s not in inv.keep]


# ---- ledger ----------------------------------------------------------------


def test_ledger_record_overwrites_in_place_preserving_order():
    led = GateLedger()
    led.record(Gate.G1_FRESHNESS, {"choice": "reuse"}, "2026-05-30T00:00:00+00:00")
    led.record(Gate.G2_GROUPING, {"choice": "accept"}, "2026-05-30T00:01:00+00:00")
    led.record(Gate.G1_FRESHNESS, {"choice": "reextract"}, "2026-05-30T00:02:00+00:00")
    assert [d.gate for d in led.decisions] == [Gate.G1_FRESHNESS, Gate.G2_GROUPING]
    assert led.get(Gate.G1_FRESHNESS).decision == {"choice": "reextract"}
    assert led.get(Gate.G1_FRESHNESS).timestamp == "2026-05-30T00:02:00+00:00"


def test_ledger_save_load_roundtrip(tmp_path):
    led = GateLedger()
    led.record(Gate.G5_METRICS, {"choice": "confirm", "metrics": ["40%"]}, "T1")
    p = led.save(tmp_path / "run_ledger.json")
    raw = json.loads(p.read_text())
    assert raw["decisions"][0]["gate"] == "G5"
    led2 = GateLedger.load(p)
    assert led2.get(Gate.G5_METRICS).decision["metrics"] == ["40%"]


def test_ledger_load_missing_is_empty(tmp_path):
    led = GateLedger.load(tmp_path / "nope.json")
    assert led.decisions == []


# ---- resume_plan -----------------------------------------------------------


def test_resume_plan_unknown_gate_is_own_blast_radius():
    led = GateLedger()  # empty
    assert resume_plan(led, Gate.G5_METRICS) == [Stage.RENDER, Stage.REVIEW]


def test_resume_plan_unions_downstream_recorded_gates():
    """Re-deciding upstream G2 must also honor a later-recorded G5's invalidation;
    union is re-projected onto canonical order."""
    led = GateLedger()
    led.record(Gate.G2_GROUPING, {"choice": "merge"}, "T1")
    led.record(Gate.G5_METRICS, {"choice": "confirm"}, "T2")
    plan = resume_plan(led, Gate.G2_GROUPING)
    # G2 -> aggregate,enrich,metrics,render,review ; G5 -> render,review ; union, ordered
    assert plan == [
        Stage.AGGREGATE, Stage.ENRICH, Stage.METRICS, Stage.RENDER, Stage.REVIEW
    ]


def test_resume_plan_ignores_strictly_upstream_gates():
    """Changing G5 (later gate) must not pull in an earlier G2's wider radius."""
    led = GateLedger()
    led.record(Gate.G2_GROUPING, {"choice": "merge"}, "T1")
    led.record(Gate.G5_METRICS, {"choice": "confirm"}, "T2")
    plan = resume_plan(led, Gate.G5_METRICS)
    assert plan == [Stage.RENDER, Stage.REVIEW]
    assert Stage.ENRICH not in plan


def test_resume_plan_from_g1_is_everything():
    led = GateLedger()
    led.record(Gate.G1_FRESHNESS, {"choice": "reextract"}, "T1")
    led.record(Gate.G4_BULLETS, {"choice": "edit"}, "T2")
    assert resume_plan(led, Gate.G1_FRESHNESS) == list(CANONICAL_ORDER)


# ---- gate file emit / read -------------------------------------------------


def test_emit_gate_writes_pending_with_context_and_choices(tmp_path):
    p = emit_gate(Gate.G5_METRICS, tmp_path, context={"candidates": [{"value": "40%", "safe_to_surface": True}]})
    assert p == gate_file_path(tmp_path, Gate.G5_METRICS)
    data = json.loads(p.read_text())
    assert data["gate"] == "G5"
    assert data["status"] == "pending"
    # #72 self-documenting scaffold; #79 part 2 adds an empty `pick` for G5.
    assert data["decision"] == {"choice": None, "pick": []}
    assert "_hint" in data and "decision.choice" in data["_hint"]
    assert data["choices"] == list(GATE_DEFS[Gate.G5_METRICS].choices)
    assert data["context"]["candidates"][0]["value"] == "40%"


def test_emit_gate_does_not_clobber_decided(tmp_path):
    p = emit_gate(Gate.G2_GROUPING, tmp_path)
    gf = GateFile.from_dict(json.loads(p.read_text()))
    gf.decision = {"choice": "merge"}
    gf.status = "decided"
    p.write_text(json.dumps(gf.as_dict()))
    # re-emit must leave the decided file intact
    emit_gate(Gate.G2_GROUPING, tmp_path, context={"new": "ctx"})
    reread = json.loads(p.read_text())
    assert reread["decision"] == {"choice": "merge"}
    assert "new" not in reread["context"]


def test_read_gate_decision_happy_path(tmp_path):
    p = emit_gate(Gate.G1_FRESHNESS, tmp_path)
    gf = GateFile.from_dict(json.loads(p.read_text()))
    gf.decision = {"choice": "reuse"}
    gf.status = "decided"
    p.write_text(json.dumps(gf.as_dict()))
    out, warnings = read_gate_decision(p)
    assert out.decision == {"choice": "reuse"}
    assert warnings == []


def test_read_gate_decision_missing_file_warns_not_raises(tmp_path):
    out, warnings = read_gate_decision(gate_file_path(tmp_path, Gate.G3_OVERWRITE))
    assert out.decision is None
    assert any("missing" in w for w in warnings)


def test_read_gate_decision_invalid_choice_warns_but_returns(tmp_path):
    p = emit_gate(Gate.G1_FRESHNESS, tmp_path)
    gf = GateFile.from_dict(json.loads(p.read_text()))
    gf.decision = {"choice": "nonsense"}
    p.write_text(json.dumps(gf.as_dict()))
    out, warnings = read_gate_decision(p)
    assert out.decision == {"choice": "nonsense"}
    assert any("not in offered" in w for w in warnings)


def test_read_gate_decision_undecided_warns(tmp_path):
    p = emit_gate(Gate.G6_REDACTION, tmp_path)
    out, warnings = read_gate_decision(p)
    # #72: pending scaffold is {"choice": None} (still undecided — null choice)
    assert out.decision == {"choice": None}
    assert not (out.decision or {}).get("choice")
    assert any("no decision" in w for w in warnings)


def test_read_gate_decision_bare_string_accepted(tmp_path):
    # #72: the obvious fill (bare string) is normalized instead of dropped to None
    p = emit_gate(Gate.G1_FRESHNESS, tmp_path)
    data = json.loads(p.read_text())
    data["decision"] = "reuse"
    p.write_text(json.dumps(data))
    out, warnings = read_gate_decision(p)
    assert out.decision == {"choice": "reuse"}
    assert not any("no decision" in w for w in warnings)


def test_read_gate_decision_wrong_shape_message(tmp_path):
    # #72: a non-null wrong-shape decision says HOW to fix it, not "no decision"
    p = emit_gate(Gate.G1_FRESHNESS, tmp_path)
    data = json.loads(p.read_text())
    data["decision"] = ["reuse"]   # list, not an object/string
    p.write_text(json.dumps(data))
    out, warnings = read_gate_decision(p)
    assert out.decision is None
    joined = " ".join(warnings)
    assert "must be an object" in joined and "no decision filled in" not in joined


# ---- G5 P1 fabrication guard (#70 item 6) ----------------------------------


def test_emit_g5_raises_on_unsafe_candidate_metric(tmp_path):
    import pytest

    ctx = {"groups": [{"candidate_metrics": [
        {"value": "40%", "safe_to_surface": True},
        {"value": "max-width: 600px", "safe_to_surface": False},
    ]}]}
    with pytest.raises(ValueError, match="non-safe_to_surface"):
        emit_gate(Gate.G5_METRICS, tmp_path, context=ctx)
    # nothing written
    assert not gate_file_path(tmp_path, Gate.G5_METRICS).exists()


def test_emit_g5_succeeds_with_only_safe_candidates(tmp_path):
    ctx = {"groups": [{"candidate_metrics": [
        {"value": "40%", "safe_to_surface": True},
        {"value": "3x", "safe_to_surface": True},
    ]}],
        "candidate_metrics": [{"value": "2k", "safe_to_surface": True}]}
    p = emit_gate(Gate.G5_METRICS, tmp_path, context=ctx)
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["gate"] == "G5"
    assert data["status"] == "pending"
    assert g5_safe_metric_values(ctx) == {"40%", "3x", "2k"}


def test_g5_emit_scaffolds_pick_list(tmp_path):
    """#79 part 2: a G5 gate scaffolds an empty `pick` so the filler can select
    per-metric (empty pick + confirm == weave all safe, the conservative legacy)."""
    ctx = {"groups": [{"candidate_metrics": [{"value": "40%", "safe_to_surface": True}]}]}
    p = emit_gate(Gate.G5_METRICS, tmp_path, context=ctx)
    data = json.loads(p.read_text())
    assert data["decision"] == {"choice": None, "pick": []}


def test_g5_selected_metrics_per_metric_pick():
    """#79 part 2: the G5 decision can record which candidates to weave."""
    from vibe_resume.core.gates import g5_selected_metrics
    ctx = {"groups": [{"candidate_metrics": [
        {"value": "2.0x→1.5x", "safe_to_surface": True},
        {"value": "7s", "safe_to_surface": True},
        {"value": "40%", "safe_to_surface": True},
    ]}]}
    # skip / undecided → conservative empty
    assert g5_selected_metrics({"choice": "skip"}, ctx) == set()
    assert g5_selected_metrics(None, ctx) == set()
    # confirm without pick → all safe (legacy all-or-nothing)
    assert g5_selected_metrics({"choice": "confirm"}, ctx) == {"2.0x→1.5x", "7s", "40%"}
    # confirm WITH pick → only the chosen subset
    picked = {"choice": "confirm", "pick": [{"group": "CRM", "value": "2.0x→1.5x"}]}
    assert g5_selected_metrics(picked, ctx) == {"2.0x→1.5x"}


def test_g5_selected_metrics_pick_cannot_smuggle_unsafe_value():
    """P1: even an explicit pick is intersected with safe values — a pick of an
    unsafe/unlisted value can never be woven."""
    from vibe_resume.core.gates import g5_selected_metrics
    ctx = {"groups": [{"candidate_metrics": [
        {"value": "40%", "safe_to_surface": True},
        {"value": "487B", "safe_to_surface": False},   # secret fragment (#79 part1)
    ]}]}
    picked = {"choice": "confirm", "pick": [
        {"value": "40%"}, {"value": "487B"}, {"value": "99%"},  # unsafe + unlisted dropped
    ]}
    assert g5_selected_metrics(picked, ctx) == {"40%"}


def test_non_g5_emit_unaffected_by_unsafe_looking_context(tmp_path):
    # A G6 gate with the same unsafe-looking metric context must NOT raise.
    ctx = {"candidate_metrics": [{"value": "css-leak", "safe_to_surface": False}]}
    p = emit_gate(Gate.G6_REDACTION, tmp_path, context=ctx)
    assert p.exists()
    assert json.loads(p.read_text())["gate"] == "G6"


# ---- determinism (#70 item 1: no clock / no RNG in the core) ----------------


def test_module_source_has_no_clock_or_rng():
    """The core must be pure: every nondeterministic input is a parameter (#70)."""
    from pathlib import Path

    import vibe_resume.core.gates as gates_mod

    src = Path(gates_mod.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in src
    assert "time(" not in src
    assert "import random" not in src and "random." not in src


# --- #70 CLI surface (gates show / plan) ------------------------------------

def test_cli_gates_show():
    from click.testing import CliRunner

    from vibe_resume.cli import cli
    r = CliRunner().invoke(cli, ["gates", "show"])
    assert r.exit_code == 0, r.output
    assert "G1" in r.output and "G8" in r.output
    assert "checkpoints" in r.output and "autopilot" in r.output


def test_cli_gates_plan_single_and_terminal():
    from click.testing import CliRunner

    from vibe_resume.cli import cli
    r = CliRunner().invoke(cli, ["gates", "plan", "--changed", "G5"])
    assert r.exit_code == 0, r.output
    assert "render" in r.output and "review" in r.output and "enrich" not in r.output.split("recompute:")[1]
    # G8 is terminal
    r2 = CliRunner().invoke(cli, ["gates", "plan", "--changed", "G8"])
    assert r2.exit_code == 0 and "terminal" in r2.output.lower()
    # unknown gate → usage error
    r3 = CliRunner().invoke(cli, ["gates", "plan", "--changed", "ZZ"])
    assert r3.exit_code != 0
