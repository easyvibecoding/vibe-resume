# Session-driven enrich + per-locale cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `vibe-resume enrich` / `company verify` 從 spawn `claude -p` 改成預設 emit prompts 給 Claude Code 主 session 處理(吃訂閱額度而非 2026-06-15 起獨立計費的 Agent SDK 額度池),並修正多 locale 互蓋既存缺陷,最後發布 0.4.0。

**Architecture:** 三-mode dispatcher(`prompt`/`subprocess`/`rule-based`)+ 新 `core/enrich_jobs.py` 管 emit/ingest + `groups_path_for(persona, locale)` 把 enriched cache 拆 per-locale。Headless `claude -p` 路徑保留但降級為 opt-in,啟動時印 ⚠ 紅字提醒額度池。

**Tech Stack:** Python 3.12+、Click、Pydantic v2、Jinja2、pytest、orjson、yaml、rich。

**Spec reference:** `docs/superpowers/specs/2026-05-27-session-driven-enrich-design.md`

---

## File Structure

**新增**:

- `core/enrich_jobs.py` — Manifest schema + `emit_jobs()` + `ingest_jobs()` 純函數
- `tests/test_enrich_jobs.py`
- `tests/test_per_locale_cache.py`
- `tests/test_cli_enrich_modes.py`
- `tests/test_company_verify_jobs.py`
- `tests/fixtures/enrich_jobs_sample/manifest.json` + `001_sample.prompt.md` + `001_sample.yaml`

**修改**:

- `core/aggregator.py:394-419` — `groups_path_for(persona, locale)` 簽名擴充 + `load_groups` fallback chain
- `core/enricher.py:269-285, 383-514` — `enrich_groups` 改成 mode dispatcher;`_call_claude` 保留;新 helper `_enrich_with_subprocess` 收容舊邏輯
- `core/runner.py:156-176` — `run_enricher` 加 `mode`、`ingest` 參數
- `cli.py:82-127` — `enrich` 加 `--mode`/`--ingest` 旗標
- `cli.py:218-279` — `personas_compare` 加 `--locale` 必填
- `cli.py:660-755` — `company_verify` 改三-mode
- `render/renderer.py:178` — `load_groups(persona=..., locale=locale_key)` + 空 cache 警告
- `core/review.py` — 同樣 locale-aware
- `skills/ai-used-resume/SKILL.md` — §4a / §4b + Pitfalls 改寫
- `skills/ai-used-resume/references/troubleshooting.md` — 6/15 額度說明
- `README.md` / `README.zh-TW.md` / `README.zh-CN.md` / `README.ja.md` — enrich 章節同步
- `CHANGELOG.md` — 0.4.0 entry
- `.gitignore` — 加 `data/enrich_jobs/`、`data/verification_jobs/`
- 6 處版本字串(見 Task 13)
- `tests/test_personas.py:135-180`、`tests/test_aggregator_helpers.py:38-57`、`tests/test_cli_e2e.py:147` — 配合新 cache 檔名

---

## Task 1: Foundation — gitignore + Pydantic Manifest schema

建立 working-dir gitignore 與 manifest schema,作為後續所有 task 的 type 契約。

**Files:**
- Modify: `.gitignore`(尾端追加)
- Create: `core/enrich_jobs.py`(只放 schema)
- Create: `tests/test_enrich_jobs.py`

- [ ] **Step 1: Append gitignore entries**

Edit `.gitignore`,在最後追加:

```
data/enrich_jobs/
data/verification_jobs/
```

- [ ] **Step 2: Write failing test for manifest schema**

Create `tests/test_enrich_jobs.py`:

```python
"""Tests for core.enrich_jobs — emit/ingest of session-driven enrich prompts."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.enrich_jobs import EnrichJobEntry, EnrichJobManifest


def test_manifest_requires_locale():
    """Locale is a first-class dimension — emit must always know which locale."""
    with pytest.raises(ValidationError):
        EnrichJobManifest(
            version=1,
            created_at=datetime.now(timezone.utc),
            persona=None,
            tailor_keywords=None,
            company=None,
            level=None,
            groups=[],
        )  # missing locale=


def test_manifest_round_trips_via_json():
    m = EnrichJobManifest(
        version=1,
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
        locale="zh_TW",
        persona="tech_lead",
        tailor_keywords=["FastAPI", "RAG"],
        company=None,
        level="senior",
        groups=[
            EnrichJobEntry(
                id="001",
                name="proj-foo",
                prompt_path="001_proj-foo.prompt.md",
                output_path="001_proj-foo.yaml",
                status="pending",
            )
        ],
    )
    restored = EnrichJobManifest.model_validate_json(m.model_dump_json())
    assert restored.locale == "zh_TW"
    assert restored.groups[0].status == "pending"


def test_entry_status_must_be_pending_or_done():
    with pytest.raises(ValidationError):
        EnrichJobEntry(
            id="001",
            name="x",
            prompt_path="a",
            output_path="b",
            status="in-progress",  # not allowed
        )
```

- [ ] **Step 3: Run test, confirm it fails**

```bash
uv run pytest tests/test_enrich_jobs.py -v
```

Expected: ImportError or `AttributeError: module 'core.enrich_jobs' has no attribute 'EnrichJobEntry'`.

- [ ] **Step 4: Implement schema**

Create `core/enrich_jobs.py`:

```python
"""Emit/ingest session-driven enrich job manifests.

Replaces the headless `claude -p` subprocess path with a two-step flow:
1. emit_jobs() writes a manifest + per-group prompt files under
   data/enrich_jobs/<persona-or-default>/<locale>/
2. The user's Claude Code session processes each *.prompt.md and writes
   *.yaml next to it.
3. ingest_jobs() reads the *.yaml back and merges into the per-locale
   enriched cache _project_groups.<persona>.<locale>.json.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EnrichJobEntry(BaseModel):
    id: str = Field(..., description="Zero-padded index e.g. '001'")
    name: str
    prompt_path: str = Field(..., description="Relative to manifest.json dir")
    output_path: str = Field(..., description="Relative to manifest.json dir")
    status: Literal["pending", "done"]


class EnrichJobManifest(BaseModel):
    version: int = 1
    created_at: datetime
    locale: str
    persona: str | None = None
    tailor_keywords: list[str] | None = None
    company: str | None = None
    level: str | None = None
    groups: list[EnrichJobEntry]
```

- [ ] **Step 5: Run test, confirm it passes**

```bash
uv run pytest tests/test_enrich_jobs.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add .gitignore core/enrich_jobs.py tests/test_enrich_jobs.py
git commit -m "feat(enrich): manifest schema + gitignore for session-driven jobs"
```

---

## Task 2: `emit_jobs()` — write manifest + per-group prompt files

把現有的 `_build_prompt()` 結果寫到磁碟,以 persona × locale 拆目錄。

**Files:**
- Modify: `core/enrich_jobs.py`
- Modify: `tests/test_enrich_jobs.py`(追加)

- [ ] **Step 1: Write failing test for emit_jobs**

在 `tests/test_enrich_jobs.py` 末尾追加:

```python
from pathlib import Path

from core.enrich_jobs import emit_jobs
from core.schema import ActivitySource, ProjectGroup


def _fake_group(name: str = "proj-foo") -> ProjectGroup:
    """Minimal ProjectGroup good enough for prompt emission."""
    return ProjectGroup(
        name=name,
        path=None,
        first_activity=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_activity=datetime(2026, 2, 1, tzinfo=timezone.utc),
        sources=[ActivitySource.CLAUDE_CODE],
        total_sessions=5,
        tech_stack=["FastAPI", "PostgreSQL"],
        category_counts={"backend": 3, "frontend": 2},
        capability_breadth=2,
        activities=[],
    )


def test_emit_writes_manifest_and_prompt_per_group(tmp_path: Path):
    groups = [_fake_group("proj-foo"), _fake_group("proj-bar")]
    jobs_dir = emit_jobs(
        groups=groups,
        out_root=tmp_path,
        persona=None,
        locale="en_US",
        tailor_keywords=None,
        company=None,
        level=None,
    )

    assert jobs_dir == tmp_path / "default" / "en_US"
    manifest_path = jobs_dir / "manifest.json"
    assert manifest_path.exists()

    from core.enrich_jobs import EnrichJobManifest
    m = EnrichJobManifest.model_validate_json(manifest_path.read_text())
    assert m.locale == "en_US"
    assert m.persona is None
    assert len(m.groups) == 2
    assert m.groups[0].status == "pending"

    # Each prompt file exists and is non-empty
    for entry in m.groups:
        p = jobs_dir / entry.prompt_path
        assert p.exists() and p.stat().st_size > 0


def test_emit_separates_locales_under_same_persona(tmp_path: Path):
    """zh_TW and en_US runs must not stomp each other."""
    groups = [_fake_group("proj-foo")]
    en_dir = emit_jobs(groups, tmp_path, persona="tech_lead", locale="en_US",
                       tailor_keywords=None, company=None, level=None)
    zh_dir = emit_jobs(groups, tmp_path, persona="tech_lead", locale="zh_TW",
                       tailor_keywords=None, company=None, level=None)
    assert en_dir != zh_dir
    assert (en_dir / "manifest.json").exists()
    assert (zh_dir / "manifest.json").exists()


def test_emit_preserves_existing_yaml_on_re_emit(tmp_path: Path):
    """Re-running emit must NOT delete *.yaml the session has already written."""
    groups = [_fake_group("proj-foo")]
    out = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                    tailor_keywords=None, company=None, level=None)

    # Simulate session writing one yaml back
    yaml_path = out / "001_proj-foo.yaml"
    yaml_path.write_text("summary: hi\n")

    emit_jobs(groups, tmp_path, persona=None, locale="en_US",
              tailor_keywords=None, company=None, level=None)
    assert yaml_path.exists(), "re-emit should not delete user-written yaml"
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest tests/test_enrich_jobs.py -v -k emit
```

Expected: `ImportError: cannot import name 'emit_jobs'`.

- [ ] **Step 3: Implement emit_jobs**

在 `core/enrich_jobs.py` 末尾追加:

```python
import re
from datetime import timezone
from pathlib import Path

import orjson

from core.enricher import _build_prompt
from core.schema import ProjectGroup


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(name: str) -> str:
    """Make a filesystem-safe slug from a group name."""
    s = _SAFE_NAME.sub("-", name).strip("-")
    return s[:60] or "group"


def emit_jobs(
    groups: list[ProjectGroup],
    out_root: Path,
    *,
    persona: str | None,
    locale: str,
    tailor_keywords: list[str] | None,
    company: str | None,
    level: str | None,
    limit: int | None = None,
) -> Path:
    """Write manifest.json + N *.prompt.md files for the session to process.

    Re-emit semantics: manifest + *.prompt.md are overwritten; *.yaml left
    untouched so a partially-completed session is not lost.
    """
    from core.company_profiles import get_company
    from core.levels import get_level
    from core.personas import get_persona
    from render.i18n import get_locale

    locale_meta = get_locale(locale)
    persona_obj = get_persona(persona)
    level_obj = get_level(level)
    company_obj = get_company(company)

    jobs_dir = out_root / (persona or "default") / locale
    jobs_dir.mkdir(parents=True, exist_ok=True)

    selected = groups if limit is None else groups[:limit]

    entries: list[EnrichJobEntry] = []
    for i, g in enumerate(selected, 1):
        idx = f"{i:03d}"
        slug = _slug(g.name)
        prompt_name = f"{idx}_{slug}.prompt.md"
        output_name = f"{idx}_{slug}.yaml"

        prompt_body = _build_prompt(
            g, locale_meta,
            tailor_keywords=tailor_keywords,
            persona=persona_obj,
            level=level_obj,
            company=company_obj,
        )
        (jobs_dir / prompt_name).write_text(prompt_body, encoding="utf-8")

        entries.append(EnrichJobEntry(
            id=idx, name=g.name,
            prompt_path=prompt_name, output_path=output_name,
            status="pending",
        ))

    manifest = EnrichJobManifest(
        created_at=datetime.now(timezone.utc),
        locale=locale,
        persona=persona,
        tailor_keywords=tailor_keywords,
        company=company,
        level=level,
        groups=entries,
    )
    (jobs_dir / "manifest.json").write_bytes(
        orjson.dumps(manifest.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
    )
    return jobs_dir
```

- [ ] **Step 4: Run test, confirm it passes**

```bash
uv run pytest tests/test_enrich_jobs.py -v
```

Expected: 6 passed (3 from Task 1 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add core/enrich_jobs.py tests/test_enrich_jobs.py
git commit -m "feat(enrich): emit_jobs writes manifest + per-locale prompt dir"
```

---

## Task 3: `ingest_jobs()` — read *.yaml, merge into per-locale cache

把使用者在 session 內寫好的 YAML 讀回,經過 `_apply_parsed_output` 套到 ProjectGroup,寫到 per-locale cache 檔。

**Files:**
- Modify: `core/enrich_jobs.py`
- Modify: `tests/test_enrich_jobs.py`(追加)

- [ ] **Step 1: Write failing test for ingest_jobs**

追加到 `tests/test_enrich_jobs.py`:

```python
from core.enrich_jobs import ingest_jobs


def test_ingest_applies_yaml_back_into_groups(tmp_path: Path, monkeypatch):
    groups = [_fake_group("proj-foo")]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)

    # Simulate Claude Code session writing a YAML response
    yaml_body = """
summary: "Built RAG pipeline cutting latency 30%"
role_label: "Backend"
achievements:
  - "Designed FastAPI service handling 1k qps"
  - "Optimized pgvector index, p95 latency 300ms→200ms"
tech_stack: ["FastAPI", "PostgreSQL", "pgvector"]
keywords_for_ats: ["RAG"]
"""
    (jobs_dir / "001_proj-foo.yaml").write_text(yaml_body)

    # Provide groups that match what aggregator would have written
    monkeypatch.setattr("core.enrich_jobs._load_raw_groups", lambda: groups)

    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert warnings == []
    assert len(enriched) == 1
    assert enriched[0].summary.startswith("Built RAG pipeline")
    assert "Designed FastAPI" in enriched[0].achievements[0]


def test_ingest_skips_missing_yaml_with_warning(tmp_path: Path, monkeypatch):
    groups = [_fake_group("proj-foo"), _fake_group("proj-bar")]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)
    # Only write yaml for the first group
    (jobs_dir / "001_proj-foo.yaml").write_text(
        'summary: ok\nachievements: ["Built X"]\ntech_stack: []\n'
    )
    monkeypatch.setattr("core.enrich_jobs._load_raw_groups", lambda: groups)

    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert len(enriched) == 2
    assert enriched[0].summary == "ok"
    assert any("002" in w or "proj-bar" in w for w in warnings)


def test_ingest_warns_on_invalid_yaml(tmp_path: Path, monkeypatch):
    groups = [_fake_group("proj-foo")]
    jobs_dir = emit_jobs(groups, tmp_path, persona=None, locale="en_US",
                         tailor_keywords=None, company=None, level=None)
    (jobs_dir / "001_proj-foo.yaml").write_text("not: valid: yaml: at: all:\n  - x")
    monkeypatch.setattr("core.enrich_jobs._load_raw_groups", lambda: groups)

    enriched, warnings = ingest_jobs(jobs_dir / "manifest.json")
    assert any("proj-foo" in w for w in warnings)
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest tests/test_enrich_jobs.py -v -k ingest
```

Expected: `ImportError: cannot import name 'ingest_jobs'`.

- [ ] **Step 3: Implement ingest_jobs**

在 `core/enrich_jobs.py` 末尾追加:

```python
import yaml as _yaml


def _load_raw_groups() -> list[ProjectGroup]:
    """Thin seam over aggregator so tests can monkey-patch."""
    from core.aggregator import load_groups
    return load_groups()  # raw aggregator output (locale-free)


def ingest_jobs(manifest_path: Path) -> tuple[list[ProjectGroup], list[str]]:
    """Read *.yaml siblings of manifest and apply them onto fresh raw groups.

    Returns (enriched_groups, warnings). Missing or malformed *.yaml never
    aborts — they become warnings and the group keeps its raw aggregator
    summary (effectively the rule-based fallback path).
    """
    from core.enricher import _apply_parsed_output, _fallback_summary

    manifest = EnrichJobManifest.model_validate_json(manifest_path.read_text())
    jobs_dir = manifest_path.parent

    raw = _load_raw_groups()
    by_name = {g.name: g for g in raw}
    warnings: list[str] = []
    enriched: list[ProjectGroup] = []

    for entry in manifest.groups:
        g = by_name.get(entry.name)
        if g is None:
            warnings.append(f"manifest entry {entry.id} {entry.name!r} has no matching raw group — skipped")
            continue

        yaml_path = jobs_dir / entry.output_path
        parsed: dict | None = None
        if not yaml_path.exists():
            warnings.append(f"{entry.id} {entry.name}: missing {entry.output_path}")
        else:
            body = yaml_path.read_text(encoding="utf-8").strip()
            if body.startswith("```"):
                body = "\n".join(body.splitlines()[1:])
            if body.endswith("```"):
                body = "\n".join(body.splitlines()[:-1])
            try:
                loaded = _yaml.safe_load(body)
                if isinstance(loaded, dict):
                    parsed = loaded
                else:
                    warnings.append(f"{entry.id} {entry.name}: yaml root is not a mapping")
            except _yaml.YAMLError as e:
                warnings.append(f"{entry.id} {entry.name}: yaml error — {e}")

        _apply_parsed_output(g, parsed or _fallback_summary(g))
        enriched.append(g)

    return enriched, warnings
```

- [ ] **Step 4: Run test, confirm it passes**

```bash
uv run pytest tests/test_enrich_jobs.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add core/enrich_jobs.py tests/test_enrich_jobs.py
git commit -m "feat(enrich): ingest_jobs reads yaml back into ProjectGroup"
```

---

## Task 4: per-locale `groups_path_for` + `load_groups` fallback chain

擴充 aggregator,讓 enriched cache 帶 locale 維度。

**Files:**
- Modify: `core/aggregator.py:394-419`
- Modify: `tests/test_personas.py:135-180`
- Create: `tests/test_per_locale_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_per_locale_cache.py`:

```python
"""Tests for per-locale enriched cache (groups_path_for + load_groups)."""
from __future__ import annotations

from pathlib import Path

import orjson
import pytest


def test_groups_path_for_includes_locale(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    assert aggregator.groups_path_for(None, None).name == "_project_groups.json"
    p1 = aggregator.groups_path_for(None, "en_US")
    assert p1.name == "_project_groups.default.en_US.json"

    p2 = aggregator.groups_path_for("tech_lead", "zh_TW")
    assert p2.name == "_project_groups.tech_lead.zh_TW.json"


def test_load_groups_prefers_exact_persona_locale(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    raw = [{"name": "raw", "path": None,
            "first_activity": "2026-01-01T00:00:00+00:00",
            "last_activity": "2026-02-01T00:00:00+00:00",
            "sources": ["claude_code"], "total_sessions": 1,
            "tech_stack": [], "category_counts": {}, "capability_breadth": 0,
            "activities": []}]
    en = [{**raw[0], "name": "from-en", "summary": "en"}]
    (tmp_path / "_project_groups.json").write_bytes(orjson.dumps(raw))
    (tmp_path / "_project_groups.tech_lead.en_US.json").write_bytes(orjson.dumps(en))

    g = aggregator.load_groups(persona="tech_lead", locale="en_US")
    assert g[0].name == "from-en"


def test_load_groups_falls_back_to_default_persona_same_locale(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    raw = [{"name": "raw", "path": None,
            "first_activity": "2026-01-01T00:00:00+00:00",
            "last_activity": "2026-02-01T00:00:00+00:00",
            "sources": ["claude_code"], "total_sessions": 1,
            "tech_stack": [], "category_counts": {}, "capability_breadth": 0,
            "activities": []}]
    default_en = [{**raw[0], "name": "from-default-en"}]
    (tmp_path / "_project_groups.json").write_bytes(orjson.dumps(raw))
    (tmp_path / "_project_groups.default.en_US.json").write_bytes(orjson.dumps(default_en))

    g = aggregator.load_groups(persona="tech_lead", locale="en_US")
    assert g[0].name == "from-default-en"


def test_load_groups_final_fallback_is_raw_aggregator(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    raw = [{"name": "raw-only", "path": None,
            "first_activity": "2026-01-01T00:00:00+00:00",
            "last_activity": "2026-02-01T00:00:00+00:00",
            "sources": ["claude_code"], "total_sessions": 1,
            "tech_stack": [], "category_counts": {}, "capability_breadth": 0,
            "activities": []}]
    (tmp_path / "_project_groups.json").write_bytes(orjson.dumps(raw))

    g = aggregator.load_groups(persona=None, locale="en_US")
    assert g[0].name == "raw-only"


def test_load_groups_empty_when_nothing_exists(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    assert aggregator.load_groups(persona="x", locale="en_US") == []
```

同步把 `tests/test_personas.py` 既有的 `test_groups_path_for_is_persona_scoped` 改寫(它現在的斷言會失敗):

```python
def test_groups_path_for_is_persona_scoped(tmp_path, monkeypatch) -> None:
    """Persona-without-locale still returns raw GROUPS_PATH (back-compat seam)."""
    monkeypatch.setattr("core.aggregator.GROUPS_PATH", tmp_path / "_project_groups.json")
    from core.aggregator import GROUPS_PATH, groups_path_for

    assert groups_path_for(None) == GROUPS_PATH
    assert groups_path_for(None, None) == GROUPS_PATH
    # Locale present → per-locale path even without persona
    p = groups_path_for("tech_lead", "en_US")
    assert p.parent == GROUPS_PATH.parent
    assert p.name == "_project_groups.tech_lead.en_US.json"
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/test_per_locale_cache.py tests/test_personas.py -v
```

Expected: import-level failure or `TypeError: groups_path_for() takes 1 positional argument`.

- [ ] **Step 3: Implement new signatures**

Replace `core/aggregator.py:394-419` with:

```python
def groups_path_for(persona: str | None = None, locale: str | None = None) -> Path:
    """Cache path for enriched project groups, scoped to (persona, locale).

    - groups_path_for(None, None)  → GROUPS_PATH (raw aggregator output)
    - groups_path_for(persona_or_none, locale) → _project_groups.<persona-or-default>.<locale>.json

    Per-locale split (added 0.4.0) prevents zh_TW enrich from overwriting
    a prior en_US enrich. Aggregator still writes the locale-free GROUPS_PATH;
    enrich --ingest is what writes the per-locale variants.
    """
    if locale is None:
        return GROUPS_PATH
    p = persona or "default"
    return GROUPS_PATH.parent / f"_project_groups.{p}.{locale}.json"


def load_groups(
    persona: str | None = None,
    locale: str | None = None,
) -> list[ProjectGroup]:
    """Load enriched groups, with fallback chain.

    Order: (persona, locale) → (None, locale) → GROUPS_PATH → [].
    The fallback to the raw aggregator output (no enrichment) is what lets
    `render` show something coherent even when enrich has not been run for
    the requested locale yet.
    """
    candidates: list[Path] = []
    if locale is not None:
        candidates.append(groups_path_for(persona, locale))
        if persona is not None:
            candidates.append(groups_path_for(None, locale))
    candidates.append(GROUPS_PATH)

    for path in candidates:
        if path.exists():
            raw = orjson.loads(path.read_bytes())
            return [ProjectGroup(**g) for g in raw]
    return []
```

- [ ] **Step 4: Run all aggregator-touching tests**

```bash
uv run pytest tests/test_per_locale_cache.py tests/test_personas.py tests/test_aggregator_helpers.py -v
```

Expected: all pass. If `test_aggregator_helpers.py` breaks (its fixtures may seed `_project_groups.json` directly), check whether the new fallback ordering still matches — fix any explicit assertions about the file name to use `groups_path_for(...)`.

- [ ] **Step 5: Commit**

```bash
git add core/aggregator.py tests/test_per_locale_cache.py tests/test_personas.py
git commit -m "feat(aggregator): per-locale enriched cache + fallback chain"
```

---

## Task 5: Refactor `enrich_groups` into mode dispatcher

把舊邏輯包成 `_enrich_with_subprocess()`,新增 `_enrich_emit()` 與 `_enrich_ingest()`,前面加一個 dispatcher。

**Files:**
- Modify: `core/enricher.py:383-514`

- [ ] **Step 1: Write failing test for mode dispatcher**

Create `tests/test_cli_enrich_modes.py`:

```python
"""Tests for enrich_groups mode dispatch (prompt / subprocess / rule-based)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import orjson
import pytest


@pytest.fixture
def seeded_cache(tmp_path, monkeypatch):
    """Seed raw aggregator output so enrich has something to chew on."""
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    raw = [{"name": "proj-foo", "path": None,
            "first_activity": "2026-01-01T00:00:00+00:00",
            "last_activity": "2026-02-01T00:00:00+00:00",
            "sources": ["claude_code"], "total_sessions": 5,
            "tech_stack": ["FastAPI"], "category_counts": {"backend": 5},
            "capability_breadth": 1, "activities": []}]
    aggregator.GROUPS_PATH.write_bytes(orjson.dumps(raw))
    return tmp_path


def test_default_mode_is_prompt_and_writes_manifest(seeded_cache, monkeypatch, capsys):
    """Calling enrich without --mode/--ingest defaults to emit a manifest."""
    from core import enricher
    # Redirect data/enrich_jobs/ to tmp
    monkeypatch.setattr(enricher, "ENRICH_JOBS_DIR", seeded_cache / "enrich_jobs")

    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, locale="en_US")

    manifest = seeded_cache / "enrich_jobs" / "default" / "en_US" / "manifest.json"
    assert manifest.exists()


def test_subprocess_mode_emits_red_quota_warning(seeded_cache, monkeypatch, capsys):
    from core import enricher
    # Make subprocess path a no-op so the test focuses on the warning
    monkeypatch.setattr(enricher, "_call_claude", lambda *a, **kw: None)
    enricher.enrich_groups(cfg={}, cache_dir=seeded_cache, locale="en_US", mode="subprocess")
    out = capsys.readouterr().out
    assert "Agent SDK" in out and "subprocess" in out
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest tests/test_cli_enrich_modes.py -v
```

Expected: TypeError on `mode=`/`ingest=` kwargs, or `AttributeError: ENRICH_JOBS_DIR`.

- [ ] **Step 3: Add ENRICH_JOBS_DIR constant + refactor enrich_groups**

In `core/enricher.py`, near the top imports add:

```python
import os
ENRICH_JOBS_DIR = Path(os.environ.get("VIBE_RESUME_ROOT") or Path(__file__).parent.parent) / "data" / "enrich_jobs"
```

Then replace the current `enrich_groups` + `_enrich_one_persona` with this dispatcher pattern (keeping `_enrich_one_persona` body but renaming to `_enrich_with_subprocess`):

```python
from typing import Literal

EnrichMode = Literal["prompt", "subprocess", "rule-based"]


def enrich_groups(
    cfg: dict[str, Any],
    cache_dir: Path,
    limit: int | None = None,
    locale: str | None = None,
    tailor: str | None = None,
    persona: str | None = None,
    company: str | None = None,
    level: str | None = None,
    *,
    mode: EnrichMode = "prompt",
    ingest: bool = False,
) -> None:
    """Run the enrich stage in one of three modes.

    - prompt (default): write prompt files to data/enrich_jobs/<persona>/<locale>/
      for the Claude Code main session to process; user runs `--ingest` after.
      Uses subscription quota (not the 2026-06-15 Agent SDK quota pool).
    - subprocess: spawn `claude -p` per group (old 0.3.x behaviour). Bills
      against the Agent SDK quota pool — prints a red warning.
    - rule-based: skip LLM entirely; every group gets _fallback_summary().
    """
    persona_keys = _resolve_persona_list(persona)
    locale_key = locale or cfg.get("render", {}).get("locale") or "en_US"

    if ingest:
        for p_key in persona_keys:
            _do_ingest(p_key, locale_key)
        return

    if mode == "subprocess":
        console.print(
            "[red]⚠ --mode subprocess spawns `claude -p`, which bills against "
            "the Anthropic Agent SDK quota pool (separate from your Claude Code "
            "subscription, 2026-06-15 change). Default mode 'prompt' uses your "
            "session quota.[/red]"
        )

    if len(persona_keys) > 1:
        label_list = ", ".join(k for k in persona_keys if k)
        console.print(f"[cyan]multi-persona run:[/cyan] {label_list}")

    for p_key in persona_keys:
        if len(persona_keys) > 1:
            console.print(f"\n[bold cyan]── persona: {p_key} ──[/bold cyan]")
        if mode == "prompt":
            _do_emit(cfg, p_key, locale_key, tailor, company, level, limit)
        elif mode == "subprocess":
            _enrich_with_subprocess(
                cfg, cache_dir, limit, locale_key, tailor,
                persona_key=p_key, company_key=company, level_key=level,
            )
        else:  # rule-based
            _enrich_rule_based_only(cache_dir, p_key, locale_key, limit)


def _do_emit(cfg, persona, locale_key, tailor, company, level, limit) -> None:
    from core.enrich_jobs import emit_jobs
    from core.aggregator import load_groups as _load
    from core.review import parse_jd_keywords

    groups = _load()  # raw aggregator output
    if not groups:
        console.print("[yellow]no groups to enrich — run aggregate first[/yellow]")
        return

    tailor_keywords = None
    if tailor:
        p = Path(tailor)
        tailor_keywords = parse_jd_keywords(p) if p.exists() else None

    jobs_dir = emit_jobs(
        groups, ENRICH_JOBS_DIR,
        persona=persona, locale=locale_key,
        tailor_keywords=tailor_keywords,
        company=company, level=level, limit=limit,
    )
    persona_arg = f" --persona {persona}" if persona else ""
    console.print(f"[green]✓[/green] wrote {len(groups[:limit] if limit else groups)} prompts to {jobs_dir.relative_to(jobs_dir.parents[2])}")
    console.print(
        f"[cyan]Next:[/cyan] in your Claude Code session, process each "
        f"*.prompt.md → write *.yaml (see SKILL.md §4a), then run "
        f"`uv run vibe-resume enrich --ingest --locale {locale_key}{persona_arg}`"
    )


def _do_ingest(persona: str | None, locale_key: str) -> None:
    from core.aggregator import groups_path_for
    from core.enrich_jobs import ingest_jobs

    jobs_dir = ENRICH_JOBS_DIR / (persona or "default") / locale_key
    manifest = jobs_dir / "manifest.json"
    if not manifest.exists():
        console.print(
            f"[red]no manifest at {manifest} — "
            f"run `vibe-resume enrich --locale {locale_key}"
            f"{' --persona ' + persona if persona else ''}` first[/red]"
        )
        raise SystemExit(1)

    enriched, warnings = ingest_jobs(manifest)
    for w in warnings:
        console.print(f"  [yellow]{w}[/yellow]")

    out_path = groups_path_for(persona, locale_key)
    out_path.write_bytes(orjson.dumps(
        [g.model_dump(mode="json") for g in enriched],
        option=orjson.OPT_INDENT_2,
    ))
    console.print(f"[green]✓[/green] ingested → {out_path.name} ({len(enriched)} groups)")


def _enrich_rule_based_only(cache_dir, persona, locale_key, limit) -> None:
    """All-fallback path: useful for CI without any LLM."""
    from core.aggregator import groups_path_for, load_groups as _load
    groups = _load()
    enriched: list[dict[str, Any]] = []
    selected = groups if limit is None else groups[:limit]
    for g in selected:
        _apply_parsed_output(g, _fallback_summary(g))
        enriched.append(g.model_dump(mode="json"))
    for g in groups[limit:] if limit else []:
        enriched.append(g.model_dump(mode="json"))
    groups_path_for(persona, locale_key).write_bytes(
        orjson.dumps(enriched, option=orjson.OPT_INDENT_2)
    )
```

Rename existing `_enrich_one_persona` → `_enrich_with_subprocess`, change signature to take `locale_key` (already does via `locale` arg — just pass through), and at the end change the write site:

```python
# was: out_path = groups_path_for(persona_key)
out_path = groups_path_for(persona_key, locale_meta["_key"])
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_enrich_modes.py tests/test_enrich_jobs.py tests/test_per_locale_cache.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/enricher.py tests/test_cli_enrich_modes.py
git commit -m "feat(enricher): three-mode dispatcher (prompt/subprocess/rule-based)"
```

---

## Task 6: Wire CLI `enrich --mode --ingest` + update runner

**Files:**
- Modify: `core/runner.py:156-176`
- Modify: `cli.py:82-127`

- [ ] **Step 1: Write failing test for CLI flag plumbing**

Append to `tests/test_cli_enrich_modes.py`:

```python
def test_cli_enrich_help_lists_mode_and_ingest(tmp_path):
    """Smoke: --mode and --ingest flags are wired up."""
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "enrich", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "--mode" in r.stdout
    assert "--ingest" in r.stdout
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest tests/test_cli_enrich_modes.py -v -k cli_enrich_help
```

Expected: `--mode` or `--ingest` not in help output.

- [ ] **Step 3: Update `core/runner.py:run_enricher`**

Replace `core/runner.py:156-176` with:

```python
def run_enricher(
    cfg: dict[str, Any],
    limit: int | None = None,
    locale: str | None = None,
    tailor: str | None = None,
    persona: str | None = None,
    company: str | None = None,
    level: str | None = None,
    *,
    mode: str = "prompt",
    ingest: bool = False,
) -> None:
    from core.enricher import enrich_groups

    enrich_groups(
        cfg, CACHE_DIR,
        limit=limit, locale=locale, tailor=tailor,
        persona=persona, company=company, level=level,
        mode=mode, ingest=ingest,
    )
```

- [ ] **Step 4: Add flags to `cli.py::enrich`**

In `cli.py:82-127`, add two `click.option`s before `@click.pass_context` and pass them through:

```python
@click.option(
    "--mode",
    type=click.Choice(["prompt", "subprocess", "rule-based"], case_sensitive=False),
    default="prompt",
    show_default=True,
    help="prompt: emit *.prompt.md for Claude Code session (uses subscription quota). "
         "subprocess: spawn `claude -p` (bills against Agent SDK quota pool since 2026-06-15). "
         "rule-based: no LLM, fallback summaries only.",
)
@click.option(
    "--ingest",
    is_flag=True,
    default=False,
    help="Read *.yaml back from data/enrich_jobs/<persona>/<locale>/ and merge into the per-locale cache.",
)
@click.pass_context
def enrich(
    ctx, limit, locale, tailor, persona, company, level, mode, ingest,
):
    """Generate per-group résumé bullets via Claude Code session (default) or claude -p subprocess."""
    from core.runner import run_enricher
    _warn_if_company_stale(company)
    run_enricher(
        ctx.obj["config"],
        limit=limit, locale=locale, tailor=tailor,
        persona=persona, company=company, level=level,
        mode=mode, ingest=ingest,
    )
```

- [ ] **Step 5: Run all enrich tests + the CLI smoke**

```bash
uv run pytest tests/test_cli_enrich_modes.py tests/test_enrich_jobs.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add cli.py core/runner.py tests/test_cli_enrich_modes.py
git commit -m "feat(cli): add enrich --mode and --ingest flags"
```

---

## Task 7: Pass locale to `load_groups` from render + review

**Files:**
- Modify: `render/renderer.py:178`
- Modify: `core/review.py`(找 `load_groups(` 呼叫處)

- [ ] **Step 1: Write failing test for render reading per-locale cache**

Append to `tests/test_per_locale_cache.py`:

```python
def test_render_picks_up_per_locale_cache(tmp_path, monkeypatch):
    from core import aggregator
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")

    en = [{"name": "from-en-cache", "path": None,
           "first_activity": "2026-01-01T00:00:00+00:00",
           "last_activity": "2026-02-01T00:00:00+00:00",
           "sources": ["claude_code"], "total_sessions": 1,
           "tech_stack": [], "category_counts": {}, "capability_breadth": 0,
           "activities": [], "summary": "from per-locale en cache"}]
    (tmp_path / "_project_groups.default.en_US.json").write_bytes(orjson.dumps(en))

    # render's load call:
    groups = aggregator.load_groups(persona=None, locale="en_US")
    assert groups[0].summary == "from per-locale en cache"
```

- [ ] **Step 2: Find call sites**

```bash
grep -n "load_groups(" render/renderer.py core/review.py
```

- [ ] **Step 3: Update each call to pass locale**

In `render/renderer.py:178` change:

```python
groups = load_groups(persona=persona)
```

to:

```python
groups = load_groups(persona=persona, locale=locale_key)
if not groups:
    pass  # downstream handles empty
elif all(not (g.summary or g.achievements) for g in groups):
    from rich.console import Console as _C
    _C().print(
        f"[yellow]⚠ no enriched cache for locale={locale_key}; "
        f"rendering from raw aggregator output. "
        f"Run `vibe-resume enrich --locale {locale_key}` then `--ingest --locale {locale_key}`.[/yellow]"
    )
```

In `core/review.py`, find the `load_groups(` call (likely takes `persona` only today). The review only inspects rendered markdown text, so it might not call `load_groups` at all — if it doesn't, skip this file. If it does (e.g. for keyword echo against group tech_stack), add `locale=locale_key` the same way.

Quick check:

```bash
grep -n "load_groups\|locale" core/review.py | head
```

If no `load_groups` call — done, this file is locale-agnostic.

- [ ] **Step 4: Run tests + e2e**

```bash
uv run pytest tests/test_per_locale_cache.py tests/test_cli_e2e.py -v
```

If `test_cli_e2e.py` fails because its fixture seeds `_project_groups.json` and now render's fallback warning prints, just verify the test still asserts core behaviour (rendered file exists) — the warning is informational. If needed, the fixture can be updated to seed `_project_groups.default.en_US.json` to suppress the warning.

- [ ] **Step 5: Commit**

```bash
git add render/renderer.py core/review.py tests/test_per_locale_cache.py
git commit -m "feat(render): read per-locale enriched cache + empty-cache warning"
```

---

## Task 8: `personas-compare --locale` required

**Files:**
- Modify: `cli.py:218-279`

- [ ] **Step 1: Write failing test**

Append to `tests/test_cli_enrich_modes.py`:

```python
def test_personas_compare_requires_locale():
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "personas-compare"],
        capture_output=True, text=True, timeout=15,
    )
    # Missing required --locale → click exits non-zero with a usage error
    assert r.returncode != 0
    assert "locale" in (r.stderr + r.stdout).lower()
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest tests/test_cli_enrich_modes.py -k personas_compare -v
```

Expected: current `personas-compare` works without `--locale`, test fails.

- [ ] **Step 3: Add required `--locale` to personas_compare**

In `cli.py:218-279` find the `@click.command("personas-compare")` decorator (or however it's spelled). Add:

```python
@click.option(
    "--locale",
    required=True,
    help="Locale of the enriched cache to compare (e.g. en_US). Required after 0.4.0 since enriched cache is per-locale.",
)
```

Then change the cache lookup loop inside the function:

```python
# was: candidates = [k for k in list_persona_keys() if groups_path_for(k).exists()]
candidates = [k for k in list_persona_keys() if groups_path_for(k, locale).exists()]
...
# was: p = groups_path_for(k)
p = groups_path_for(k, locale)
```

(Pass `locale` from the click option into the function arg.)

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli_enrich_modes.py -k personas_compare -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_cli_enrich_modes.py
git commit -m "feat(cli): personas-compare requires --locale (per-locale cache split)"
```

---

## Task 9: `company verify` three-mode refactor

對齊 enrich 的三-mode 模式;`--emit` dump prompt 到 `data/verification_jobs/<key>_<date>/`,`--ingest` 讀 `report.md` → 寫 `verification_reports/`。

**Files:**
- Modify: `cli.py:660-755`
- Create: `tests/test_company_verify_jobs.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_company_verify_jobs.py`:

```python
"""Tests for `company verify` three-mode flow."""
from __future__ import annotations

import subprocess

import pytest


def test_company_verify_help_lists_emit_ingest_mode():
    r = subprocess.run(
        ["uv", "run", "python", "cli.py", "company", "verify", "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 0, r.stderr
    assert "--emit" in r.stdout
    assert "--ingest" in r.stdout
    assert "--mode" in r.stdout


def test_company_verify_emit_writes_prompt(tmp_path, monkeypatch):
    """--emit dumps prompt.md + manifest.json to data/verification_jobs/<key>_<date>/."""
    from cli import VERIFICATION_REPORTS_DIR  # for reference; not used directly
    # Use a real bundled profile key — there should be at least 'ramp'
    from core.company_profiles import COMPANY_PROFILES
    key = next(iter(COMPANY_PROFILES))

    monkeypatch.chdir(tmp_path)
    # Need to run under a sandboxed VIBE_RESUME_ROOT
    env = {"VIBE_RESUME_ROOT": str(tmp_path)}
    r = subprocess.run(
        ["uv", "run", "python",
         str(__import__("pathlib").Path(__file__).resolve().parent.parent / "cli.py"),
         "company", "verify", "--emit", key],
        capture_output=True, text=True, timeout=30,
        env={**__import__("os").environ, **env},
    )
    assert r.returncode == 0, r.stderr
    # Expect data/verification_jobs/<key>_<date>/ directory to be created
    jobs_root = tmp_path / "data" / "verification_jobs"
    assert jobs_root.exists()
    sub = next(jobs_root.iterdir())
    assert (sub / "prompt.md").exists()
    assert (sub / "manifest.json").exists()
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest tests/test_company_verify_jobs.py -v
```

Expected: `--emit`/`--ingest`/`--mode` not in help output; the directory creation test errors out.

- [ ] **Step 3: Refactor `company_verify` in cli.py**

Replace `cli.py:660-755` (the `company_verify` function and its constants) with:

```python
VERIFICATION_REPORTS_DIR = ROOT / "data" / "verification_reports"
VERIFICATION_JOBS_DIR = ROOT / "data" / "verification_jobs"


def _build_verify_prompt(key: str, profile, yaml_body: str) -> str:
    from datetime import date
    today = date.today().isoformat()
    return _VERIFY_PROMPT.format(key=key, today=today, yaml_body=yaml_body)


@company.command("verify")
@click.argument("key")
@click.option("--emit", "do_emit", is_flag=True, default=False,
              help="Write prompt.md + manifest.json to data/verification_jobs/<key>_<date>/ for the Claude Code session to process. Default mode.")
@click.option("--ingest", "do_ingest", is_flag=True, default=False,
              help="Read report.md from data/verification_jobs/<key>_<date>/ and save to data/verification_reports/.")
@click.option("--mode",
              type=click.Choice(["prompt", "subprocess"], case_sensitive=False),
              default="prompt", show_default=True,
              help="prompt (default): emit + ingest pair. subprocess: spawn `claude -p` (bills Agent SDK quota pool since 2026-06-15).")
@click.option("--apply", is_flag=True, default=False,
              help="On ingest with verdict 'clean', auto-bump last_verified_at to today.")
@click.option("--timeout", type=int, default=300,
              help="claude CLI timeout in seconds (subprocess mode only).")
def company_verify(key: str, do_emit: bool, do_ingest: bool, mode: str, apply: bool, timeout: int) -> None:
    """Fact-check a company profile.

    Default (prompt mode): emit prompt + manifest for Claude Code session to
    process with WebSearch/WebFetch tools; then call again with --ingest to
    save the report and parse the verdict.

    --mode subprocess: spawn `claude -p` (old 0.3.x behaviour, bills against
    Agent SDK quota pool).
    """
    from datetime import date

    from core.company_profiles import COMPANY_PROFILES, PROFILES_DIR

    profile = COMPANY_PROFILES.get(key)
    if profile is None:
        raise click.UsageError(
            f"unknown company key {key!r}. Run `vibe-resume company list`."
        )

    today = date.today().isoformat()
    job_dir = VERIFICATION_JOBS_DIR / f"{key}_{today}"

    if do_ingest:
        return _verify_ingest(key, job_dir, apply)

    if mode == "subprocess":
        console.print(
            "[red]⚠ --mode subprocess spawns `claude -p`, billing against the "
            "Agent SDK quota pool (separate from Claude Code subscription, "
            "2026-06-15 change). Default mode 'prompt' uses your session quota.[/red]"
        )
        return _verify_subprocess(key, profile, PROFILES_DIR, today, timeout, apply)

    # prompt mode (default) — emit
    return _verify_emit(key, profile, PROFILES_DIR, today, job_dir)


def _verify_emit(key, profile, profiles_dir, today, job_dir):
    job_dir.mkdir(parents=True, exist_ok=True)
    yaml_body = (profiles_dir / f"{key}.yaml").read_text(encoding="utf-8")
    prompt = _build_verify_prompt(key, profile, yaml_body)
    (job_dir / "prompt.md").write_text(prompt, encoding="utf-8")

    import orjson
    manifest = {
        "version": 1,
        "key": key, "label": profile.label,
        "created_at": today,
        "prompt": "prompt.md",
        "report": "report.md",
        "status": "pending",
    }
    (job_dir / "manifest.json").write_bytes(orjson.dumps(manifest, option=orjson.OPT_INDENT_2))
    console.print(f"[green]✓[/green] wrote verify job to {job_dir.relative_to(ROOT)}")
    console.print(
        f"[cyan]Next:[/cyan] in your Claude Code session, run the WebSearch+WebFetch "
        f"workflow against prompt.md, save report to {job_dir.name}/report.md, then run "
        f"`uv run vibe-resume company verify --ingest {key}`."
    )


def _verify_ingest(key, job_dir, apply_flag):
    report_path = job_dir / "report.md"
    if not report_path.exists():
        console.print(f"[red]no report.md at {report_path}[/red]")
        raise click.Abort()

    VERIFICATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    final = VERIFICATION_REPORTS_DIR / f"{job_dir.name}.md"
    final.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]✓[/green] saved report to {final.relative_to(ROOT)}")

    verdict = _parse_verdict(final.read_text(encoding="utf-8"))
    _handle_verdict(key, verdict, apply_flag)


def _verify_subprocess(key, profile, profiles_dir, today, timeout, apply_flag):
    """Old 0.3.x path — kept for CI/headless."""
    from core.enricher import _call_claude
    yaml_body = (profiles_dir / f"{key}.yaml").read_text(encoding="utf-8")
    prompt = _build_verify_prompt(key, profile, yaml_body)
    console.print(f"[cyan]verifying {profile.label} ({key}) via claude -p subprocess…[/cyan]")
    report = _call_claude(prompt, timeout=timeout)
    if not report:
        console.print("[red]claude CLI unavailable or call failed.[/red]")
        raise click.Abort()

    VERIFICATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    final = VERIFICATION_REPORTS_DIR / f"{key}_{today}.md"
    final.write_text(report, encoding="utf-8")
    console.print(f"[green]✓[/green] saved report to {final.relative_to(ROOT)}")
    verdict = _parse_verdict(report)
    _handle_verdict(key, verdict, apply_flag)


def _handle_verdict(key, verdict, apply_flag):
    """Shared post-report logic for both modes."""
    console.print(f"verdict: [bold]{verdict}[/bold]")
    if verdict == "clean" and apply_flag:
        from cli import _mark_verified_today  # if it exists; otherwise inline a bump
        _mark_verified_today(key)
```

If `_mark_verified_today` doesn't exist with that exact name in `cli.py`, find the implementation of `company mark-verified` and call its body directly — same behaviour the old `--apply` path used.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_company_verify_jobs.py -v
```

Expected: all pass. The `test_company_verify_emit_writes_prompt` test may need a `data/verification_reports/` sibling to exist; create it in the test if needed.

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_company_verify_jobs.py
git commit -m "feat(verify): company verify three-mode (prompt/subprocess) + warning"
```

---

## Task 10: SKILL.md §4a/§4b + remove Pitfalls 互蓋警告

**Files:**
- Modify: `skills/ai-used-resume/SKILL.md`

- [ ] **Step 1: Update Procedure §4**

Replace `skills/ai-used-resume/SKILL.md:96-127` (the current Procedure §4) with:

```markdown
4. **Run extractors → aggregate.**

   ```bash
   uv run vibe-resume extract
   uv run vibe-resume status              # sanity-check per-source counts
   uv run vibe-resume aggregate           # → data/cache/_project_groups.json
   ```

4a. **(Default, uses subscription quota)** Emit + session-driven enrich.

   ```bash
   uv run vibe-resume enrich --locale <L>
   # → writes data/enrich_jobs/<persona-or-default>/<L>/manifest.json
   #   + one *.prompt.md per project group
   ```

   Then in the current Claude Code session:

   1. Read `data/enrich_jobs/<persona>/<L>/manifest.json`
   2. For each `status: pending` entry, read its `*.prompt.md`
   3. Produce strict YAML matching the schema the prompt requires
   4. Write to the entry's `output_path` (`NNN_<name>.yaml`)

   When all entries are done:

   ```bash
   uv run vibe-resume enrich --ingest --locale <L>
   # → merges *.yaml into _project_groups.<persona>.<L>.json
   ```

   Multi-locale runs are independent (per-locale subdir + per-locale cache):

   ```bash
   uv run vibe-resume enrich --locale en_US
   uv run vibe-resume enrich --locale zh_TW      # does NOT overwrite en_US
   # process both locales' yaml in session…
   uv run vibe-resume enrich --ingest --locale en_US
   uv run vibe-resume enrich --ingest --locale zh_TW
   uv run vibe-resume render --locale en_US      # reads _project_groups.default.en_US.json
   uv run vibe-resume render --locale zh_TW      # reads _project_groups.default.zh_TW.json
   ```

4b. **(Fallback for CI / non-interactive)** Spawn `claude -p` subprocess.

   ```bash
   uv run vibe-resume enrich --mode subprocess --locale <L>
   ```

   This bills against the Anthropic Agent SDK monthly quota pool (Pro $20 /
   Max 20x $200, separate from the Claude Code subscription quota — change
   effective 2026-06-15). The CLI prints a red warning at startup.

   `--mode rule-based` skips LLM entirely and uses heuristic summaries
   (works without any `claude` binary).

5. **Render.**
   …  (keep existing §5 unchanged)
```

- [ ] **Step 2: Update Quick Reference table**

In `skills/ai-used-resume/SKILL.md:54-67`, change the `Fresh pipeline` row to use the new two-step enrich:

```markdown
| Fresh pipeline | `uv run vibe-resume extract && uv run vibe-resume aggregate && uv run vibe-resume enrich --locale en_US` then process prompts in session, then `enrich --ingest --locale en_US && render -f all --locale en_US` |
```

(Or keep a shorter row pointing to §4a.)

- [ ] **Step 3: Remove the 互蓋 line from Pitfalls reference**

In `skills/ai-used-resume/references/troubleshooting.md`, find the bullet that says "enrich 會覆寫 _project_groups.json,所以 zh_TW → render → en_US enrich → render 的順序較安全" (or its English equivalent) and **delete it** — per-locale cache eliminates the hazard.

- [ ] **Step 4: Run skill-spec test**

```bash
uv run pytest tests/test_skill_spec.py -v
```

Expected: all pass (the test validates frontmatter + manifest version, not body content).

- [ ] **Step 5: Commit**

```bash
git add skills/ai-used-resume/SKILL.md skills/ai-used-resume/references/troubleshooting.md
git commit -m "docs(skill): document session-driven enrich §4a + remove stale 互蓋 pitfall"
```

---

## Task 11: troubleshooting.md — add 6/15 quota note

**Files:**
- Modify: `skills/ai-used-resume/references/troubleshooting.md`

- [ ] **Step 1: Read current content**

```bash
cat skills/ai-used-resume/references/troubleshooting.md
```

- [ ] **Step 2: Add new bullet after the existing `claude -p` line**

Find the line `- **\`claude -p\` is optional.**` (around line 13) and replace its short paragraph with:

```markdown
- **`claude -p` is optional but billed separately as of 2026-06-15.** The
  `--mode subprocess` path spawns `claude -p`, which bills against the
  Anthropic Agent SDK monthly quota pool (Pro $20 / Max 20x $200), not
  your Claude Code subscription. The default `--mode prompt` flow keeps
  everything inside the current Claude Code session (uses subscription
  quota). If `claude` is missing on PATH, `--mode subprocess` automatically
  falls back to `--mode rule-based`.
  ([Anthropic billing change](https://codersera.com/blog/anthropic-june-2026-billing-change-claude-code/))
```

- [ ] **Step 3: Commit**

```bash
git add skills/ai-used-resume/references/troubleshooting.md
git commit -m "docs(troubleshooting): note 2026-06-15 Agent SDK quota pool split"
```

---

## Task 12: READMEs × 4 — enrich section + 6/15 footnote

**Files:**
- Modify: `README.md` lines 36, 239, 603(approx, see Task 0's grep output)
- Modify: `README.zh-TW.md` lines 36, 215, 499
- Modify: `README.zh-CN.md` lines 36, 215, 499
- Modify: `README.ja.md` lines 36, 215, 499

- [ ] **Step 1: For each README, replace the privacy-table 行 with quota-aware text**

In `README.md:36` change:

```markdown
| **Privacy** | Fully local; `claude -p` headless; nothing leaves your machine | …
```

to:

```markdown
| **Privacy** | Fully local. Default mode keeps LLM work inside the Claude Code session (subscription quota); `--mode subprocess` spawns `claude -p` (Agent SDK quota pool, 2026-06-15 change). | …
```

Translate equivalently in the three localised READMEs (keep the link to Anthropic billing announcement in EN versions only — CJK readers can follow the SKILL.md cross-link).

- [ ] **Step 2: Update the `enrich` description line in each README**

In `README.md:239`:

```markdown
uv run vibe-resume enrich           # XYZ bullets — emits prompts for Claude Code session by default
```

Same translated treatment for the three localised versions.

- [ ] **Step 3: Update the architecture diagram comment**

In `README.md:603`:

```markdown
│   ├── enricher.py        # mode dispatcher: prompt (default) / subprocess / rule-based
```

Same for the localised versions.

- [ ] **Step 4: Commit**

```bash
git add README.md README.zh-TW.md README.zh-CN.md README.ja.md
git commit -m "docs(readme): note default enrich mode is now session-driven (0.4.0)"
```

---

## Task 13: CHANGELOG 0.4.0 entry + bump 6 version strings

**Files:**
- Modify: `CHANGELOG.md`(prepend a new `## [0.4.0]` block)
- Modify: `pyproject.toml:3`
- Modify: `skills/ai-used-resume/SKILL.md:7`
- Modify: `.claude-plugin/plugin.json:4`
- Modify: `.claude-plugin/marketplace.json:9, 19`
- Modify: `.codex-plugin/plugin.json:3`

- [ ] **Step 1: Write the CHANGELOG entry**

Prepend to `CHANGELOG.md` before any existing `## [Unreleased]` block:

```markdown
## [0.4.0] — 2026-05-27

### Breaking changes

- **`enrich` default mode changed.** Was: spawn `claude -p` per group
  (billed against Anthropic Agent SDK quota pool as of 2026-06-15).
  Now: emit `*.prompt.md` files to `data/enrich_jobs/<persona>/<locale>/`
  for the current Claude Code session to process (uses subscription
  quota). Process the prompts in your session, then run
  `vibe-resume enrich --ingest --locale <L>` to merge the YAML back.
  CI / non-interactive: opt back into the old path with
  `--mode subprocess` (the CLI prints a red warning explaining the
  billing implication). Background:
  https://codersera.com/blog/anthropic-june-2026-billing-change-claude-code/

- **Enriched cache is now per-locale.** The cache file
  `_project_groups.<persona>.json` became
  `_project_groups.<persona-or-default>.<locale>.json`. This eliminates
  the previous hazard where `enrich --locale zh_TW` then
  `enrich --locale en_US` would overwrite each other.

  **Migration:**
  ```bash
  rm data/cache/_project_groups.*.json   # delete 0.3.x enriched caches
  uv run vibe-resume enrich --locale <L>  # re-run for each locale you need
  uv run vibe-resume enrich --ingest --locale <L>
  ```

- **`company verify` mirrored the same three-mode pattern.** Default
  emits prompt + manifest to `data/verification_jobs/<key>_<date>/`;
  session writes `report.md`; `verify --ingest <key>` finalises it.
  `--mode subprocess` keeps the old `claude -p` behaviour.

- **`personas-compare` now requires `--locale`** (cache is per-locale).

### Added

- `core/enrich_jobs.py` — `EnrichJobManifest` + `emit_jobs` + `ingest_jobs`
- `data/enrich_jobs/` and `data/verification_jobs/` working-directory
  layout (both gitignored)
- `tests/fixtures/enrich_jobs_sample/` — reference manifest + prompt + yaml
  so new contributors can see the schema shape (the live working dir is
  gitignored)
- New test suites: `test_enrich_jobs.py`, `test_per_locale_cache.py`,
  `test_cli_enrich_modes.py`, `test_company_verify_jobs.py`

### Verified

- No sensitive data ever entered git history (audit covered `profile.yaml`,
  `data/cache/*`, `data/resume_history/*`, `data/reviews/*`, secret patterns,
  credential file extensions). Historical `config.yaml` content was example-
  grade with no PII.
```

- [ ] **Step 2: Bump all 6 version strings**

```bash
# 1. pyproject
sed -i '' 's/^version = "0\.3\.0"/version = "0.4.0"/' pyproject.toml

# 2. SKILL.md
sed -i '' 's/version: "0\.3\.0"/version: "0.4.0"/' skills/ai-used-resume/SKILL.md

# 3. claude-plugin plugin.json
sed -i '' 's/"version": "0\.3\.0"/"version": "0.4.0"/' .claude-plugin/plugin.json

# 4-5. claude-plugin marketplace.json (two occurrences)
sed -i '' 's/"version": "0\.3\.0"/"version": "0.4.0"/g' .claude-plugin/marketplace.json

# 6. codex-plugin plugin.json
sed -i '' 's/"version": "0\.3\.0"/"version": "0.4.0"/' .codex-plugin/plugin.json
```

Verify with:

```bash
grep -rn '"version"\|^version =\|^  version:' pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/ .codex-plugin/ | grep -E '0\.[0-9]+\.[0-9]+'
```

Expected: all show `0.4.0`.

- [ ] **Step 3: Run skill-spec test (enforces version consistency)**

```bash
uv run pytest tests/test_skill_spec.py -v
```

Expected: all pass.

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/
uv run ruff check .
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md \
        .claude-plugin/plugin.json .claude-plugin/marketplace.json \
        .codex-plugin/plugin.json
git commit -m "chore(release): bump version 0.3.0 → 0.4.0 + CHANGELOG"
```

---

## Task 14: Sample fixture for contributors

**Files:**
- Create: `tests/fixtures/enrich_jobs_sample/manifest.json`
- Create: `tests/fixtures/enrich_jobs_sample/001_sample.prompt.md`
- Create: `tests/fixtures/enrich_jobs_sample/001_sample.yaml`

- [ ] **Step 1: Create the manifest**

`tests/fixtures/enrich_jobs_sample/manifest.json`:

```json
{
  "version": 1,
  "created_at": "2026-05-27T12:00:00+00:00",
  "locale": "en_US",
  "persona": null,
  "tailor_keywords": null,
  "company": null,
  "level": null,
  "groups": [
    {
      "id": "001",
      "name": "sample-project",
      "prompt_path": "001_sample.prompt.md",
      "output_path": "001_sample.yaml",
      "status": "done"
    }
  ]
}
```

- [ ] **Step 2: Create a minimal prompt sample**

`tests/fixtures/enrich_jobs_sample/001_sample.prompt.md`:

```markdown
You are drafting resume bullets for a software engineer…

Project: sample-project
Path: (not on disk)
Timespan: 2026-01-01T00:00 -> 2026-02-01T00:00
Sessions: 5
AI sources observed: claude_code
Detected tech stack: FastAPI, PostgreSQL
…

Output strict YAML (no prose, no fences) with EXACTLY this shape:

summary: "<=150 chars English sentence stating role + stack + outcome>"
role_label: "<2-5 word role tag>"
achievements:
  - "<XYZ bullet, English, <=120 chars>"
tech_stack:
  - "<normalized tech name>"
keywords_for_ats:
  - "<ATS keyword>"
```

(This is a snippet — the live emitter writes the full prompt; the fixture is just a schema reference.)

- [ ] **Step 3: Create the matching yaml**

`tests/fixtures/enrich_jobs_sample/001_sample.yaml`:

```yaml
summary: "Built a sample backend service for fixture documentation purposes"
role_label: "Backend"
achievements:
  - "Designed FastAPI service with 1k qps throughput"
  - "Optimized pgvector index, cutting p95 latency from 300ms to 200ms"
tech_stack: ["FastAPI", "PostgreSQL", "pgvector"]
keywords_for_ats: ["RAG", "vector-search"]
```

- [ ] **Step 4: Reference the fixture from SKILL.md**

Append to `skills/ai-used-resume/SKILL.md` §4a (after the `Multi-locale` example):

```markdown
For a reference of what the manifest + prompt + yaml look like, see
`tests/fixtures/enrich_jobs_sample/`.
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/enrich_jobs_sample/ skills/ai-used-resume/SKILL.md
git commit -m "docs(fixtures): add enrich_jobs_sample schema reference"
```

---

## Task 15: Release ceremony

**Pre-flight gate**: do NOT run unless **the user has explicitly authorised pushing `main`** in the same turn (per `~/.claude/CLAUDE.md` and Claude Code's main-branch protection). The git identity switch is mandatory to avoid leaking the work account.

- [ ] **Step 1: Final verification**

```bash
uv run pytest tests/                # full suite
uv run ruff check .                 # lint
grep -rn '0\.3\.0' pyproject.toml .claude-plugin/ .codex-plugin/ skills/ai-used-resume/SKILL.md
```

Expected: tests + ruff green; the grep returns **nothing** (all 6 versions bumped).

- [ ] **Step 2: Switch git identity to easyvibecoding**

```bash
git config user.email easyvibecoding@users.noreply.github.com
git config user.name easyvibecoding
git config user.email   # verify
```

Expected: `easyvibecoding@users.noreply.github.com`.

- [ ] **Step 3: Tag the release**

```bash
git tag v0.4.0
git tag --list 'v0.*' --sort=-creatordate | head
```

Expected: `v0.4.0` appears at top.

- [ ] **Step 4: Push main + tag to easyvibecoding (REQUIRES USER AUTHORISATION)**

If — and only if — the user has explicitly said "push" / "推上去" in this turn:

```bash
PAT=$(security find-internet-password -s github.com -a easyvibecoding -w)
git -c 'credential.helper=' \
    -c "credential.helper=!f() { test \"\$1\" = get && { echo username=easyvibecoding; echo password=$PAT; }; }; f" \
    -c 'credential.useHttpPath=true' \
    push origin main --follow-tags
unset PAT
```

- [ ] **Step 5: Create GitHub release**

```bash
gh release create v0.4.0 \
  --title "v0.4.0 — session-driven enrich + per-locale cache" \
  --notes-file <(sed -n '/^## \[0.4.0\]/,/^## \[/{ /^## \[0\.[^4]/q; p; }' CHANGELOG.md)
```

Verify with:

```bash
gh release view v0.4.0
```

- [ ] **Step 6: Verify all four distribution channels**

```bash
# GitHub Releases
gh release list --limit 3

# Claude Code marketplace pulls automatically; users get it via /plugin update
# skills.sh registry reindexes from main HEAD (usually <1 hour)
echo "Wait ~10 min then check https://www.skills.sh/easyvibecoding/vibe-resume/ai-used-resume"
```

- [ ] **Step 7: Reset git identity back to the work default (avoid pollution)**

```bash
git config --unset user.email
git config --unset user.name
git config user.email   # should now fall back to the global ~/.gitconfig default
```

---

## Self-Review

✅ **Spec coverage:**
- §1 CLI shape → Tasks 5, 6, 9
- §2 directory structure → Tasks 1, 2, 9
- §3 schema (manifest + groups_path_for) → Tasks 1, 4
- §4 module split → Tasks 2, 3, 5
- §5 SKILL.md changes → Tasks 10, 14
- §6 render/review/personas-compare → Tasks 7, 8
- §7 error handling → Tasks 2, 3, 5, 9
- §8 backward compat + migration → Tasks 7 (render warning), 13 (CHANGELOG)
- §9 testing → Tasks 1-9 inline + Task 14 fixture
- §git audit → Task 13 CHANGELOG `### Verified` (no separate task — already done in spec phase)
- §distribution channels → Tasks 13, 15
- §release steps → Task 15

✅ **Placeholder scan:** no `TBD` / `appropriate error handling` / `etc.`.

✅ **Type consistency:** `EnrichJobEntry` / `EnrichJobManifest` shape consistent Tasks 1-3; `groups_path_for(persona, locale)` signature consistent Tasks 4-8; `mode: Literal["prompt", "subprocess", "rule-based"]` consistent Tasks 5-6.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-session-driven-enrich-plan.md`.**
