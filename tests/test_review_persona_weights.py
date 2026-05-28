"""Persona-specific review scoring weights — Issue #16."""
from __future__ import annotations


def test_review_weights_change_total_across_personas():
    from vibe_resume.core.personas import get_persona
    from vibe_resume.core.review import review
    md = (
        "# Daisy\nBackend Engineer\n\n"
        "## Summary\nBuilt platforms across the stack.\n\n"
        "## Experience\n"
        "- Designed RAG pipeline cutting latency 30%\n"
        "- Built FastAPI service handling 1k qps\n"
        "- Led migration reducing cost 20%\n"
    )
    tl = get_persona("tech_lead")
    hr = get_persona("hr")
    r_tl = review(md, locale_key="en_US", persona=tl)
    r_hr = review(md, locale_key="en_US", persona=hr)
    if tl.review_weights and hr.review_weights:
        assert r_tl.total != r_hr.total
    assert 0 <= r_tl.total <= r_tl.max_total
    assert 0 <= r_hr.total <= r_hr.max_total


def test_review_without_persona_is_uniform():
    from vibe_resume.core.review import review
    md = "# Test\nEngineer\n\n## Summary\nX.\n\n## Experience\n- One bullet here\n"
    r = review(md, locale_key="en_US")
    raw = sum(s.score for s in r.scores if s.max > 0)
    assert r.total == raw
