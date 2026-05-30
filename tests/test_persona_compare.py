"""Tests for the multi-persona diff + review-score dashboard (#78)."""
from __future__ import annotations

from dataclasses import dataclass

from vibe_resume.core.persona_compare import (
    GroupBulletDiff,
    PersonaComparison,
    PersonaScoreRow,
    compare_personas,
)

# -- stub review report (mirrors review.ReviewReport's read surface) ---------

@dataclass
class _StubScore:
    name: str
    score: int
    max: int


@dataclass
class _StubReport:
    total: int
    max_total: int
    grade: str
    scores: list[_StubScore]


def _groups(role: str, summary: str, bullets: list[str], *, names=("Alpha", "Beta", "Gamma")):
    """Build a list of persona group dicts mirroring the cache shape."""
    out = []
    for i, name in enumerate(names):
        out.append(
            {
                "name": name,
                "total_sessions": (i + 1) * 10,
                "role_label": f"{role} {name}",
                "headline": None,
                "summary": f"{summary} for {name}",
                "achievements": [f"{b} ({name})" for b in bullets],
            }
        )
    return out


def _persona_groups():
    return {
        "tech_lead": _groups("Tech Lead", "Led", ["Shipped X", "Cut Y"]),
        "hr": _groups("Recruiter view", "Coordinated", ["Aligned Z"]),
    }


# -- diff axis / limit -------------------------------------------------------

def test_diff_uses_first_persona_axis_and_limit():
    comp = compare_personas(_persona_groups(), limit=2)
    assert isinstance(comp, PersonaComparison)
    assert [d.name for d in comp.diffs] == ["Alpha", "Beta"]
    assert all(isinstance(d, GroupBulletDiff) for d in comp.diffs)
    first = comp.diffs[0]
    assert first.sessions == 10
    assert set(first.per_persona) == {"tech_lead", "hr"}
    assert first.per_persona["tech_lead"]["role"] == "Tech Lead Alpha"
    assert first.per_persona["tech_lead"]["bullets"] == ["Shipped X (Alpha)", "Cut Y (Alpha)"]
    assert first.per_persona["hr"]["summary"] == "Coordinated for Alpha"


def test_diff_headline_preferred_over_role_label():
    groups = _persona_groups()
    groups["tech_lead"][0]["headline"] = "Staff Engineer"
    comp = compare_personas(groups, limit=1)
    assert comp.diffs[0].per_persona["tech_lead"]["role"] == "Staff Engineer"


def test_diff_handles_missing_group_in_a_persona():
    groups = _persona_groups()
    # hr persona only has the first group
    groups["hr"] = groups["hr"][:1]
    comp = compare_personas(groups, limit=3)
    beta = next(d for d in comp.diffs if d.name == "Beta")
    # hr should be absent (not in cache) but tech_lead present
    assert "tech_lead" in beta.per_persona
    assert "hr" not in beta.per_persona


def test_limit_caps_diffs():
    comp = compare_personas(_persona_groups(), limit=1)
    assert len(comp.diffs) == 1


# -- score_fn None path ------------------------------------------------------

def test_no_score_fn_means_no_scores():
    comp = compare_personas(_persona_groups(), score_fn=None)
    assert comp.scores == []
    assert comp.best_persona is None


# -- score_fn path -----------------------------------------------------------

def _score_fn_factory(totals: dict[str, int]):
    def score_fn(persona: str) -> _StubReport:
        scores = [
            _StubScore("Top fold", 4, 10),
            _StubScore("Numbers per bullet", 3, 10),
            _StubScore("Keyword echo (JD)", 5, 10),
            _StubScore("Page count", 6, 10),
            _StubScore("AI proficiency", 2, 10),
            _StubScore("Some other check", 9, 10),
        ]
        return _StubReport(total=totals[persona], max_total=80, grade="B", scores=scores)

    return score_fn


def test_scores_built_and_best_persona_is_max_total():
    comp = compare_personas(
        _persona_groups(),
        score_fn=_score_fn_factory({"tech_lead": 70, "hr": 55}),
    )
    assert [r.persona for r in comp.scores] == ["tech_lead", "hr"]
    assert all(isinstance(r, PersonaScoreRow) for r in comp.scores)
    assert comp.best_persona == "tech_lead"
    row = comp.scores[0]
    assert row.total == 70
    assert row.max_total == 80
    assert row.grade == "B"


def test_columns_extraction_pulls_interesting_checks():
    comp = compare_personas(
        _persona_groups(),
        score_fn=_score_fn_factory({"tech_lead": 70, "hr": 55}),
    )
    cols = comp.scores[0].columns
    assert cols["top-fold"] == 4
    assert cols["numbers-per-bullet"] == 3
    assert cols["keyword-echo"] == 5
    assert cols["page-count"] == 6
    assert cols["ai-proficiency"] == 2
    # an un-tracked check name should not leak into columns
    assert "some-other-check" not in cols


def test_missing_check_is_absent_from_columns():
    def score_fn(persona: str) -> _StubReport:
        # only top-fold present
        return _StubReport(
            total=40,
            max_total=80,
            grade="C",
            scores=[_StubScore("Top fold", 7, 10)],
        )

    comp = compare_personas(_persona_groups(), score_fn=score_fn)
    cols = comp.scores[0].columns
    assert cols == {"top-fold": 7}


def test_best_persona_tie_picks_first_in_input_order():
    comp = compare_personas(
        _persona_groups(),
        score_fn=_score_fn_factory({"tech_lead": 60, "hr": 60}),
    )
    assert comp.best_persona == "tech_lead"


def test_as_dict_round_trips_structure():
    comp = compare_personas(
        _persona_groups(),
        limit=2,
        score_fn=_score_fn_factory({"tech_lead": 70, "hr": 55}),
    )
    d = comp.as_dict()
    assert d["best_persona"] == "tech_lead"
    assert len(d["diffs"]) == 2
    assert d["diffs"][0]["name"] == "Alpha"
    assert d["diffs"][0]["per_persona"]["tech_lead"]["bullets"][0] == "Shipped X (Alpha)"
    assert d["scores"][0]["persona"] == "tech_lead"
    assert d["scores"][0]["columns"]["top-fold"] == 4


def test_empty_persona_groups_is_safe():
    comp = compare_personas({}, score_fn=None)
    assert comp.diffs == []
    assert comp.scores == []
    assert comp.best_persona is None
