"""Trade-off surface exploration (#76).

Sweep a small grid of ``top_n × page_budget`` configurations, render+review
each cell, and surface the Pareto-best configs — those not dominated on
(higher score↑, fewer pages↓). This replaces the manual, one-config-at-a-time
``iterate`` loop with a visible trade-off surface.

Like ``iterate``, this is a pure *layout/selection* lever: it never rewrites
bullets, invents metrics, or inserts a human gate to chase points — the same
truthful guarantee. The module itself is pure logic: rendering and reviewing
are injected as callables so it stays trivially unit-testable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ExploreCell:
    """One swept ``(top_n, page_budget)`` configuration and its review outcome."""

    top_n: int
    page_budget: float
    total: int
    max_total: int
    grade: str
    est_pages: float

    def score_ratio(self) -> float:
        """Fraction of the available points scored (0 when ``max_total`` is 0)."""
        if self.max_total == 0:
            return 0.0
        return self.total / self.max_total

    def dominates(self, other: ExploreCell) -> bool:
        """True iff this cell dominates ``other`` on (score↑, pages↓).

        Domination requires being at least as good on both axes and strictly
        better on at least one.
        """
        better_or_equal = (
            self.score_ratio() >= other.score_ratio()
            and self.est_pages <= other.est_pages
        )
        strictly_better = (
            self.score_ratio() > other.score_ratio()
            or self.est_pages < other.est_pages
        )
        return better_or_equal and strictly_better

    def as_dict(self) -> dict:
        return {
            "top_n": self.top_n,
            "page_budget": self.page_budget,
            "total": self.total,
            "max_total": self.max_total,
            "grade": self.grade,
            "est_pages": self.est_pages,
            "score_ratio": self.score_ratio(),
        }


@dataclass
class ExploreResult:
    """The full swept grid plus the Pareto-best subset."""

    cells: list[ExploreCell] = field(default_factory=list)
    pareto_front: list[ExploreCell] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "cells": [c.as_dict() for c in self.cells],
            "pareto_front": [c.as_dict() for c in self.pareto_front],
        }

    def grid_table_rows(self) -> list[tuple]:
        """Rows convenient for a ``rich`` Table print (one row per cell).

        Columns: ``(top_n, page_budget, score, grade, est_pages, on_front)``.
        Sorted by ``top_n`` then ``page_budget`` for a stable, readable grid.
        """
        front = {id(c) for c in self.pareto_front}
        rows: list[tuple] = []
        for c in sorted(self.cells, key=lambda x: (x.top_n, x.page_budget)):
            rows.append(
                (
                    c.top_n,
                    c.page_budget,
                    f"{c.total}/{c.max_total}",
                    c.grade,
                    round(c.est_pages, 2),
                    id(c) in front,
                )
            )
        return rows


def explore_grid(
    top_ns: list[int],
    page_budgets: list[float],
    *,
    render_fn: Callable[[int, float], str],
    review_fn: Callable[[str], tuple[int, int, str, float]],
) -> ExploreResult:
    """Sweep the ``top_ns × page_budgets`` grid and compute the Pareto front.

    ``render_fn(top_n, page_budget)`` returns rendered markdown; ``review_fn(md)``
    returns ``(total, max_total, grade, est_pages)``. Both are injected so this
    function carries no rendering/reviewing logic of its own.

    The Pareto front holds every cell not dominated by any *other* cell on
    (higher ``score_ratio``, fewer ``est_pages``), sorted by ``score_ratio``
    descending then ``est_pages`` ascending.
    """
    cells: list[ExploreCell] = []
    for top_n in top_ns:
        for budget in page_budgets:
            md = render_fn(top_n, budget)
            total, max_total, grade, est_pages = review_fn(md)
            cells.append(
                ExploreCell(
                    top_n=top_n,
                    page_budget=budget,
                    total=total,
                    max_total=max_total,
                    grade=grade,
                    est_pages=est_pages,
                )
            )

    front = [
        c for c in cells if not any(other.dominates(c) for other in cells if other is not c)
    ]
    front.sort(key=lambda c: (-c.score_ratio(), c.est_pages))

    return ExploreResult(cells=cells, pareto_front=front)
