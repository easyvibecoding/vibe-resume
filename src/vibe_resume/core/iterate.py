"""Score-driven auto-iterate loop (#57) — truth-preserving, stops honestly.

The highest Goodhart risk in the toolset, so the design is deliberately strict
(see docs/PRINCIPLES.md P1.5):

- The loop applies ONLY deterministic, truth-preserving levers: tighten the page
  budget (#52, drops least-representative bullets — never pads/fabricates) and
  the composite reorder already done at render. It NEVER rewrites a bullet,
  invents a metric, or inserts a human gate to chase points.
- The truthful edits that DO need bullet rewriting (surface present-but-omitted
  keywords #54, strengthen real human-gate framing #56) are **not auto-applied**;
  they are emitted as human-actionable suggestions sourced from the disclosed
  evidence, each traceable to a real signal.
- It stops at the bar (grade B by default) OR honestly reports the ceiling
  ("page-count" / "genuine content gap") rather than distorting to pass.

`auto_iterate` takes injected render/review/suggestion callables so the loop is
unit-testable without a real profile/render pipeline.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class IterationStep:
    round: int
    lever: str               # what truth-preserving change was applied this round
    max_pages: float | None
    grade: str
    total: int
    max_total: int

    def as_dict(self) -> dict:
        return {
            "round": self.round, "lever": self.lever, "max_pages": self.max_pages,
            "grade": self.grade, "total": self.total, "max_total": self.max_total,
        }


@dataclass
class IterateResult:
    steps: list[IterationStep] = field(default_factory=list)
    best_round: int = 0
    reached_bar: bool = False
    stop_reason: str = ""
    suggestions: list[str] = field(default_factory=list)  # truthful, human-applied only

    @property
    def best(self) -> IterationStep | None:
        return self.steps[self.best_round] if self.steps else None

    def as_dict(self) -> dict:
        return {
            "steps": [s.as_dict() for s in self.steps],
            "best_round": self.best_round,
            "reached_bar": self.reached_bar,
            "stop_reason": self.stop_reason,
            "suggestions": self.suggestions,
        }


def _budget_ladder(target: float, floor: float = 1.0, step: float = 0.3) -> list[float | None]:
    """Candidate page budgets to try, tightening from target down to a floor.
    The first entry is None (no budget — the natural render) so round 0 is the
    untouched baseline."""
    ladder: list[float | None] = [None]
    b = target
    while b >= floor:
        ladder.append(round(b, 2))
        b -= step
    return ladder


def auto_iterate(
    render_fn: Callable[[float | None], str],
    review_fn: Callable[[str], object],
    *,
    page_target: float,
    bar: float = 0.8,
    max_rounds: int = 6,
    suggestion_fn: Callable[[], list[str]] | None = None,
) -> IterateResult:
    """Iterate the truth-preserving page-budget lever until the bar or the ceiling.

    `render_fn(max_pages) -> md`, `review_fn(md) -> ReviewReport` (needs `.total`,
    `.max_total`, `.grade`). Picks the highest-scoring truthful render; if the bar
    isn't reached it reports the honest ceiling + truthful suggestions, never
    distorting to pass."""
    res = IterateResult()
    ladder = _budget_ladder(page_target)[:max_rounds]
    best_ratio = -1.0

    for i, budget in enumerate(ladder):
        md = render_fn(budget)
        rep = review_fn(md)
        total = getattr(rep, "total", 0)
        max_total = getattr(rep, "max_total", 0) or 1
        ratio = total / max_total
        lever = "baseline render" if budget is None else f"page budget ≤ {budget}"
        res.steps.append(IterationStep(
            round=i, lever=lever, max_pages=budget,
            grade=getattr(rep, "grade", "n/a"), total=total, max_total=max_total,
        ))
        if ratio > best_ratio:
            best_ratio = ratio
            res.best_round = i
        if ratio >= bar:
            res.reached_bar = True
            res.stop_reason = f"reached grade {getattr(rep, 'grade', '?')} (≥ bar)"
            break

    if not res.reached_bar:
        tightened = any(s.max_pages is not None for s in res.steps)
        res.stop_reason = (
            "page-count ceiling — content already trimmed toward the budget floor; "
            "the remaining gap is not a length problem"
            if tightened else
            "no truth-preserving lever moved the score to the bar"
        )

    # Truthful, human-applied-only suggestions (never auto-fabricated).
    if suggestion_fn is not None:
        res.suggestions = suggestion_fn()
    if not res.reached_bar:
        res.suggestions.append(
            "Remaining gains require TRUE edits a human applies — surface "
            "present-but-omitted keywords (#54) and real human-gate framing (#56) "
            "from `vibe-resume evidence`; never invent to close the gap (P1)."
        )
    return res
