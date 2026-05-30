"""Joined persona diff + review-score dashboard (#78).

`personas-compare` already shows per-group bullet diffs across personas. This
module adds the *combined* view: the same bullet diff PLUS a per-persona
review-score table for one locale + JD, and flags the persona that maximizes
JD fit (highest review total).

Pure logic only — the render + review pipeline is injected as a `score_fn`
callable, so the dashboard is unit-testable without the LLM/render stack. The
CLI builds `score_fn` from `render._render_md` + `review.review`; here we only
call it.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Review check-name -> compact column key surfaced in the dashboard. The
# values are the human-readable `Score.name`s emitted by `review.review`; the
# keys are the stable slugs the CLI/JSON consumers use. A persona whose report
# is missing one of these checks simply omits that key (graceful).
_INTERESTING_CHECKS: dict[str, str] = {
    "Top fold": "top-fold",
    "Numbers per bullet": "numbers-per-bullet",
    "Keyword echo (JD)": "keyword-echo",
    "Page count": "page-count",
    "AI proficiency": "ai-proficiency",
}


@dataclass
class PersonaScoreRow:
    persona: str
    total: int
    max_total: int
    grade: str
    columns: dict[str, int]  # selected check-name slug -> score

    def as_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "total": self.total,
            "max_total": self.max_total,
            "grade": self.grade,
            "columns": dict(self.columns),
        }


@dataclass
class GroupBulletDiff:
    name: str
    sessions: int
    per_persona: dict[str, dict]  # persona_key -> {"role", "summary", "bullets"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sessions": self.sessions,
            "per_persona": {k: dict(v) for k, v in self.per_persona.items()},
        }


@dataclass
class PersonaComparison:
    diffs: list[GroupBulletDiff] = field(default_factory=list)
    scores: list[PersonaScoreRow] = field(default_factory=list)
    best_persona: str | None = None  # persona with highest total; None if no scores

    def as_dict(self) -> dict[str, Any]:
        return {
            "diffs": [d.as_dict() for d in self.diffs],
            "scores": [s.as_dict() for s in self.scores],
            "best_persona": self.best_persona,
        }


def _score_row(persona: str, report: Any) -> PersonaScoreRow:
    """Project a ReviewReport-shaped object into a compact dashboard row.

    Pulls the fixed `_INTERESTING_CHECKS` set out of `report.scores` by name;
    checks absent from the report are simply omitted from `columns`.
    """
    by_name = {s.name: s.score for s in getattr(report, "scores", [])}
    columns = {
        slug: by_name[name]
        for name, slug in _INTERESTING_CHECKS.items()
        if name in by_name
    }
    return PersonaScoreRow(
        persona=persona,
        total=report.total,
        max_total=report.max_total,
        grade=report.grade,
        columns=columns,
    )


def compare_personas(
    persona_groups: dict[str, list[dict]],
    *,
    limit: int = 3,
    score_fn: Callable[[str], Any] | None = None,
) -> PersonaComparison:
    """Build the joined diff + score dashboard.

    Args:
        persona_groups: persona_key -> list of enriched group dicts (already
            loaded from the per-persona cache). Each group dict carries
            ``name``, ``total_sessions``, ``summary``, ``achievements`` and
            ``headline``/``role_label``.
        limit: show the top-N project groups (axis taken from the first
            persona's group order, mirroring the existing personas-compare).
        score_fn: given a persona key, return its ReviewReport (rendered +
            reviewed for the shared locale + JD). When ``None``, ``scores`` is
            empty and ``best_persona`` is ``None``.

    Returns a `PersonaComparison`. Pure: never renders or reviews internally —
    only the injected ``score_fn`` is called.
    """
    personas = list(persona_groups.keys())

    # -- diffs: align by group `name` off the first persona's order ----------
    diffs: list[GroupBulletDiff] = []
    if personas:
        axis = (persona_groups.get(personas[0]) or [])[:limit]
        for group in axis:
            name = group.get("name") or "(unnamed)"
            sessions = group.get("total_sessions", 0) or 0
            per_persona: dict[str, dict] = {}
            for p_key in personas:
                match = next(
                    (g for g in (persona_groups.get(p_key) or []) if g.get("name") == name),
                    None,
                )
                if match is None:
                    continue  # not in this persona's cache
                role = match.get("headline") or match.get("role_label") or "—"
                per_persona[p_key] = {
                    "role": role,
                    "summary": (match.get("summary") or "").strip(),
                    "bullets": list(match.get("achievements") or []),
                }
            diffs.append(GroupBulletDiff(name=name, sessions=sessions, per_persona=per_persona))

    # -- scores: one row per persona via the injected scorer -----------------
    scores: list[PersonaScoreRow] = []
    best_persona: str | None = None
    if score_fn is not None and personas:
        for p_key in personas:
            scores.append(_score_row(p_key, score_fn(p_key)))
        if scores:
            # ties resolve to first in input order (max over a stable list is
            # left-biased), which `max(key=...)` already guarantees.
            best_persona = max(scores, key=lambda r: r.total).persona

    return PersonaComparison(diffs=diffs, scores=scores, best_persona=best_persona)
