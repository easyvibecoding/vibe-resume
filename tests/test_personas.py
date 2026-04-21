"""Registry + wiring tests for the reviewer-persona layer."""
from __future__ import annotations

import pytest

from core.personas import PERSONAS, Persona, get_persona, list_persona_keys

_EXPECTED_KEYS = {"tech_lead", "hr", "executive", "startup_founder", "academic"}


def test_registry_covers_the_advertised_keys() -> None:
    assert _EXPECTED_KEYS.issubset(PERSONAS.keys()), (
        "PERSONAS is referenced by CLI help + SKILL.md; the documented keys "
        "must remain available — removing one is a breaking change."
    )


def test_every_persona_has_non_empty_bias_and_tips() -> None:
    for key, p in PERSONAS.items():
        assert isinstance(p, Persona)
        assert p.key == key
        assert len(p.label) >= 4
        assert len(p.enrich_bias) >= 100, (
            f"{key} enrich_bias is too short to meaningfully shape an LLM response"
        )
        assert len(p.review_tips) >= 50, (
            f"{key} review_tips should be one full actionable sentence or two"
        )


def test_get_persona_resolves_known_keys() -> None:
    assert get_persona("tech_lead") is PERSONAS["tech_lead"]
    assert get_persona("hr") is PERSONAS["hr"]


@pytest.mark.parametrize("bad", [None, "", "unknown", "Tech Lead", "TECH_LEAD"])
def test_get_persona_rejects_unknown_or_empty(bad: str | None) -> None:
    assert get_persona(bad) is None


def test_list_persona_keys_matches_registry() -> None:
    assert set(list_persona_keys()) == set(PERSONAS.keys())


def test_enrich_prompt_injects_persona_bias_block() -> None:
    """The bias block must land at the tail of the prompt so the model reads
    it right before emitting YAML (same rationale as the tailor block)."""
    from datetime import UTC, datetime

    from core.enricher import _build_prompt
    from core.schema import ProjectGroup, Source
    from render.i18n import get_locale

    now = datetime(2026, 3, 1, tzinfo=UTC)
    g = ProjectGroup(
        name="demo",
        path="/tmp/demo",
        total_sessions=5,
        first_activity=now,
        last_activity=now,
        sources=[Source.CLAUDE_CODE],
        tech_stack=["Python"],
        category_counts={"backend": 3},
        capability_breadth=1,
        activities=[],
    )
    prompt = _build_prompt(g, get_locale("en_US"), persona=PERSONAS["tech_lead"])
    assert "Reviewer persona — Tech Lead" in prompt
    # The persona block must come after the locale template so the model
    # re-reads it just before emitting YAML.
    assert prompt.rindex("Reviewer persona") > prompt.index("Project:")


def test_review_file_attaches_persona_tips(tmp_path) -> None:
    """Smoke test: review_file with --persona surfaces persona_tips in markdown."""
    from pathlib import Path

    from core.review import review_file

    md = tmp_path / "resume_v001_en_US.md"
    md.write_text(
        "# Alex\n\n## Experience\n\n- Shipped feature X.\n", encoding="utf-8"
    )
    report = review_file(Path(md), persona="tech_lead")
    out = report.as_markdown()
    assert report.persona == "tech_lead"
    assert "Reviewer lens" in out
    assert "named systems" in out  # phrase unique to tech_lead.review_tips


# ─────────────────────── multi-persona orchestration ──────────────────────────


def test_resolve_persona_list_accepts_single_csv_and_all() -> None:
    from core.enricher import _resolve_persona_list

    assert _resolve_persona_list(None) == [None]
    assert _resolve_persona_list("") == [None]
    assert _resolve_persona_list("tech_lead") == ["tech_lead"]
    assert _resolve_persona_list("tech_lead,hr") == ["tech_lead", "hr"]
    # Whitespace around commas is tolerated — common when copy-pasting.
    assert _resolve_persona_list(" tech_lead , hr ") == ["tech_lead", "hr"]
    # 'all' expands to every registered persona (order preserved from registry).
    from core.personas import list_persona_keys

    assert _resolve_persona_list("all") == list_persona_keys()
    # Unknown keys drop silently but don't poison the valid ones.
    assert _resolve_persona_list("tech_lead,bogus,hr") == ["tech_lead", "hr"]


def test_groups_path_for_is_persona_scoped(tmp_path, monkeypatch) -> None:
    """Persona-less pipelines keep writing to the canonical file; persona runs
    split into sibling files so variants don't clobber each other."""
    from core.aggregator import GROUPS_PATH, groups_path_for

    assert groups_path_for(None) == GROUPS_PATH
    p = groups_path_for("tech_lead")
    assert p.parent == GROUPS_PATH.parent
    assert p.name == "_project_groups.tech_lead.json"
    assert groups_path_for("tech_lead") != groups_path_for("hr")


def test_load_groups_falls_back_to_canonical_when_persona_cache_missing(
    tmp_path, monkeypatch
) -> None:
    """`render --persona X` before `enrich --persona X` should still produce
    a reasonable draft from the canonical file, not silently render empty."""
    import orjson

    from core import aggregator

    fake_canon = tmp_path / "_project_groups.json"
    fake_canon.write_bytes(
        orjson.dumps(
            [
                {
                    "name": "demo",
                    "path": None,
                    "total_sessions": 1,
                    "first_activity": "2026-01-01T00:00:00+00:00",
                    "last_activity": "2026-01-01T00:00:00+00:00",
                    "sources": ["claude-code"],
                    "tech_stack": [],
                    "category_counts": {},
                    "capability_breadth": 0,
                    "activities": [],
                    "summary": "canonical",
                }
            ]
        )
    )
    monkeypatch.setattr(aggregator, "GROUPS_PATH", fake_canon)

    # No persona-specific file → falls back to canonical.
    result = aggregator.load_groups(persona="tech_lead")
    assert len(result) == 1
    assert result[0].summary == "canonical"
