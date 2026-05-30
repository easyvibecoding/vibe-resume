"""Angle-biased candidate bullet-sets per group (#75).

At the bullets stage (enrich / gate G4) the same activity can legitimately lead
with **impact**, with cross-functional **breadth**, or with **depth** on one
system. This module turns the single-shot draft into a small search over those
framings: each angle is a prompt PREFIX appended to the base enrich prompt (the
anti-fabrication + human-gate rules are untouched), and the user picks the best
candidate per group via the ``bullets-compare`` view.

Pure + deterministic: no clock, no RNG, no I/O — the CLI builds the base prompt
(via ``enricher._build_prompt``), this module appends the angle blocks, and the
session processes the variants exactly like ordinary enrich prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The bias is a lead-framing hint only; every block re-states the never-fabricate
# rule so an angle can never license inventing a metric/scope the activity lacks.
CANDIDATE_ANGLES: dict[str, str] = {
    "impact_first": (
        "\n\nCANDIDATE ANGLE — impact-first:\n"
        "Lead each bullet with the measurable outcome (the metric / cost saved / "
        "latency cut / users served) when the raw activity genuinely supports a "
        "number; put the mechanism second. Never invent a metric the activity "
        "doesn't show — if there is no real number, lead with the concrete result."
    ),
    "breadth_first": (
        "\n\nCANDIDATE ANGLE — breadth-first:\n"
        "Lead with cross-functional reach (systems integrated, teams/stakeholders, "
        "end-to-end ownership) when the activity supports it. Show range over a "
        "single deep dive. Never claim collaboration or scope the input doesn't show."
    ),
    "depth_first": (
        "\n\nCANDIDATE ANGLE — depth-first:\n"
        "Lead with technical depth on the single hardest system (the design "
        "decision, the constraint solved, the architecture) when the activity "
        "supports it. Prefer one rigorous claim over a broad list. Never overstate "
        "depth beyond what the input shows."
    ),
}


def angle_block(angle: str) -> str:
    """The prompt block for one angle. Raises ``KeyError`` on an unknown angle."""
    return CANDIDATE_ANGLES[angle]


def build_candidate_prompts(
    base_prompt: str, angles: list[str] | None = None
) -> dict[str, str]:
    """Return ``{angle: base_prompt + angle_block}`` for each requested angle.

    ``angles=None`` builds all three. The base prompt is preserved verbatim; each
    candidate appends exactly one angle block (no cross-contamination)."""
    keys = list(CANDIDATE_ANGLES) if angles is None else angles
    return {k: base_prompt + angle_block(k) for k in keys}


def select_candidates(
    picks: dict[str, int], by_group: dict[str, list[Any]]
) -> dict[str, Any]:
    """Resolve which candidate to weave per group (#75 G4 ``pick`` decision).

    ``picks`` maps group-name -> chosen candidate index. A group with no pick (or
    an out-of-range index) falls back conservatively to candidate 0 — so an
    un-curated group keeps the first (default) framing rather than dropping out."""
    chosen: dict[str, Any] = {}
    for name, cands in by_group.items():
        if not cands:
            continue
        idx = picks.get(name, 0)
        if not isinstance(idx, int) or idx < 0 or idx >= len(cands):
            idx = 0
        chosen[name] = cands[idx]
    return chosen


@dataclass
class CompareRow:
    name: str
    candidates: list[dict[str, Any]]   # each: {"angle": str, "bullets": [...], ...}


def compare_rows(by_group: dict[str, list[dict[str, Any]]], *, limit: int = 3) -> list[CompareRow]:
    """Side-by-side rows for the ``bullets-compare`` view (top ``limit`` groups)."""
    rows: list[CompareRow] = []
    for name, cands in list(by_group.items())[:limit]:
        rows.append(CompareRow(name=name, candidates=list(cands)))
    return rows
