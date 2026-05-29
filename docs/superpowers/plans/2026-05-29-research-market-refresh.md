# Research / market-refresh Implementation Plan (#46 → v0.16.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An opt-in `vibe-resume research` (emit → session researches → `--ingest`) that installs a cited, dated `data/cache/market_rubric.yaml` consumed by #47, with strict source-required validation and enrich/review staleness surfacing.

**Architecture:** `core/research.py` (emit prompt + strict ingest + staleness helper) + a `research` CLI command. Ingest writes the #47 override path and clears `load_rubric()` cache. enrich/review surface a staleness note.

**Tech Stack:** Python 3.12, click, PyYAML, pydantic v2, pytest, ruff.

---

### Task 1: `core/research.py` — emit + ingest + staleness

**Files:**
- Create: `src/vibe_resume/core/research.py`
- Test: `tests/test_research.py`

- [ ] **Step 1: Write failing tests** `tests/test_research.py`:

```python
from datetime import date

import pytest

from vibe_resume.core import research as RS
from vibe_resume.core import rubric as R

_VALID = '''
version: 2
refreshed_at: "2026-05-29"
bullet_formula: "verb + tool + scale + delta + gate"
agentic_keywords: [MCP, subagent]
sources:
  - title: "DORA 2025"
    url: "https://dora.dev/research/2025/"
yellow_flag_patterns:
  - kind: stale_stack
    pattern: "(?i)\\\\blangchain\\\\b"
    why: "stale"
'''

_NO_SOURCES = 'version: 2\nrefreshed_at: "2026-05-29"\nagentic_keywords: [MCP]\nsources: []\n'

_BAD_REGEX = '''
refreshed_at: "2026-05-29"
agentic_keywords: [MCP]
sources:
  - title: "x"
    url: "https://x"
yellow_flag_patterns:
  - kind: junior_volume
    pattern: "(?i)\\\\b(unclosed"
    why: "broken regex"
'''


def test_emit_prompt_has_fanout_and_source_rule(tmp_path):
    p = RS.emit_research_prompt(tmp_path, today="2026-05-29")
    body = p.read_text()
    assert "research.result.yaml" in body
    assert "senior" in body.lower() and "ats" in body.lower()
    assert "source" in body.lower()  # every claim needs a source
    assert "2026-05-29" in body


def test_ingest_rejects_no_sources(tmp_path, monkeypatch):
    res = tmp_path / "research.result.yaml"
    res.write_text(_NO_SOURCES, encoding="utf-8")
    monkeypatch.setattr(RS, "_user_root", lambda: tmp_path)
    with pytest.raises(RS.ResearchValidationError):
        RS.ingest_research(res)


def test_ingest_valid_installs_override(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    res = tmp_path / "research.result.yaml"
    res.write_text(_VALID, encoding="utf-8")
    monkeypatch.setattr(RS, "_user_root", lambda: tmp_path)
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    installed, warnings = RS.ingest_research(res)
    assert (tmp_path / "data" / "cache" / "market_rubric.yaml").exists()
    rb = R.load_rubric()
    assert rb.bullet_formula == "verb + tool + scale + delta + gate"
    assert rb.version == 2
    R.load_rubric.cache_clear()


def test_ingest_drops_bad_regex_with_warning(tmp_path, monkeypatch):
    R.load_rubric.cache_clear()
    res = tmp_path / "research.result.yaml"
    res.write_text(_BAD_REGEX, encoding="utf-8")
    monkeypatch.setattr(RS, "_user_root", lambda: tmp_path)
    monkeypatch.setattr(R, "_user_root", lambda: tmp_path)
    installed, warnings = RS.ingest_research(res)
    assert any("regex" in w.lower() for w in warnings)
    rb = R.load_rubric()
    assert rb.yellow_flags == ()  # the only (bad) flag was dropped
    R.load_rubric.cache_clear()


def test_staleness_note():
    R.load_rubric.cache_clear()
    rb_fresh = R.load_rubric()  # bundled 2026-05-29
    assert RS.staleness_note(rb_fresh, as_of=date(2026, 5, 30)) is None
    assert RS.staleness_note(rb_fresh, as_of=date(2099, 1, 1)) is not None
```

- [ ] **Step 2: Run, expect fail** — `uv run pytest tests/test_research.py -q`.

- [ ] **Step 3: Implement `core/research.py`:**

```python
"""Opt-in research/market-refresh pass (#46): emit a cited-research prompt for
the user's Claude Code session, then strictly ingest the result into the #47
rubric override at data/cache/market_rubric.yaml. Never fabricates numbers."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from vibe_resume.core import rubric as _rubric
from vibe_resume.core.paths import user_root as _user_root

RESULT_NAME = "research.result.yaml"
PROMPT_NAME = "research.prompt.md"


class ResearchValidationError(ValueError):
    """Raised when an ingested research result fails the source-required gate."""


_PROMPT = """# Market-refresh research — AI-proficiency résumé rubric

You have web search. Research how engineers are *actually hired for AI/agentic
work right now* and produce a refreshed, cited rubric. Fan out across these
angles, one focused search each:

1. Recruiter / hiring-manager evaluation criteria for AI-assisted engineers.
2. Senior-vs-junior AI signals (what separates "directs AI with judgment" from
   "uses AI").
3. ATS keyword sets for AI / agentic engineering roles (2025-2026).
4. Credible impact-metric *ranges* (review round-trips, first-pass QA %,
   cycle time, token-cost %, eval task-completion) — for sanity-checking only.
5. Current yellow-flag anti-patterns (e.g. a 2024-only LangChain/Pinecone stack
   as a headline; bare tool name-dropping; unverified LLM-as-judge claims).

ADVERSARIAL VERIFICATION (required): for every claim, confirm it against at
least two credible sources (vendor engineering blogs, DORA-style reports, ATS
vendors). KILL any ungrounded hype (e.g. "AI improves productivity 80%") that
lacks a citation. Prefer primary sources.

HARD RULES:
- `refreshed_at: "{today}"`.
- `sources:` MUST be non-empty; every entry needs a `title` and a `url`. A rubric
  with no sources will be REJECTED on ingest.
- Metric ranges are for sanity-checking / flagging ONLY — never to be written as
  numbers into a résumé bullet.

Write the result as YAML to `{result_name}` next to this file, using EXACTLY the
bundled `market_rubric.yaml` schema (version, refreshed_at, source_note,
sources[], bullet_formula, agentic_keywords, ai_tool_names, human_gate_verbs,
senior_differentiators, anti_patterns, yellow_flag_patterns[kind/pattern/why],
metric_hints{{review,cost,cycle,eval}}).

Then run: `vibe-resume research --ingest`
"""


def emit_research_prompt(out_dir: Path, *, today: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / PROMPT_NAME
    path.write_text(_PROMPT.format(today=today, result_name=RESULT_NAME), encoding="utf-8")
    return path


def _validate_regexes(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    yfs = data.get("yellow_flag_patterns")
    if not isinstance(yfs, list):
        return warnings
    kept = []
    for y in yfs:
        if not isinstance(y, dict) or not y.get("pattern"):
            continue
        try:
            re.compile(str(y["pattern"]))
        except re.error as e:
            warnings.append(f"dropped yellow-flag '{y.get('kind')}' — bad regex: {e}")
            continue
        kept.append(y)
    data["yellow_flag_patterns"] = kept
    return warnings


def ingest_research(result_path: Path) -> tuple[dict[str, Any], list[str]]:
    if not result_path.exists():
        raise ResearchValidationError(
            f"no {result_path.name} — run `vibe-resume research` first, then let "
            "your session do the research and write the result."
        )
    try:
        data = yaml.safe_load(result_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ResearchValidationError(f"result YAML did not parse: {e}") from e
    if not isinstance(data, dict):
        raise ResearchValidationError("result root is not a mapping")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources or not any(
        isinstance(s, dict) and s.get("url") for s in sources
    ):
        raise ResearchValidationError(
            "refusing to install an un-sourced rubric — `sources` must be a "
            "non-empty list and at least one entry must carry a url"
        )
    warnings = _validate_regexes(data)
    out = _user_root() / "data" / "cache" / "market_rubric.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    _rubric.load_rubric.cache_clear()
    return data, warnings


def staleness_note(rubric: Any, *, as_of: date | None = None) -> str | None:
    try:
        stale = rubric.is_stale(as_of=as_of)
    except Exception:
        return None
    if not stale:
        return None
    return (
        f"market rubric refreshed {rubric.refreshed_at} is stale "
        "— run `vibe-resume research` to refresh framing/keywords"
    )
```

- [ ] **Step 4: Run, expect pass** — `uv run pytest tests/test_research.py -q`.

- [ ] **Step 5: Commit** — `git add src/vibe_resume/core/research.py tests/test_research.py && git commit -m "feat(research): emit cited-research prompt + strict source-gated ingest (#46)"`

---

### Task 2: CLI `research` command

**Files:**
- Modify: `src/vibe_resume/cli.py`
- Test: `tests/test_cli.py` (or `tests/test_research.py` via CliRunner)

- [ ] **Step 1: Write failing test** (append to `tests/test_research.py`):

```python
def test_cli_research_emit(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from vibe_resume.cli import cli
    monkeypatch.setattr("vibe_resume.cli.ROOT", tmp_path)
    runner = CliRunner()
    # config bootstrap writes config.yaml in cwd; run isolated
    with runner.isolated_filesystem():
        r = runner.invoke(cli, ["research"])
        assert r.exit_code == 0, r.output
        assert "research.prompt.md" in r.output
```

- [ ] **Step 2: Run, expect fail** — `uv run pytest tests/test_research.py -k cli_research -q`.

- [ ] **Step 3: Add the command** to `cli.py` (after the `emphasis` command, before `enrich`):

```python
@cli.command()
@click.option("--ingest", "ingest_", is_flag=True, default=False,
              help="Validate research.result.yaml and install the rubric override")
@click.option("--status", "status_", is_flag=True, default=False,
              help="Show the active rubric date + staleness")
@click.pass_context
def research(ctx: click.Context, ingest_: bool, status_: bool) -> None:
    """Opt-in market-refresh: emit a cited-research prompt for this session to
    run (web search + adversarial verify), then `--ingest` the result into
    data/cache/market_rubric.yaml (consumed by enrich + review)."""
    from datetime import UTC, datetime

    from vibe_resume.core.research import (
        PROMPT_NAME,
        RESULT_NAME,
        ResearchValidationError,
        emit_research_prompt,
        ingest_research,
        staleness_note,
    )
    from vibe_resume.core.rubric import load_rubric

    research_dir = ROOT / "data" / "research"

    if status_:
        rb = load_rubric()
        click.echo(f"rubric version {rb.version}, refreshed_at {rb.refreshed_at}")
        note = staleness_note(rb)
        click.echo(note if note else "rubric is fresh")
        return

    if ingest_:
        try:
            _, warnings = ingest_research(research_dir / RESULT_NAME)
        except ResearchValidationError as e:
            raise click.ClickException(str(e)) from e
        for w in warnings:
            console.print(f"[yellow]{w}[/yellow]")
        load_rubric.cache_clear()
        click.echo("✓ installed data/cache/market_rubric.yaml — enrich/review now use it")
        return

    path = emit_research_prompt(research_dir, today=datetime.now(UTC).date().isoformat())
    click.echo(f"✓ wrote {path}")
    click.echo(
        f"Next: in this Claude Code session, do the research the {PROMPT_NAME} "
        f"describes and write {RESULT_NAME} next to it, then run "
        "`vibe-resume research --ingest`."
    )
```

- [ ] **Step 4: Run, expect pass** — `uv run pytest tests/test_research.py -k cli_research -q`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(cli): research command — emit/ingest/status (#46)"`

---

### Task 3: Staleness surfacing in enrich + review

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (`_do_emit` staleness warning)
- Modify: `src/vibe_resume/core/review.py` (`_check_ai_proficiency` stale note)
- Test: `tests/test_review.py`

- [ ] **Step 1: Write failing test** (append to `tests/test_review.py`):

```python
def test_ai_proficiency_surfaces_staleness(monkeypatch):
    import vibe_resume.core.review as RV
    from vibe_resume.core.rubric import MarketRubric
    stale = MarketRubric(version=1, refreshed_at="2000-01-01",
                         agentic_keywords=["Claude"], human_gate_verbs=["reviewed"])
    monkeypatch.setattr(RV, "load_rubric", lambda: stale)
    rep = RV.review(_AI_MD, "en_US")
    prof = next(s for s in rep.scores if s.name == "AI proficiency")
    assert any("stale" in n.lower() for n in prof.notes)
```

- [ ] **Step 2: Run, expect fail** — `uv run pytest tests/test_review.py -k staleness -q`.

- [ ] **Step 3: Add stale note in `_check_ai_proficiency`** — at the end, before `return Score(...)`:

```python
    from vibe_resume.core.research import staleness_note
    note = staleness_note(rubric)
    if note:
        notes.append(f"⚠ {note}")
```

(Place inside the function after the metric-hint block; `rubric` is already the
param.)

- [ ] **Step 4: Add enrich-side warning in `_do_emit`** — after `groups = _load()` and the empty-check, before computing keywords:

```python
    from vibe_resume.core.research import staleness_note
    from vibe_resume.core.rubric import load_rubric as _load_rubric
    _sn = staleness_note(_load_rubric())
    if _sn:
        console.print(f"[yellow]⚠ {_sn}[/yellow]")
```

- [ ] **Step 5: Run, expect pass** — `uv run pytest tests/test_review.py -k staleness -q`.

- [ ] **Step 6: Full suite + lint** — `uv run pytest tests/ -q && uv run ruff check .`. Resolve any import-cycle (review → research → rubric is acyclic; research imports rubric, review imports both — fine) or E402.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat(enrich,review): surface rubric staleness from the research pass (#46)"`

---

### Task 4: config + release v0.16.0

**Files:**
- Modify: `config.example.yaml`, `CHANGELOG.md`, 6 version strings, `uv.lock`.

- [ ] **Step 1: Add `research:` block** to `config.example.yaml` (enabled:false opt-in marker + stale_after_days:180, documented as network+LLM in-session work writing data/cache/market_rubric.yaml).

- [ ] **Step 2: Bump 6 version strings** `0.15.0 → 0.16.0`: `pyproject.toml`, `.claude-plugin/marketplace.json` (×2 lines), `.claude-plugin/plugin.json`, `skills/ai-used-resume/SKILL.md`, `.codex-plugin/plugin.json`. Verify: `grep -rn "0.15.0" pyproject.toml .claude-plugin/ skills/ .codex-plugin/`.

- [ ] **Step 3: CHANGELOG.md** — new `## [0.16.0] — 2026-05-29` section (em-dash) for #46.

- [ ] **Step 4: `uv lock`** + green gate — `uv run pytest tests/ -q && uv run ruff check .`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "chore(release): bump version 0.15.0 → 0.16.0"`

- [ ] **Step 6: finishing-a-development-branch** — FF-merge to main, then (with explicit user push authorization) push main + annotated tag v0.16.0 + GitHub Release (author easyvibecoding via keychain PAT) + close #46.

---

## Self-review notes
- Spec coverage: emit prompt w/ fan-out + adversarial-verify + source rule (T1) ✓, strict source-gated ingest writing #47 override + cache_clear (T1) ✓, bad-regex tolerance (T1) ✓, CLI emit/ingest/status (T2) ✓, staleness in enrich + review (T3) ✓, config opt-in block (T4) ✓, no-fabrication (prompt forbids number injection) ✓.
- Type consistency: `ingest_research` returns `(dict, list[str])`; `staleness_note(rubric, *, as_of=None)` matches test calls; `load_rubric.cache_clear()` after install. CLI monkeypatches `cli.ROOT`.
- Acyclic imports: research → rubric; review → (rubric, research); enricher → (rubric, research). No cycle back into review/enricher.
```
