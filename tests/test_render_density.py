"""#52 page-budget density control + estimate_pages."""
from vibe_resume.core.review import estimate_pages
from vibe_resume.render.renderer import _fit_to_page_budget


class _Tpl:
    def render(self, **ctx):
        return "\n".join(a for g in ctx["groups"] for a in g["achievements"])


def test_estimate_pages_grows_with_content():
    short = "\n".join(["x" * 95] * 45)
    long = "\n".join(["x" * 95] * 135)
    assert estimate_pages(short) < estimate_pages(long)
    assert estimate_pages(short) <= 1.2


def test_fit_trims_density_to_budget():
    line = "x" * 95
    ctx = {"groups": [{"achievements": [line] * 30} for _ in range(3)]}  # ~2 pages
    md = _fit_to_page_budget(_Tpl(), ctx, {"_key": "en_US"}, budget=1.0, floor=2)
    fits = estimate_pages(md) <= 1.0
    floored = all(len(g["achievements"]) == 2 for g in ctx["groups"])
    assert fits or floored
    # guardrail P1.4: never grew beyond the original count (no padding)
    assert all(len(g["achievements"]) <= 30 for g in ctx["groups"])
    # did trim (was over budget)
    assert any(len(g["achievements"]) < 30 for g in ctx["groups"])


def test_fit_noop_when_under_budget():
    ctx = {"groups": [{"achievements": ["x" * 95] * 3}]}
    md = _fit_to_page_budget(_Tpl(), ctx, {"_key": "en_US"}, budget=2.0, floor=2)
    assert ctx["groups"][0]["achievements"] == ["x" * 95] * 3  # untouched
    assert md


# ---- #88: surface truncation instead of silently dropping bullets ----------


def test_fit_records_truncation_in_ctx():
    """#88: when the budget fit drops bullets, ctx must record what was dropped
    so the caller can warn (silent truncation hides woven content)."""
    line = "x" * 95
    ctx = {"groups": [{"name": "A", "achievements": [line] * 60},
                      {"name": "B", "achievements": [line] * 60}]}  # ~2.5 pages → must trim
    _fit_to_page_budget(_Tpl(), ctx, {"_key": "en_US"}, budget=1.0, floor=2)
    trunc = ctx.get("_truncation")
    assert trunc, "expected ctx['_truncation'] to list dropped groups"
    by_name = {t["name"]: t for t in trunc}
    assert "A" in by_name and by_name["A"]["kept"] < by_name["A"]["total"]
    assert by_name["A"]["total"] == 60


def test_fit_no_truncation_record_when_under_budget():
    ctx = {"groups": [{"name": "A", "achievements": ["x" * 95] * 3}]}
    _fit_to_page_budget(_Tpl(), ctx, {"_key": "en_US"}, budget=2.0, floor=2)
    assert not ctx.get("_truncation")


def test_apply_bullets_cap_records_and_caps():
    """#88: an explicit per-group cap (`--bullets-per-group`) caps and records."""
    from vibe_resume.render.renderer import _apply_bullets_cap
    ctx = {"groups": [{"name": "A", "achievements": list("abcde")},
                      {"name": "B", "achievements": list("ab")}]}
    _apply_bullets_cap(ctx, 3)
    assert ctx["groups"][0]["achievements"] == list("abc")
    assert ctx["groups"][1]["achievements"] == list("ab")     # already under cap, untouched
    trunc = {t["name"]: t for t in ctx.get("_truncation") or []}
    assert trunc["A"]["kept"] == 3 and trunc["A"]["total"] == 5
    assert "B" not in trunc
