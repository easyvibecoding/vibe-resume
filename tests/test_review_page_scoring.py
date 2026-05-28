"""Per-locale + gradual page-count scoring (Issue #14)."""
from __future__ import annotations


def _make_md(n_bullets: int) -> str:
    lines = ["# Name", "title", "summary line", ""]
    for i in range(n_bullets):
        lines.append(f"- bullet {i} with some content text padding here for length")
    return "\n".join(lines)


def _page_score(r):
    return next(s for s in r.scores if "page" in s.name.lower())


def test_page_count_full_when_under_target_en_us():
    from core.review import review
    r = review(_make_md(15), locale_key="en_US")
    assert _page_score(r).score == 10


def test_page_count_stricter_for_ja_JP_than_en_US():
    from core.review import review
    md = _make_md(80)
    assert _page_score(review(md, locale_key="ja_JP")).score <= _page_score(review(md, locale_key="en_US")).score


def test_page_count_lenient_for_de_DE_than_en_US():
    from core.review import review
    md = _make_md(110)
    assert _page_score(review(md, locale_key="de_DE")).score >= _page_score(review(md, locale_key="en_US")).score


def test_page_count_has_gradual_bands():
    """Scores should include an intermediate band (8 or 5), not just 10/2."""
    from core.review import review
    seen = set()
    for n in (10, 60, 100, 140, 200):
        seen.add(_page_score(review(_make_md(n), locale_key="en_US")).score)
    # At least one intermediate band present across the range
    assert seen & {8, 5}, f"no gradual band seen: {seen}"
