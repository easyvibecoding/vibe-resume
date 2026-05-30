"""Tests for the trade-off surface explorer (#76)."""

from __future__ import annotations

from vibe_resume.core.explore import ExploreCell, explore_grid


def _make_review_fn(table: dict[tuple[int, float], tuple[int, int, str, float]]):
    """Build a deterministic review_fn keyed by the (top_n, page_budget) that
    render_fn embeds into its returned markdown."""

    def render_fn(top_n: int, budget: float) -> str:
        return f"{top_n}|{budget}"

    def review_fn(md: str) -> tuple[int, int, str, float]:
        top_n_s, budget_s = md.split("|")
        return table[(int(top_n_s), float(budget_s))]

    return render_fn, review_fn


def test_grid_fully_swept():
    top_ns = [4, 6, 8]
    budgets = [1.5, 2.0]
    table = {
        (t, b): (80, 100, "B", 1.5) for t in top_ns for b in budgets
    }
    render_fn, review_fn = _make_review_fn(table)
    res = explore_grid(top_ns, budgets, render_fn=render_fn, review_fn=review_fn)
    assert len(res.cells) == len(top_ns) * len(budgets) == 6
    # every swept (top_n, budget) pair is represented exactly once
    seen = {(c.top_n, c.page_budget) for c in res.cells}
    assert seen == {(t, b) for t in top_ns for b in budgets}


def test_pareto_excludes_dominated_and_includes_winner():
    # (4,1.5): high score, fewest pages -> dominates everything.
    # (4,2.0) / (6,2.0): lower score AND more pages -> strictly dominated.
    # (6,1.5): same score as the winner but more pages -> dominated.
    table = {
        (4, 1.5): (90, 100, "A", 1.0),
        (4, 2.0): (70, 100, "C", 2.0),
        (6, 1.5): (90, 100, "A", 1.5),
        (6, 2.0): (70, 100, "C", 2.0),
    }
    render_fn, review_fn = _make_review_fn(table)
    res = explore_grid([4, 6], [1.5, 2.0], render_fn=render_fn, review_fn=review_fn)
    front = {(c.top_n, c.page_budget) for c in res.pareto_front}
    # The unique best (90/100 @ 1.0 pages) must be on the front.
    assert (4, 1.5) in front
    # A strictly dominated cell (lower score + more pages) must NOT be on it.
    assert (4, 2.0) not in front
    assert (6, 2.0) not in front
    # (6, 1.5): same score as winner but more pages -> dominated -> excluded.
    assert (6, 1.5) not in front


def test_genuine_tradeoff_both_stay_on_front():
    # X wins on score but loses on pages; Y wins on pages but loses on score.
    # Neither dominates the other -> both stay on the front. The two filler
    # cells are dominated and drop off.
    table = {
        (4, 1.0): (70, 100, "C", 1.0),  # fewest pages, lower score -> on front
        (8, 2.0): (95, 100, "A", 2.0),  # more pages, highest score -> on front
        (4, 2.0): (60, 100, "D", 2.0),  # dominated by both
        (8, 1.0): (65, 100, "C", 1.5),  # dominated by (4,1.0)
    }
    render_fn, review_fn = _make_review_fn(table)
    res = explore_grid([4, 8], [1.0, 2.0], render_fn=render_fn, review_fn=review_fn)
    front = {(c.top_n, c.page_budget) for c in res.pareto_front}
    assert (4, 1.0) in front
    assert (8, 2.0) in front
    assert (4, 2.0) not in front
    # front sorted by score_ratio desc -> the high-score cell comes first
    assert res.pareto_front[0].top_n == 8


def test_score_ratio_zero_when_max_total_zero():
    cell = ExploreCell(top_n=4, page_budget=1.5, total=0, max_total=0,
                       grade="n/a", est_pages=1.0)
    assert cell.score_ratio() == 0.0


def test_score_ratio_normal():
    cell = ExploreCell(top_n=4, page_budget=1.5, total=80, max_total=100,
                       grade="B", est_pages=1.5)
    assert cell.score_ratio() == 0.8


def test_as_dict_and_grid_rows_shapes():
    table = {
        (4, 1.5): (90, 100, "A", 1.0),
        (4, 2.0): (80, 100, "B", 1.8),
    }
    render_fn, review_fn = _make_review_fn(table)
    res = explore_grid([4], [1.5, 2.0], render_fn=render_fn, review_fn=review_fn)
    d = res.as_dict()
    assert set(d) == {"cells", "pareto_front"}
    assert len(d["cells"]) == 2
    assert all("score_ratio" in c for c in d["cells"])
    rows = res.grid_table_rows()
    assert len(rows) == 2
    # row shape: (top_n, page_budget, "tot/max", grade, est_pages, on_front)
    assert len(rows[0]) == 6
    # sorted by (top_n, page_budget) -> 1.5 budget first
    assert rows[0][1] == 1.5
    # the 1.5/A cell dominates the 2.0/B cell -> only it is on the front
    on_front = [r for r in rows if r[5]]
    assert len(on_front) == 1
    assert on_front[0][1] == 1.5
