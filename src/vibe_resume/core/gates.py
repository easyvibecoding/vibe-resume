"""Interactive gate-mode core for the run pipeline (#70).

Robustness-first, *pure* core for an 8-gate human-in-the-loop run mode. It owns
three concerns and nothing else (no I/O beyond JSON file read/write, no wall
clock, no RNG — every nondeterministic input is passed in):

1. Gate definitions (G1..G8) + presets (autopilot / checkpoints / full_review).
2. The gate -> downstream-stage INVALIDATION graph and the function that turns a
   changed gate into the *ordered recompute suffix* over the canonical pipeline
   stages {extract, aggregate, enrich, metrics, render, review}. Correctness of
   this suffix is the priority: invalidation is always expressed as a *start
   stage* and the suffix is sliced from the single canonical order, so a recompute
   set can never be out of order or skip an intermediate stage.
3. A Gate Ledger (run_ledger.json): one record per gate decision (timestamp is a
   PARAMETER), save/load to JSON, and ``resume_plan`` which replays the ledger to
   compute what to recompute when a recorded gate's decision changes.

Plus gate-file emit/read helpers that mirror the enrich emit/continue manifest
pattern (``core/enrich_jobs.py``): ``emit_gate`` writes a ``*.gate.json`` with the
decision context + offered choices; ``read_gate_decision`` reads the filled-in
decision back. JSON-based, deterministic.

ALIGNMENT (docs/PRINCIPLES.md P1): the review score is a proxy; gates must NEVER
enable fabrication. The metrics gate (G5) only ever carries evidence-disclosed
real metrics (``safe_to_surface`` from ``core/evidence.py``), never invented
numbers. This is a CORE invariant, not merely a caller convention:
:func:`emit_gate` calls :func:`assert_g5_safe` before writing a G5 gate file and
raises :class:`ValueError` on any non-``safe_to_surface`` candidate metric, so an
unsafe/invented metric can never reach the gate — satisfying P1's "at least one
test asserting the guardrail."

NOTE (deliberate deviation): this module uses stdlib ``dataclasses`` (matching
``core/evidence.py`` / ``core/iterate.py``), NOT pydantic as in
``core/enrich_jobs.py`` — a documented choice to stay dependency-light. Per-gate
payload validation beyond the G5 P1 guard is the orchestrator's job (minimal
surface). The module reads no wall clock and no RNG: every nondeterministic input
(notably the ledger ``timestamp``) is passed in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Stage(str, Enum):
    """Canonical pipeline stages an invalidation can target (#70).

    The string values are the stage names the run CLI dispatches on. Order
    matters: ``CANONICAL_ORDER`` below is the single source of truth for the
    recompute-suffix slice."""

    EXTRACT = "extract"
    AGGREGATE = "aggregate"
    ENRICH = "enrich"
    METRICS = "metrics"
    RENDER = "render"
    REVIEW = "review"


#: The one canonical pipeline order. A recompute set is ALWAYS a contiguous
#: suffix of this list (optionally minus stages a gate explicitly keeps), so the
#: result can never be mis-ordered or skip an intermediate stage (#70).
CANONICAL_ORDER: tuple[Stage, ...] = (
    Stage.EXTRACT,
    Stage.AGGREGATE,
    Stage.ENRICH,
    Stage.METRICS,
    Stage.RENDER,
    Stage.REVIEW,
)


class Gate(str, Enum):
    """The 8 interactive gates (#70). Value = stable id used in the ledger/files."""

    G1_FRESHNESS = "G1"
    G2_GROUPING = "G2"
    G3_OVERWRITE = "G3"
    G4_BULLETS = "G4"
    G5_METRICS = "G5"
    G6_REDACTION = "G6"
    G7_VARIANTS = "G7"
    G8_ACCEPTANCE = "G8"


@dataclass(frozen=True)
class GateDef:
    """Static definition of a gate: id, short name, human description, and the
    choice keys the gate offers (the values a filled decision may set)."""

    gate: Gate
    short: str
    description: str
    choices: tuple[str, ...]


GATE_DEFS: dict[Gate, GateDef] = {
    Gate.G1_FRESHNESS: GateDef(
        Gate.G1_FRESHNESS, "freshness",
        "Re-extract from sources vs reuse the cached extract.",
        ("reextract", "reuse"),
    ),
    Gate.G2_GROUPING: GateDef(
        Gate.G2_GROUPING, "grouping",
        "Adjust grouping: top-N, merge groups, or drop-noise.",
        ("top_n", "merge", "drop_noise", "accept"),
    ),
    Gate.G3_OVERWRITE: GateDef(
        Gate.G3_OVERWRITE, "overwrite",
        "Profile ingest mode: clean overwrite vs re-merge into existing yaml.",
        ("clean", "remerge"),
    ),
    Gate.G4_BULLETS: GateDef(
        Gate.G4_BULLETS, "bullets",
        "Per-group bullets before ingest: approve / regenerate / edit.",
        ("approve", "regenerate", "edit"),
    ),
    Gate.G5_METRICS: GateDef(
        Gate.G5_METRICS, "metrics",
        "Confirm evidence-surfaced real numbers before weaving (P1: only "
        "safe_to_surface disclosed metrics; never invents).",
        ("confirm", "skip"),
    ),
    Gate.G6_REDACTION: GateDef(
        Gate.G6_REDACTION, "redaction",
        "Review the scrub list before render.",
        ("accept", "edit"),
    ),
    Gate.G7_VARIANTS: GateDef(
        Gate.G7_VARIANTS, "variants",
        "Choose variants / formats / page budget.",
        ("accept", "edit"),
    ),
    Gate.G8_ACCEPTANCE: GateDef(
        Gate.G8_ACCEPTANCE, "acceptance",
        "After review: accept / iterate / stop (terminal).",
        ("accept", "iterate", "stop"),
    ),
}


# ---- presets ---------------------------------------------------------------

PRESETS: dict[str, list[Gate]] = {
    "autopilot": [],
    "checkpoints": [Gate.G1_FRESHNESS, Gate.G2_GROUPING, Gate.G8_ACCEPTANCE],
    "full_review": list(Gate),
}


def preset_gates(preset: str) -> list[Gate]:
    """Resolve a preset name to its gate list. Raises KeyError on unknown name."""
    return list(PRESETS[preset])


# ---- invalidation graph ----------------------------------------------------

# A gate's blast radius is expressed as: the canonical stage the recompute SUFFIX
# starts at, minus any stages the gate explicitly KEEPS. Expressing it as a
# start-stage (never an ad-hoc set) is what guarantees the recompute list is a
# well-ordered contiguous suffix of CANONICAL_ORDER (#70).
#
# ``terminal`` gates produce no recompute (G8 stop/iterate is handled by the
# orchestrator, not by recomputing a stage suffix).


@dataclass(frozen=True)
class Invalidation:
    """How a gate's decision change propagates downstream (#70).

    ``start`` is the earliest canonical stage that must recompute; ``keep`` are
    stages at/after ``start`` that this gate leaves intact (e.g. G4 keeps ENRICH
    for groups it didn't touch). ``terminal`` gates recompute nothing here."""

    start: Stage | None = None
    keep: frozenset[Stage] = frozenset()
    terminal: bool = False
    note: str = ""


INVALIDATION: dict[Gate, Invalidation] = {
    # G1 freshness -> everything (the whole pipeline from extract on).
    Gate.G1_FRESHNESS: Invalidation(start=Stage.EXTRACT, note="freshness re-extracts all"),
    # G2 grouping -> aggregate,enrich,metrics,render,review (keep extract). Per the
    # #38 curate-gate spec the grouping/merge decision rewrites the AGGREGATE output
    # (_project_groups.json canonical_key/merged_from/merge_evidence), so the
    # recompute suffix must begin at AGGREGATE — extract is still kept (#70 item 7).
    Gate.G2_GROUPING: Invalidation(
        start=Stage.AGGREGATE, note="grouping change re-derives aggregate; keep extract"),
    # G3 overwrite -> profile ingest mode feeds render; enrich/metrics intact.
    # (Inferred — #70 invalidation list omits G3; mapped to the render suffix.)
    Gate.G3_OVERWRITE: Invalidation(start=Stage.RENDER, note="profile ingest mode; keep enrich+metrics"),
    # G4 bullets -> (changed groups') metrics,render,review (keep OTHER enrich).
    # Group-scoped: ENRICH is kept wholesale here; the per-group recompute of the
    # changed groups is the caller's job (regenerate/edit re-runs enrich for those
    # ids), so the *stage suffix* starts at METRICS.
    Gate.G4_BULLETS: Invalidation(
        start=Stage.METRICS, keep=frozenset({Stage.ENRICH}),
        note="bullets: keep unchanged-group enrich; recompute metrics->review",
    ),
    # G5 metrics -> render,review (keep enrich).
    Gate.G5_METRICS: Invalidation(
        start=Stage.RENDER, keep=frozenset({Stage.ENRICH, Stage.METRICS}),
        note="metric confirm reweaves render; keep enrich+metrics",
    ),
    # G6 redaction -> render,review (keep enrich,metrics).
    Gate.G6_REDACTION: Invalidation(
        start=Stage.RENDER, keep=frozenset({Stage.ENRICH, Stage.METRICS}),
        note="scrub list reweaves render; keep enrich+metrics",
    ),
    # G7 variants -> render,review (keep enrich,metrics).
    Gate.G7_VARIANTS: Invalidation(
        start=Stage.RENDER, keep=frozenset({Stage.ENRICH, Stage.METRICS}),
        note="variant/format/budget reweaves render; keep enrich+metrics",
    ),
    # G8 acceptance -> terminal.
    Gate.G8_ACCEPTANCE: Invalidation(terminal=True, note="accept/iterate/stop — terminal"),
}


def invalidated_stages(gate: Gate) -> list[Stage]:
    """Ordered stages to recompute when ``gate``'s decision changes (#70).

    Returns the contiguous suffix of ``CANONICAL_ORDER`` starting at the gate's
    invalidation ``start``, minus any stages the gate explicitly keeps. Terminal
    gates (G8) return ``[]``. The result is ALWAYS in canonical order because it
    is sliced from the single canonical order — never assembled ad hoc."""
    inv = INVALIDATION[gate]
    if inv.terminal or inv.start is None:
        return []
    start_i = CANONICAL_ORDER.index(inv.start)
    return [s for s in CANONICAL_ORDER[start_i:] if s not in inv.keep]


# ---- gate ledger -----------------------------------------------------------


@dataclass
class GateDecision:
    """One recorded gate decision (#70).

    ``decision`` is the free-form filled choice (e.g. ``{"choice": "merge",
    "targets": [...]}``). ``timestamp`` is supplied by the caller as an ISO-8601
    string — this module NEVER reads the wall clock (testability + determinism)."""

    gate: Gate
    decision: dict[str, Any]
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return {"gate": self.gate.value, "decision": self.decision, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GateDecision:
        return cls(gate=Gate(d["gate"]), decision=dict(d.get("decision") or {}),
                   timestamp=str(d.get("timestamp", "")))


@dataclass
class GateLedger:
    """Append-only record of gate decisions making a run replayable (#70).

    ``record`` keeps the latest decision per gate (re-deciding a gate updates in
    place, preserving first-seen order) so ``resume_plan`` operates on a clean
    one-row-per-gate view."""

    version: int = 1
    decisions: list[GateDecision] = field(default_factory=list)

    def record(self, gate: Gate, decision: dict[str, Any], timestamp: str) -> GateDecision:
        """Record (or overwrite) the decision for ``gate``. Returns the record."""
        rec = GateDecision(gate=gate, decision=dict(decision), timestamp=timestamp)
        for i, existing in enumerate(self.decisions):
            if existing.gate is gate:
                self.decisions[i] = rec
                return rec
        self.decisions.append(rec)
        return rec

    def get(self, gate: Gate) -> GateDecision | None:
        for d in self.decisions:
            if d.gate is gate:
                return d
        return None

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.version, "decisions": [d.as_dict() for d in self.decisions]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GateLedger:
        return cls(version=int(d.get("version", 1)),
                   decisions=[GateDecision.from_dict(x) for x in d.get("decisions", [])])

    def save(self, path: Path) -> Path:
        """Write the ledger to ``path`` as pretty JSON (run_ledger.json)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> GateLedger:
        """Load a ledger from ``path``; an absent file yields an empty ledger."""
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def resume_plan(ledger: GateLedger, changed_gate: Gate) -> list[Stage]:
    """Stages to recompute to resume a run after ``changed_gate`` is re-decided.

    The blast radius of the changed gate is its own ``invalidated_stages`` UNIONED
    with the blast radius of every *later-or-equal* gate recorded in the ledger:
    re-deciding an upstream gate (e.g. G2 grouping) necessarily re-opens the gates
    downstream of it, whose own invalidations must also be honored. The union is
    re-projected onto ``CANONICAL_ORDER`` so the returned plan is always correctly
    ordered (#70). Terminal gates (G8) contribute nothing.

    If ``changed_gate`` is not in the ledger, the plan is just that gate's own
    ``invalidated_stages`` (nothing downstream was recorded yet)."""
    affected: set[Stage] = set(invalidated_stages(changed_gate))

    changed_pos = _gate_order_index(changed_gate)
    for d in ledger.decisions:
        if _gate_order_index(d.gate) >= changed_pos:
            affected.update(invalidated_stages(d.gate))

    return [s for s in CANONICAL_ORDER if s in affected]


# Stable gate ordering used for "later-or-equal" comparison in resume_plan. This
# is gate ENUM declaration order (G1..G8), which is also the order gates open in
# a run — independent of the stage they invalidate.
_GATE_SEQUENCE: tuple[Gate, ...] = tuple(Gate)


def _gate_order_index(gate: Gate) -> int:
    return _GATE_SEQUENCE.index(gate)


# ---- gate-file emit / read (mirrors enrich emit/continue manifest) ---------


@dataclass
class GateFile:
    """The on-disk ``*.gate.json`` payload (#70), mirroring the enrich manifest.

    ``context`` carries decision-support data fed by the #62-#69 disclosure layer
    (kind/confidence/safe_to_surface/provenance) so the human/agent decides on
    real signals. ``choices`` are the offered options; ``decision`` is filled in
    by the session and read back by :func:`read_gate_decision`."""

    gate: Gate
    short: str
    description: str
    choices: list[str]
    context: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] | None = None
    status: str = "pending"          # "pending" | "decided"
    version: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "gate": self.gate.value,
            "short": self.short,
            "description": self.description,
            "choices": list(self.choices),
            "context": self.context,
            # #72: the decision is an object — make its shape self-documenting so a
            # filler doesn't guess. A bare string is also accepted (normalized).
            "_hint": "set `decision.choice` to one of `choices` (a bare string is also accepted)",
            "decision": self.decision,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GateFile:
        return cls(
            gate=Gate(d["gate"]),
            short=str(d.get("short", "")),
            description=str(d.get("description", "")),
            choices=list(d.get("choices", [])),
            context=dict(d.get("context") or {}),
            decision=cls._coerce_decision(d.get("decision")),
            status=str(d.get("status", "pending")),
            version=int(d.get("version", 1)),
        )

    @staticmethod
    def _coerce_decision(raw: Any) -> dict[str, Any] | None:
        """Normalize a filled decision to the ``{"choice": ...}`` object shape (#72).

        Accepts the canonical object as-is, and — forgivingly — a **bare string**
        shorthand (``"reuse"`` -> ``{"choice": "reuse"}``) so the obvious fill
        works instead of being silently dropped to ``None``. Anything else
        (list/number/empty) -> ``None`` (genuinely undecided)."""
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str) and raw.strip():
            return {"choice": raw.strip()}
        return None


def gate_file_path(out_dir: Path, gate: Gate) -> Path:
    """Deterministic path for a gate file: ``<out_dir>/<gate-id>.gate.json``."""
    return out_dir / f"{gate.value}.gate.json"


# ---- G5 fabrication guard (PRINCIPLES.md P1, turned into a core invariant) --


def g5_safe_metric_values(context: dict[str, Any]) -> set[str]:
    """Literal metric values the G5 context is allowed to offer (#70).

    Every ``candidate_metric`` whose ``safe_to_surface`` is True (the
    ``core/evidence.py`` :class:`MetricCandidate` shape — keys ``value`` /
    ``safe_to_surface``). Reads ONLY from the passed context; computes nothing.
    Accepts both the per-group shape (``context["groups"][*]["candidate_metrics"]``)
    and a flat ``context["candidate_metrics"]`` shape."""
    out: set[str] = set()
    for grp in context.get("groups", []) or []:
        for m in grp.get("candidate_metrics", []) or []:
            if m.get("safe_to_surface"):
                out.add(str(m.get("value")))
    for m in context.get("candidate_metrics", []) or []:
        if m.get("safe_to_surface"):
            out.add(str(m.get("value")))
    return out


def assert_g5_safe(context: dict[str, Any]) -> None:
    """P1 guard: a G5 gate context may surface ONLY ``safe_to_surface`` real
    metrics from the evidence disclosure layer (#70).

    Raises :class:`ValueError` if ANY ``candidate_metric`` present in the context
    is not ``safe_to_surface`` (i.e. a UI threshold / css / model-spec /
    url-fragment / unsafe value leaked into the gate). Pure: no clock, no I/O."""
    bad: list[str] = []

    def _scan(metrics: list[dict[str, Any]] | None) -> None:
        for m in metrics or []:
            if not m.get("safe_to_surface"):
                bad.append(str(m.get("value")))

    for grp in context.get("groups", []) or []:
        _scan(grp.get("candidate_metrics"))
    _scan(context.get("candidate_metrics"))
    if bad:
        raise ValueError(
            f"G5 gate context offers non-safe_to_surface metrics {bad}; "
            "P1 forbids surfacing them."
        )


def emit_gate(
    gate: Gate,
    out_dir: Path,
    *,
    context: dict[str, Any] | None = None,
) -> Path:
    """Write a pending ``*.gate.json`` for ``gate`` with its choices + context.

    Re-emit semantics (like enrich emit): if a *decided* file already exists it is
    left untouched so a partially-completed run isn't clobbered; a pending file is
    refreshed with the latest context.

    P1 invariant (PRINCIPLES.md): emitting the G5 metrics gate calls
    :func:`assert_g5_safe` BEFORE writing, so a G5 gate file can NEVER be emitted
    listing an unsafe/invented metric — the fabrication guardrail lives in the
    core, not only at the CLI seam. Raises :class:`ValueError` on a non-safe
    metric in the G5 context."""
    if gate is Gate.G5_METRICS:
        assert_g5_safe(context or {})
    out_dir.mkdir(parents=True, exist_ok=True)
    path = gate_file_path(out_dir, gate)
    if path.exists():
        try:
            prior = GateFile.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if prior.status == "decided":
                return path
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # unreadable -> overwrite fresh

    d = GATE_DEFS[gate]
    gf = GateFile(
        gate=gate, short=d.short, description=d.description,
        choices=list(d.choices), context=dict(context or {}),
        # #72: scaffold the decision SHAPE (not a bare null) so the filler sees
        # exactly what to set. A null choice still reads as "not yet decided".
        decision={"choice": None},
    )
    path.write_text(json.dumps(gf.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_gate_decision(path: Path) -> tuple[GateFile, list[str]]:
    """Read a filled-in gate file back. Returns ``(gate_file, warnings)``.

    Never raises on a malformed/undecided file — problems become warnings and the
    returned ``GateFile.decision`` stays ``None`` so the caller can fall back
    (mirrors ``ingest_jobs`` tolerance). A decision whose ``choice`` is not among
    the offered ``choices`` is surfaced as a warning but still returned, so the
    caller decides how strict to be."""
    warnings: list[str] = []
    if not path.exists():
        warnings.append(f"gate file missing: {path}")
        # synthesize an empty pending file so the caller has a typed object
        return GateFile(gate=_gate_from_path(path), short="", description="",
                        choices=[], status="pending"), warnings

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        gf = GateFile.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        warnings.append(f"{path.name}: unreadable gate file — {e}")
        return GateFile(gate=_gate_from_path(path), short="", description="",
                        choices=[], status="pending"), warnings

    # #72: distinguish a genuinely-empty decision from a *wrong-shape* one (the
    # bare string is already normalized by _coerce_decision, so anything still
    # without a usable choice is either empty or malformed — say which).
    raw = data.get("decision")
    choice = gf.decision.get("choice") if isinstance(gf.decision, dict) else None
    empty = raw is None or (isinstance(raw, dict) and not raw.get("choice"))
    if not choice:
        if empty:
            warnings.append(f"{gf.gate.value}: no decision filled in (status={gf.status})")
        else:
            warnings.append(
                f'{gf.gate.value}: decision must be an object like '
                f'{{"choice": "<one of {gf.choices}>"}} (a bare string is also '
                f"accepted); got {raw!r}"
            )
    elif gf.choices and choice not in gf.choices:
        warnings.append(
            f"{gf.gate.value}: decision choice {choice!r} not in offered "
            f"choices {gf.choices}"
        )
    return gf, warnings


def _gate_from_path(path: Path) -> Gate:
    """Best-effort recover the Gate id from a ``<id>.gate.json`` filename."""
    stem = path.name.split(".", 1)[0]
    try:
        return Gate(stem)
    except ValueError:
        return Gate.G1_FRESHNESS
