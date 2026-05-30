"""Run-level orchestration glue for Interactive Gate Mode (#71).

Phase 2 of the gate feature: this module CONSUMES the pure gate core
(``core/gates.py``, shipped + tested in #70) and turns it into a ledger-driven
multi-stop state machine for the ``run`` command. It owns three small concerns:

1. Resolving the ACTIVE gate set from the ``run`` flags
   (``--interactive`` / ``--preset`` / ``--gates``).
2. The gate -> pipeline-stage GUARD map (where in CANONICAL_ORDER a gate pauses),
   and ``first_pending_gate`` — the ledger query that tells ``run`` where to
   resume (the first ACTIVE gate that still has no recorded decision).
3. Building the decision-support ``context`` for each gate's emit. G5's context
   is fed from ``core/evidence.disclose_all`` and contains ONLY
   ``safe_to_surface`` metrics, so the core's ``assert_g5_safe`` (called inside
   ``emit_gate``) holds — the P1 fabrication guard is never bypassed.

It deliberately stays clock-free where the core does: the CLI passes the
timestamp in. Heavy pipeline work (extract/aggregate/enrich/render/review) stays
in ``core/runner.py`` + ``core/review.py``; this module only sequences it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe_resume.core.gates import (
    GATE_DEFS,
    PRESETS,
    Gate,
    GateLedger,
    preset_gates,
)

#: Default preset selected by a bare ``run --interactive`` (no explicit set).
DEFAULT_INTERACTIVE_PRESET = "checkpoints"

#: run_ledger.json lives under the user's data/ dir (sibling of cache/).
LEDGER_NAME = "run_ledger.json"

# ---- gate -> pipeline-stage guard map --------------------------------------
#
# WHERE a gate pauses, expressed as the run-phase it guards. This is distinct
# from ``core/gates.INVALIDATION`` (which says what RECOMPUTES when a *recorded*
# gate is re-decided). A guard is the forward-direction "stop before this stage
# the first time through" position.
#
#   G1 freshness  -> guards extract+aggregate (reextract vs reuse)
#   G2 grouping   -> guards aggregate/enrich  (top_n / drop_noise)
#   G4 bullets    -> the EXISTING enrich emit/process/continue checkpoint
#   G5 metrics    -> guards render (context = safe_to_surface metrics)
#   G6 redaction  -> guards render
#   G7 variants   -> guards render
#   G8 acceptance -> after review (terminal: accept / iterate / stop)
#
# G3 (overwrite) has no run-phase guard in the MVP matrix flow; it is emit-only
# if ever armed and never pauses the matrix.

GUARD_PHASE: dict[Gate, str] = {
    Gate.G1_FRESHNESS: "freshness",
    Gate.G2_GROUPING: "grouping",
    Gate.G4_BULLETS: "bullets",
    Gate.G5_METRICS: "render",
    Gate.G6_REDACTION: "render",
    Gate.G7_VARIANTS: "render",
    Gate.G8_ACCEPTANCE: "acceptance",
}

#: The order gates open during a forward run (== gate enum order, G1..G8). The
#: state machine pauses at the FIRST active gate in this order without a decision.
GATE_RUN_ORDER: tuple[Gate, ...] = tuple(Gate)

#: Which gates the #71 MVP fully wires end-to-end (apply semantics) vs emit-only.
#: G1/G2/G8 (the ``checkpoints`` preset) are fully wired; the rest emit + record
#: their decision but apply only the documented light semantics. G5's emit stays
#: guarded by ``assert_g5_safe`` regardless (core invariant).
FULLY_WIRED: frozenset[Gate] = frozenset(
    {Gate.G1_FRESHNESS, Gate.G2_GROUPING, Gate.G8_ACCEPTANCE}
)


def ledger_path(data_dir: Path) -> Path:
    """Deterministic path for the run ledger under the user's data/ dir."""
    return data_dir / LEDGER_NAME


def gate_dir(data_dir: Path) -> Path:
    """Where ``*.gate.json`` pause files are emitted (data/gates/)."""
    return data_dir / "gates"


def resolve_active_gates(
    *,
    interactive: bool,
    preset: str | None,
    gates: str | None,
) -> list[Gate]:
    """Resolve the ACTIVE gate set from the run flags (#71).

    Precedence: explicit ``--gates`` > ``--preset`` > ``--interactive`` default.
    A bare ``--interactive`` with no explicit set resolves to the
    ``checkpoints`` preset (G1, G2, G8). Returns ``[]`` when no gate flag is
    present (autopilot — current behavior, no ledger, no pauses).

    Raises ``ValueError`` on an unknown preset name or gate id so the CLI can map
    it to a UsageError.
    """
    if gates:
        out: list[Gate] = []
        for tok in gates.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                out.append(Gate(tok.upper()))
            except ValueError as e:
                raise ValueError(
                    f"unknown gate {tok!r}; use one of {', '.join(g.value for g in Gate)}"
                ) from e
        # de-dup preserving order
        seen: set[Gate] = set()
        deduped = [g for g in out if not (g in seen or seen.add(g))]
        return deduped
    if preset:
        if preset not in PRESETS:
            raise ValueError(
                f"unknown preset {preset!r}; use one of {', '.join(PRESETS)}"
            )
        return preset_gates(preset)
    if interactive:
        return preset_gates(DEFAULT_INTERACTIVE_PRESET)
    return []


def active_gates_from_ledger(ledger: GateLedger) -> list[Gate]:
    """Recover the armed gate set persisted in the ledger's active-set marker.

    Stored as a pseudo-decision under the ``active_set`` key (a string the core
    never interprets), so a ``--continue`` invocation need not re-pass flags.
    Returns ``[]`` if no marker was recorded.
    """
    raw = None
    # The marker is stashed under a reserved ``__active_set__`` key on a real
    # decision row, keeping the core ledger schema (one row per Gate) clean.
    for d in ledger.decisions:
        if d.decision.get("__active_set__"):
            raw = d.decision["__active_set__"]
            break
    if not raw:
        return []
    out: list[Gate] = []
    for tok in raw:
        try:
            out.append(Gate(tok))
        except ValueError:
            continue
    return out


def record_active_set(ledger: GateLedger, active: list[Gate], timestamp: str) -> None:
    """Persist the armed gate set into the ledger (idempotent marker row).

    Uses G1's slot is avoided — instead we stash the set on whichever gate the
    set first contains, under a reserved ``__active_set__`` key that is ignored
    by ``resume_plan``/``invalidated_stages``. If the set is empty nothing is
    recorded.
    """
    if not active:
        return
    marker_gate = active[0]
    existing = ledger.get(marker_gate)
    decision = dict(existing.decision) if existing else {}
    decision["__active_set__"] = [g.value for g in active]
    ledger.record(marker_gate, decision, timestamp)


def first_pending_gate(active: list[Gate], ledger: GateLedger) -> Gate | None:
    """First ACTIVE gate (in run order) without a real decision yet (#71).

    A gate counts as decided once its ledger record carries a ``choice`` (the
    ``__active_set__`` marker alone does NOT count as a decision). Returns
    ``None`` when every active gate has been decided — the run can finish.
    """
    armed = [g for g in GATE_RUN_ORDER if g in set(active)]
    for g in armed:
        rec = ledger.get(g)
        if rec is None or not rec.decision.get("choice"):
            return g
    return None


def build_gate_context(
    gate: Gate,
    *,
    cfg: dict[str, Any],
    locale: str | None = None,
    persona: str | None = None,
    score: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decision-support ``context`` for a gate's emit (#71).

    G5's context is sourced from ``core/evidence.disclose_all`` and filtered to
    ONLY ``safe_to_surface`` metrics, satisfying the core's ``assert_g5_safe``
    P1 guard (which ``emit_gate`` enforces before writing). Other gates get a
    lightweight, honest context. Never invents data: an empty source yields an
    empty context.
    """
    d = GATE_DEFS[gate]
    base: dict[str, Any] = {"gate": gate.value, "short": d.short}

    if gate is Gate.G5_METRICS:
        # P1: surface ONLY disclosed, safe_to_surface real metrics — never invent.
        from vibe_resume.core.aggregator import load_groups
        from vibe_resume.core.evidence import disclose_all
        from vibe_resume.render.i18n import get_locale

        lang = get_locale(locale or cfg.get("render", {}).get("locale")).get("language")
        groups = load_groups(persona=persona, locale=locale)
        evs = disclose_all(groups, lang=lang)
        out_groups: list[dict[str, Any]] = []
        for e in evs:
            safe = [
                m.as_dict() for m in e.candidate_metrics if m.safe_to_surface
            ]
            if safe:
                out_groups.append({"group": e.group, "candidate_metrics": safe})
        base["groups"] = out_groups
        return base

    if gate is Gate.G8_ACCEPTANCE:
        base["score"] = score or {}
        return base

    # G1/G2/G4/G6/G7 — light context.
    base["locale"] = locale
    base["persona"] = persona
    return base
