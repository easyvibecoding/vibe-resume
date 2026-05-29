# AI-proficiency rubric Implementation Plan (#47 → v0.15.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bake the cited AI-proficiency rubric into enrich (a prompt directive) and review (two gated scorecard checks), sourced from a bundled, dated `market_rubric.yaml` that #46 can later refresh.

**Architecture:** One `core/market_rubric.yaml` (bundled, cited) loaded by `core/rubric.py::load_rubric` (lru_cached, user-cache override wins). Enricher appends `AI_PROFICIENCY_BLOCK` in `_build_prompt` when the group is AI-relevant. Review adds `_check_ai_proficiency` (positive) + `_check_ai_red_flags` (negative), both `max=0`-skipped when the résumé has no AI content.

**Tech Stack:** Python 3.12, pydantic v2, PyYAML, pytest, ruff.

---

### Task 1: Bundled rubric + loader

**Files:**
- Create: `src/vibe_resume/core/market_rubric.yaml`
- Create: `src/vibe_resume/core/rubric.py`
- Test: `tests/test_rubric.py`

- [ ] **Step 1: Write `market_rubric.yaml`** — the full schema from the spec (version, refreshed_at "2026-05-29", source_note, sources[5], bullet_formula, agentic_keywords, ai_tool_names, human_gate_verbs, senior_differentiators, anti_patterns, yellow_flag_patterns[stale_stack/junior_volume/unverified_judge], metric_hints{review,cost,cycle,eval}).

- [ ] **Step 2: Write failing tests** `tests/test_rubric.py`:

```python
from datetime import date
from pathlib import Path

import pytest

from vibe_resume.core import rubric as R


def test_bundled_rubric_loads():
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    assert rb.bullet_formula
    assert "MCP" in rb.agentic_keywords
    assert any(y.kind == "stale_stack" for y in rb.yellow_flags)
    assert rb.metric_hints.get("review")


def test_user_cache_override_wins(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    (cache / "market_rubric.yaml").write_text(
        'version: 9\nrefreshed_at: "2099-01-01"\nbullet_formula: "OVERRIDE"\n'
        'agentic_keywords: [ZZZ]\n', encoding="utf-8")
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    rb = R.load_rubric()
    assert rb.bullet_formula == "OVERRIDE"
    assert rb.agentic_keywords == ["ZZZ"]
    R.load_rubric.cache_clear()


def test_malformed_override_falls_back(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    (cache / "market_rubric.yaml").write_text("{ not: valid: yaml ::", encoding="utf-8")
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    rb = R.load_rubric()
    assert "MCP" in rb.agentic_keywords  # bundled baseline used
    R.load_rubric.cache_clear()


def test_is_stale_boundary():
    R.load_rubric.cache_clear()
    rb = R.load_rubric()
    assert rb.is_stale(as_of=date(2099, 1, 1)) is True
    assert rb.is_stale(as_of=date(2026, 5, 30)) is False
```

- [ ] **Step 3: Run, expect fail** — `uv run pytest tests/test_rubric.py -q` → ImportError / fail.

- [ ] **Step 4: Implement `core/rubric.py`:**

```python
"""Bundled, cited AI-proficiency market rubric (consumed by enrich + review).

The bundled baseline lives next to this module as ``market_rubric.yaml``.
A user-cache copy at ``<user_root>/data/cache/market_rubric.yaml`` (written by
the #46 research pass) takes precedence when present and parseable. All fields
degrade to empty/safe defaults so a malformed rubric never crashes the pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from vibe_resume.core.paths import user_root as _user_root

_BUNDLED = Path(__file__).with_name("market_rubric.yaml")
_STALE_DAYS = 180


@dataclass(frozen=True)
class YellowFlag:
    kind: str
    pattern: str
    why: str

    @property
    def regex(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


@dataclass(frozen=True)
class MarketRubric:
    version: int = 0
    refreshed_at: str | None = None
    source_note: str = ""
    sources: tuple[dict[str, str], ...] = ()
    bullet_formula: str = ""
    agentic_keywords: list[str] = field(default_factory=list)
    ai_tool_names: list[str] = field(default_factory=list)
    human_gate_verbs: list[str] = field(default_factory=list)
    senior_differentiators: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    yellow_flags: tuple[YellowFlag, ...] = ()
    metric_hints: dict[str, list[str]] = field(default_factory=dict)

    def is_stale(self, *, as_of: date | None = None) -> bool:
        if not self.refreshed_at:
            return False
        try:
            ref = date.fromisoformat(self.refreshed_at)
        except ValueError:
            return False
        today = as_of or date.today()
        return (today - ref).days > _STALE_DAYS


def _coerce(data: dict[str, Any]) -> MarketRubric:
    yfs = tuple(
        YellowFlag(kind=str(y.get("kind", "")), pattern=str(y.get("pattern", "")),
                   why=str(y.get("why", "")))
        for y in (data.get("yellow_flag_patterns") or [])
        if isinstance(y, dict) and y.get("pattern")
    )
    return MarketRubric(
        version=int(data.get("version", 0) or 0),
        refreshed_at=(str(data["refreshed_at"]) if data.get("refreshed_at") else None),
        source_note=str(data.get("source_note") or ""),
        sources=tuple(data.get("sources") or ()),
        bullet_formula=str(data.get("bullet_formula") or ""),
        agentic_keywords=list(data.get("agentic_keywords") or []),
        ai_tool_names=list(data.get("ai_tool_names") or []),
        human_gate_verbs=list(data.get("human_gate_verbs") or []),
        senior_differentiators=list(data.get("senior_differentiators") or []),
        anti_patterns=list(data.get("anti_patterns") or []),
        yellow_flags=yfs,
        metric_hints={str(k): list(v) for k, v in (data.get("metric_hints") or {}).items()},
    )


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


@lru_cache(maxsize=1)
def load_rubric() -> MarketRubric:
    override = _user_root() / "data" / "cache" / "market_rubric.yaml"
    if override.exists():
        data = _read(override)
        if data is not None:
            return _coerce(data)
    data = _read(_BUNDLED) or {}
    return _coerce(data)
```

- [ ] **Step 5: Run, expect pass** — `uv run pytest tests/test_rubric.py -q`.

- [ ] **Step 6: Commit** — `git add src/vibe_resume/core/market_rubric.yaml src/vibe_resume/core/rubric.py tests/test_rubric.py && git commit -m "feat(rubric): bundled cited market_rubric + lru_cached loader (#47)"`

---

### Task 2: Enricher AI_PROFICIENCY_BLOCK

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (add block template + `_ai_relevant` + injection in `_build_prompt`)
- Test: `tests/test_enricher.py`

- [ ] **Step 1: Write failing tests** (append to `tests/test_enricher.py`, imports at top of file):

```python
def _grp(**kw):
    from datetime import UTC, datetime
    from vibe_resume.core.schema import ProjectGroup
    base = dict(name="X", first_activity=datetime(2026,1,1,tzinfo=UTC),
                last_activity=datetime(2026,2,1,tzinfo=UTC), total_sessions=5)
    base.update(kw)
    return ProjectGroup(**base)


def test_ai_proficiency_block_fires_on_signals():
    from vibe_resume.core.enricher import _build_prompt
    from vibe_resume.core.schema import AgenticSignals
    g = _grp(agentic_signals=AgenticSignals(orchestration=["fan-out"]))
    p = _build_prompt(g)
    assert "AI-PROFICIENCY FRAMING" in p
    assert "human quality gate" in p


def test_ai_proficiency_block_absent_for_plain_group():
    from vibe_resume.core.enricher import _build_prompt
    g = _grp()
    assert "AI-PROFICIENCY FRAMING" not in _build_prompt(g)


def test_ai_proficiency_block_fires_on_agentic_persona():
    from vibe_resume.core.enricher import _build_prompt
    from vibe_resume.core.personas import get_persona
    g = _grp()
    p = _build_prompt(g, persona=get_persona("agentic"))
    assert "AI-PROFICIENCY FRAMING" in p
```

- [ ] **Step 2: Run, expect fail** — `uv run pytest tests/test_enricher.py -k ai_proficiency -q`.

- [ ] **Step 3: Add the block template** near `AGENTIC_SIGNALS_BLOCK` in `enricher.py`:

```python
AI_PROFICIENCY_BLOCK = (
    "\n\nAI-PROFICIENCY FRAMING (apply only when the raw activity supports it — "
    "never invent):\n"
    "- Winning bullet shape: {formula}.\n"
    "- Pair AI delegation with the human-only work (architecture / security "
    "review / verification): high usage + high verification reads senior; blind "
    "enthusiasm does not.\n"
    "- When the data supports it, surface senior differentiators: {senior}.\n"
    "- Avoid these junior tells: {anti}.\n"
    "- Frame AI tools as directed multipliers, not skills; keep every claim "
    "grounded in the activity above.\n"
)
```

- [ ] **Step 4: Add `_ai_relevant` helper** in `enricher.py`:

```python
def _ai_relevant(
    g: ProjectGroup,
    persona: Persona | None,
    emphasis: EmphasisRecord | None,
) -> bool:
    sig = g.agentic_signals
    if sig is not None and (
        sig.skills_authored or sig.skills_used or sig.mcp_servers_used
        or sig.mcp_authored or sig.sdd or sig.tdd or sig.orchestration
    ):
        return True
    if persona is not None and persona.key == "agentic":
        return True
    if emphasis is not None:
        blob = f"{emphasis.intent} {' '.join(emphasis.keywords)}".lower()
        if any(t in blob for t in ("ai", "agent", "llm", "mcp", "claude", "copilot")):
            return True
    return False
```

- [ ] **Step 5: Inject in `_build_prompt`** — right after the `INSTALLED_TOOLKIT_BLOCK` line (`if any(a.source == Source.INSTALLED_ENV ...)`), before the emphasis block:

```python
    if _ai_relevant(g, persona, emphasis):
        from vibe_resume.core.rubric import load_rubric
        rb = load_rubric()
        body += AI_PROFICIENCY_BLOCK.format(
            formula=rb.bullet_formula or "directing verb + named tool + scale + measurable delta + human quality gate",
            senior="; ".join(rb.senior_differentiators[:4]) or "scoped MCP topology; authored Agent Skills; eval-harness ownership",
            anti="; ".join(rb.anti_patterns[:4]) or "tool name-drop with no verification; raw-volume bragging",
        )
```

- [ ] **Step 6: Run, expect pass** — `uv run pytest tests/test_enricher.py -k ai_proficiency -q`.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat(enricher): AI_PROFICIENCY_BLOCK gated on agentic signals/persona/emphasis (#47)"`

---

### Task 3: Review checks

**Files:**
- Modify: `src/vibe_resume/core/review.py` (`_has_ai_content`, `_check_ai_proficiency`, `_check_ai_red_flags`, wire into `review()`)
- Test: `tests/test_review.py`

- [ ] **Step 1: Write failing tests** (append to `tests/test_review.py`):

```python
_AI_MD = """# Jane Dev

## Experience
- Architected a Claude Code subagent pipeline; reviewed every diff, cutting review round-trips 40%
- Used Claude Code to ship features
- Built an eval harness; AI-validated 200 cases
"""

_PLAIN_MD = """# Jane Dev

## Experience
- Built a FastAPI service handling 2k req/s
- Migrated Postgres with zero downtime
"""

def test_has_ai_content_gate():
    from vibe_resume.core.review import _has_ai_content
    from vibe_resume.core.rubric import load_rubric
    rb = load_rubric()
    assert _has_ai_content(_AI_MD, rb) is True
    assert _has_ai_content(_PLAIN_MD, rb) is False


def test_ai_checks_skipped_on_plain_resume():
    from vibe_resume.core.review import review
    rep = review(_PLAIN_MD, "en_US")
    ai = [s for s in rep.scores if s.name in ("AI proficiency", "AI framing red flags")]
    assert ai and all(s.max == 0 for s in ai)


def test_ai_proficiency_rewards_human_gate():
    from vibe_resume.core.review import review
    rep = review(_AI_MD, "en_US")
    prof = next(s for s in rep.scores if s.name == "AI proficiency")
    assert prof.max == 10 and prof.score > 0


def test_ai_red_flags_flags_namedrop_and_unverified():
    from vibe_resume.core.review import review
    rep = review(_AI_MD, "en_US")
    rf = next(s for s in rep.scores if s.name == "AI framing red flags")
    assert rf.max == 10 and rf.score < 10
    joined = " ".join(rf.notes).lower()
    assert "name-drop" in joined or "junior" in joined or "unverified" in joined
```

- [ ] **Step 2: Run, expect fail** — `uv run pytest tests/test_review.py -k "ai_" -q`.

- [ ] **Step 3: Implement helpers + checks** in `review.py` (above `def review(`):

```python
def _has_ai_content(md: str, rubric: Any) -> bool:
    low = md.lower()
    terms = list(getattr(rubric, "agentic_keywords", [])) + list(getattr(rubric, "ai_tool_names", []))
    return any(t.lower() in low for t in terms)


def _ai_bullets(md: str, rubric: Any) -> list[tuple[int, str]]:
    terms = [t.lower() for t in
             list(getattr(rubric, "agentic_keywords", [])) + list(getattr(rubric, "ai_tool_names", []))]
    return [(ln, b) for ln, b in _bullets_in_scope(md)
            if any(t in b.lower() for t in terms)]


def _check_ai_proficiency(md: str, rubric: Any) -> Score:
    if not _has_ai_content(md, rubric):
        return Score("AI proficiency", 0, 0, ["no AI/agentic content — skipped"])
    bullets = _ai_bullets(md, rubric)
    if not bullets:
        return Score("AI proficiency", 0, 10, ["AI terms present but not in scored bullets"])
    gates = [v.lower() for v in getattr(rubric, "human_gate_verbs", [])]
    paired = [(ln, b) for ln, b in bullets if any(g in b.lower() for g in gates)]
    ratio = len(paired) / len(bullets)
    pts = min(int(round(ratio * 10)), 10)
    notes = [f"{len(paired)}/{len(bullets)} AI bullets pair a tool with a human quality gate"]
    # metric guidance — pointer, never a value
    hints = getattr(rubric, "metric_hints", {}) or {}
    numberless = [(ln, b) for ln, b in bullets if _count_metrics(b) == 0]
    if numberless and hints:
        ln, b = numberless[0]
        cat = _hint_category(b, hints)
        if cat:
            notes.append(f'L{ln} AI bullet has no number — consider measuring: {", ".join(hints[cat])}')
    return Score("AI proficiency", pts, 10, notes)


def _hint_category(bullet: str, hints: dict[str, list[str]]) -> str | None:
    low = bullet.lower()
    table = {"review": ("review", "qa", "pr"), "cost": ("cost", "token", "cache"),
             "cycle": ("cycle", "ship", "deploy", "lead time"),
             "eval": ("eval", "judge", "validate", "test", "regression")}
    for cat, kws in table.items():
        if cat in hints and any(k in low for k in kws):
            return cat
    return next(iter(hints), None)


def _check_ai_red_flags(md: str, rubric: Any) -> Score:
    if not _has_ai_content(md, rubric):
        return Score("AI framing red flags", 0, 0, ["no AI/agentic content — skipped"])
    pts = 10
    notes: list[str] = []
    head = "\n".join(md.splitlines()[:14])
    gates = [v.lower() for v in getattr(rubric, "human_gate_verbs", [])]
    for yf in getattr(rubric, "yellow_flags", ()):  # YellowFlag records
        if yf.kind == "stale_stack":
            if yf.regex.search(head):
                pts -= 2
                notes.append(f"stale-stack in top fold — {yf.why}")
        elif yf.kind == "junior_volume":
            if yf.regex.search(md):
                pts -= 3
                notes.append(f"junior volume-bragging — {yf.why}")
        elif yf.kind == "unverified_judge":
            for ln, b in _bullets_in_scope(md):
                if yf.regex.search(b) and not any(g in b.lower() for g in gates):
                    pts -= 2
                    notes.append(f'L{ln} unverified-judge claim — {yf.why}')
                    break
    # bare tool name-drop: AI bullet with no metric AND no human gate
    for ln, b in _ai_bullets(md, rubric):
        if _count_metrics(b) == 0 and not any(g in b.lower() for g in gates):
            pts -= 2
            notes.append(f'L{ln} bare tool name-drop (no metric, no quality gate) — reads junior')
            break
    pts = max(pts, 0)
    if not notes:
        notes.append("no AI framing red flags detected")
    return Score("AI framing red flags", pts, 10, notes)
```

- [ ] **Step 4: Wire into `review()`** — after the `if company is not None:` block, before `scoring = [...]`:

```python
    from vibe_resume.core.rubric import load_rubric
    _rb = load_rubric()
    scores.append(_check_ai_proficiency(md_text, _rb))
    scores.append(_check_ai_red_flags(md_text, _rb))
```

- [ ] **Step 5: Run, expect pass** — `uv run pytest tests/test_review.py -k "ai_" -q`.

- [ ] **Step 6: Full suite + lint** — `uv run pytest tests/ -q && uv run ruff check .`. Fix any fallout (e.g. tests asserting an exact `len(scores)` / `max_total`).

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat(review): gated AI-proficiency + AI-framing-red-flag checks (#47)"`

---

### Task 4: Config note + release v0.15.0

**Files:**
- Modify: `config.example.yaml` (document the rubric override path under a comment), `CHANGELOG.md`, 6 version strings, `uv.lock`.

- [ ] **Step 1: Add a comment block to `config.example.yaml`** explaining that `data/cache/market_rubric.yaml` (written by the future `research` pass, #46) overrides the bundled rubric. No new enabled key needed.

- [ ] **Step 2: Bump 6 version strings** to `0.15.0` (per `reference_vibe_resume_release_flow`): `pyproject.toml`, `src/vibe_resume/__init__.py`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `skills/ai-used-resume/SKILL.md` frontmatter, and any `AGENTS.md`/`README` version badge the release-flow memory lists. Verify with `grep -rn "0.14.0" --include=*.toml --include=*.json --include=*.md --include=*.py .`

- [ ] **Step 3: CHANGELOG.md** — new `## [0.15.0]` section (em-dash style) summarizing #47.

- [ ] **Step 4: `uv lock`** then full green gate — `uv run pytest tests/ -q && uv run ruff check .`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "chore(release): bump version 0.14.0 → 0.15.0"`

- [ ] **Step 6: finishing-a-development-branch** — invoke superpowers:finishing-a-development-branch: merge to main (FF), push, annotated tag `v0.15.0`, GitHub Release (body from CHANGELOG, author easyvibecoding via keychain PAT), close #47.

---

## Self-review notes
- Spec coverage: rubric (T1) ✓, enrich block (T2) ✓, review 2 checks + metric guidance (T3) ✓, staleness note (T1 `is_stale`; surfaced in report — fold into T3/report if time, else acceptable as informational on the rubric object), bundled-cited sources (T1 yaml) ✓, #46 forward-compat loader (T1) ✓.
- Type consistency: `MarketRubric.yellow_flags` is `tuple[YellowFlag]`; review iterates `.kind/.regex/.why`. `load_rubric()` zero-arg, lru_cached — tests `cache_clear()` between monkeypatches.
- Gating identical to keyword-echo (`max=0` skip) so non-AI résumé `max_total` is unchanged → historical comparability preserved.
