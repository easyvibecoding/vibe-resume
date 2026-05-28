"""#36.4: blank education/cert year must not render empty parens."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from vibe_resume.render.i18n import LOCALES


@pytest.mark.parametrize("locale_key", list(LOCALES))
def test_blank_year_no_empty_parens(locale_key, tmp_path, monkeypatch):
    from vibe_resume.render import renderer
    tpl = Path(renderer.__file__).parent / "templates" / f"resume.{locale_key}.md.j2"
    if not tpl.exists():
        pytest.skip(f"no locale template for {locale_key}")
    src = tpl.read_text()

    # For each paren pattern that wraps a year expression, verify every occurrence
    # is preceded (within 80 chars) by the corresponding {% if %} guard.
    checks = [
        (r"\({{ ed\.year }}\)", "ed.year"),
        (r"\({{ c\.year }}\)", "c.year"),
        (r"（{{ ed\.year }}年）", "ed.year"),
        (r"（{{ c\.year }}年）", "c.year"),
        (r"（{{ ed\.year }}）", "ed.year"),
        (r"（{{ c\.year }}）", "c.year"),
    ]
    for expr, var in checks:
        for m in re.finditer(expr, src):
            start = max(0, m.start() - 80)
            context_before = src[start:m.start()]
            guard = f"{{% if {var} %}}"
            assert guard in context_before, (
                f"{locale_key}: unguarded year expression `{m.group()}` — "
                f"no `{guard}` in the 80 chars before it"
            )
