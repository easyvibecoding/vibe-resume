"""DOB red-flag should not false-match summary/target-role dates (Issue #3)."""
from __future__ import annotations


def test_dob_does_not_match_summary_iso_date():
    """A date like '2024-01-15' in a summary line must NOT trigger DOB red flag."""
    from core.review import review
    md = (
        "# Daisy\n"
        "Backend Engineer\n"
        "daisy@example.com\n\n"
        "**Target:** Backend role\n\n"
        "## Summary\n"
        "Built RAG pipeline 2024-01-15 onwards, cutting latency 30%.\n"
        "\n## Skills\nPython, FastAPI\n"
    )
    r = review(md, locale_key="en_US")
    red_flags = next(s for s in r.scores if s.name == "Red flags")
    assert "DOB" not in " ".join(red_flags.notes), \
        f"false positive: {red_flags.notes}"


def test_dob_with_explicit_label_still_flagged():
    """An actual DOB row WITH a label MUST still trigger the red flag."""
    from core.review import review
    md = (
        "# Daisy\n"
        "Backend Engineer\n"
        "DOB: 1990-01-15\n"
        "daisy@example.com\n\n"
        "## Summary\nXYZ.\n"
    )
    r = review(md, locale_key="en_US")
    red_flags = next(s for s in r.scores if s.name == "Red flags")
    assert any("DOB" in n for n in red_flags.notes), \
        f"expected DOB flag, got: {red_flags.notes}"


def test_dob_with_date_of_birth_label_flagged():
    from core.review import review
    md = (
        "# Daisy\n"
        "Date of birth: 1990-01-15\n"
        "daisy@example.com\n\n"
        "## Summary\nXYZ.\n"
    )
    r = review(md, locale_key="en_US")
    red_flags = next(s for s in r.scores if s.name == "Red flags")
    assert any("DOB" in n for n in red_flags.notes)
