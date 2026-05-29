# Emphasis Lever Implementation Plan (#38 SP3 / 0.10.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加一個 file-based emphasis lever：`vibe-resume emphasis "<intent>"` 寫可編輯的 `_emphasis.yaml`，enrich 把它當最高優先 bias block、render 用 spotlight/demote 調整排序；深度隱含於重跑哪個階段。

**Architecture:** 新模組 `core/emphasis.py`（`EmphasisRecord` + load/write/clear + `rank_delta` + `emphasis_block`）。`load_emphasis(cfg)` 同時看檔案存在與 `cfg.emphasis.enabled`，故 `--no-emphasis` 只需在 cli 把 `cfg["emphasis"]["enabled"]=False`（cfg 已傳到 `_render_md`/`enrich_groups`/`_do_emit`，無需多層 threading）。enricher `_build_prompt` 加 `emphasis` 參數，append `EMPHASIS_BLOCK` 於 company/contribution 之後。renderer 用 `_sort_groups(groups, emphasis)`（`_rank_score + rank_delta`）。

**Tech Stack:** Python 3.12+, Pydantic v2, pyyaml, click, pytest, ruff, uv。Spec: `docs/superpowers/specs/2026-05-29-emphasis-lever-design.md`。

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/emphasis.py` | EmphasisRecord + load/write/clear + rank_delta + emphasis_block | Create |
| `src/vibe_resume/core/enricher.py` | `_build_prompt(emphasis=)` + EMPHASIS_BLOCK；`enrich_groups`/`_do_emit` 讀 load_emphasis(cfg) | Modify |
| `src/vibe_resume/core/enrich_jobs.py` | `emit_jobs(emphasis=)` 透傳 `_build_prompt` | Modify |
| `src/vibe_resume/render/renderer.py` | `_sort_groups(groups, emphasis)` + `_render_md` 使用 | Modify |
| `src/vibe_resume/cli.py` | `emphasis` 指令；enrich/render `--no-emphasis` | Modify |
| `config.example.yaml` | `emphasis:` 區塊 | Modify |
| `tests/test_emphasis.py` | model/load/write/clear/rank_delta/block | Create |
| `tests/test_enricher.py` | `_build_prompt` 含 EMPHASIS_BLOCK | Modify |
| `tests/test_render_helpers.py` | `_sort_groups` spotlight/demote 排序 | Modify |
| `tests/test_emphasis_cli.py` | `emphasis` set/clear + `--no-emphasis` | Create |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.10.0 bump | Modify |

**Execution order:** Task 1（emphasis 模組）→ Task 2（enrich）→ Task 3（render）→ Task 4（CLI+config）→ Task 5（release）。

---

### Task 1: emphasis 模組

**Files:**
- Create: `src/vibe_resume/core/emphasis.py`
- Test: `tests/test_emphasis.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_emphasis.py`：

```python
from vibe_resume.core import emphasis as em
from vibe_resume.core.emphasis import EmphasisRecord


def test_record_defaults():
    r = EmphasisRecord()
    assert r.intent == "" and r.keywords == [] and r.spotlight == [] and r.demote == []


def test_rank_delta_spotlight_demote_none():
    r = EmphasisRecord(spotlight=["A"], demote=["B"])
    assert em.rank_delta("A", r) == em._BOOST
    assert em.rank_delta("B", r) == -em._BOOST
    assert em.rank_delta("C", r) == 0
    assert em.rank_delta("A", None) == 0


def test_emphasis_block_contains_intent_keywords():
    r = EmphasisRecord(intent="security focus", keywords=["MCP", "guardrails"],
                       bias_instruction="Lead with the trade-off.")
    blk = em.emphasis_block(r)
    assert "security focus" in blk
    assert "MCP" in blk and "guardrails" in blk
    assert "Lead with the trade-off." in blk


def test_write_then_load_and_carry_forward(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    r = em.write_emphasis("first intent")
    assert r.intent == "first intent"
    # user edits keywords/spotlight by hand
    import yaml
    data = yaml.safe_load(em.EMPHASIS_PATH.read_text())
    data["keywords"] = ["agents"]
    data["spotlight"] = ["proj-x"]
    em.EMPHASIS_PATH.write_text(yaml.safe_dump(data))
    # re-running emphasis updates intent but keeps edits
    r2 = em.write_emphasis("second intent")
    assert r2.intent == "second intent"
    assert r2.keywords == ["agents"]
    assert r2.spotlight == ["proj-x"]


def test_load_respects_config_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    em.write_emphasis("x")
    assert em.load_emphasis({}) is not None
    assert em.load_emphasis({"emphasis": {"enabled": False}}) is None


def test_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    em.write_emphasis("x")
    assert em.clear_emphasis() is True
    assert em.load_emphasis({}) is None
    assert em.clear_emphasis() is False        # already gone
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_emphasis.py -v`
Expected: FAIL（`emphasis` 模組不存在）。

- [ ] **Step 3: 實作**

Create `src/vibe_resume/core/emphasis.py`：

```python
"""Emphasis lever: a file-based重點控制 that rides the enrich bias stack and
the render ranking. `_emphasis.yaml` is human-editable; enrich injects it as
the highest-priority bias block, render boosts/penalizes ranked groups."""
from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel

from vibe_resume.core.paths import user_root

EMPHASIS_PATH = user_root() / "data" / "cache" / "_emphasis.yaml"
_BOOST = 10_000   # dominates _rank_score (sessions + achievements*5 + breadth*2)


class EmphasisRecord(BaseModel):
    version: int = 1
    intent: str = ""
    keywords: list[str] = []
    bias_instruction: str = ""
    spotlight: list[str] = []
    demote: list[str] = []


def load_emphasis(cfg: dict[str, Any] | None = None) -> EmphasisRecord | None:
    """Return the active emphasis, or None when disabled / absent / unreadable.
    `cfg.emphasis.enabled = false` (or the --no-emphasis flag, which sets it)
    suppresses the lever without deleting the file."""
    if cfg is not None and not cfg.get("emphasis", {}).get("enabled", True):
        return None
    if not EMPHASIS_PATH.exists():
        return None
    try:
        return EmphasisRecord(**(yaml.safe_load(EMPHASIS_PATH.read_text()) or {}))
    except Exception:
        return None


def write_emphasis(intent: str) -> EmphasisRecord:
    """Set `intent`, carry forward any hand-edited keywords/spotlight/demote."""
    existing = None
    if EMPHASIS_PATH.exists():
        try:
            existing = EmphasisRecord(**(yaml.safe_load(EMPHASIS_PATH.read_text()) or {}))
        except Exception:
            existing = None
    rec = existing or EmphasisRecord()
    rec.intent = intent
    EMPHASIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMPHASIS_PATH.write_text(yaml.safe_dump(rec.model_dump(), sort_keys=False, allow_unicode=True))
    return rec


def clear_emphasis() -> bool:
    if EMPHASIS_PATH.exists():
        EMPHASIS_PATH.unlink()
        return True
    return False


def rank_delta(name: str, emphasis: EmphasisRecord | None) -> int:
    if emphasis is None:
        return 0
    if name in emphasis.spotlight:
        return _BOOST
    if name in emphasis.demote:
        return -_BOOST
    return 0


def emphasis_block(emphasis: EmphasisRecord) -> str:
    kw = ", ".join(emphasis.keywords) if emphasis.keywords else "(none)"
    return (
        "\n\nHIGHEST-PRIORITY EMPHASIS — the candidate wants this résumé to "
        f"foreground:\n{emphasis.intent}\n"
        f"Surface these themes/keywords where the raw activity supports them "
        f"(never invent): {kw}\n"
        f"{emphasis.bias_instruction}\n"
        "This emphasis overrides earlier framing on tie-breaks; do not fabricate "
        "to satisfy it.\n"
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_emphasis.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/emphasis.py tests/test_emphasis.py
git commit -m "feat(emphasis): EmphasisRecord + load/write/clear + rank_delta + block (#38)"
```

---

### Task 2: enrich 注入 EMPHASIS_BLOCK

**Files:**
- Modify: `src/vibe_resume/core/enricher.py`（`_build_prompt` 簽名+block；`enrich_groups`/`_do_emit` 讀 emphasis）
- Modify: `src/vibe_resume/core/enrich_jobs.py`（`emit_jobs` 透傳）
- Test: `tests/test_enricher.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_enricher.py` 追加：

```python
def test_build_prompt_includes_emphasis_block_last():
    from vibe_resume.core.emphasis import EmphasisRecord
    g = _many_act_group(3)
    em = EmphasisRecord(intent="security + agents", keywords=["MCP"],
                        bias_instruction="Lead with the trade-off.")
    p = _build_prompt(g, emphasis=em)
    assert "HIGHEST-PRIORITY EMPHASIS" in p
    assert "security + agents" in p and "MCP" in p


def test_build_prompt_no_emphasis_block_when_absent():
    g = _many_act_group(3)
    assert "HIGHEST-PRIORITY EMPHASIS" not in _build_prompt(g)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_enricher.py -k emphasis -v`
Expected: FAIL（`_build_prompt` 無 `emphasis` 參數 → TypeError）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/enricher.py` import 區加：

```python
from vibe_resume.core.emphasis import EmphasisRecord, emphasis_block, load_emphasis
```

`_build_prompt` 簽名加參數（在 `char_budget: int = 200,` 之後）：

```python
    emphasis: EmphasisRecord | None = None,
```

在 `_build_prompt` 的 CONTRIBUTION_BLOCK 區塊之後、`return body` 之前加：

```python
    if emphasis is not None and (emphasis.intent or emphasis.keywords or emphasis.bias_instruction):
        body += emphasis_block(emphasis)
    return body
```

在 `enrich_groups`，於 `input_char_budget` 解析行之後加：

```python
    emphasis = load_emphasis(cfg)
```

並在該函式的 `_build_prompt(...)` 呼叫（enrich_groups 內，含 `char_budget=input_char_budget,`）加一行 `emphasis=emphasis,`。

在 `_do_emit`，於 `_enr = cfg.get("enrich", {})` 之後加 `emphasis = load_emphasis(cfg)`，並在 `emit_jobs(...)` 呼叫加 `emphasis=emphasis,`。

在 `src/vibe_resume/core/enrich_jobs.py`，`emit_jobs` 簽名加（在 `input_char_budget: int = 200,` 之後）：

```python
    emphasis: "EmphasisRecord | None" = None,
```

並在 `emit_jobs` 內的 `_build_prompt(...)` 呼叫（含 `char_budget=input_char_budget,`）加 `emphasis=emphasis,`。`EmphasisRecord` 以字串註解避免額外 import；若 ruff 要求，於檔頂 `from vibe_resume.core.emphasis import EmphasisRecord`。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_enricher.py tests/test_enrich_jobs.py -v`
Expected: PASS（新 emphasis 測試 + 既有 window/contributed/emit 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py src/vibe_resume/core/enrich_jobs.py tests/test_enricher.py
git commit -m "feat(enricher): inject highest-priority EMPHASIS_BLOCK from _emphasis.yaml (#38)"
```

---

### Task 3: render spotlight/demote 排序

**Files:**
- Modify: `src/vibe_resume/render/renderer.py`（加 `_sort_groups`；`_render_md` 使用）
- Test: `tests/test_render_helpers.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_render_helpers.py` 追加：

```python
def test_sort_groups_spotlight_floats_demote_sinks():
    from vibe_resume.core.emphasis import EmphasisRecord
    from vibe_resume.core.schema import ProjectGroup
    from vibe_resume.render.renderer import _sort_groups

    def g(name, sessions):
        return ProjectGroup(name=name, first_activity="2026-01-01T00:00:00+00:00",
                            last_activity="2026-01-01T00:00:00+00:00", total_sessions=sessions)

    big = g("big", 100)       # high _rank_score
    small = g("small", 1)     # low _rank_score
    em = EmphasisRecord(spotlight=["small"], demote=["big"])
    ordered = [x.name for x in _sort_groups([big, small], em)]
    assert ordered == ["small", "big"]      # spotlight floats above, demote sinks


def test_sort_groups_no_emphasis_is_rank_order():
    from vibe_resume.core.schema import ProjectGroup
    from vibe_resume.render.renderer import _sort_groups

    def g(name, sessions):
        return ProjectGroup(name=name, first_activity="2026-01-01T00:00:00+00:00",
                            last_activity="2026-01-01T00:00:00+00:00", total_sessions=sessions)

    ordered = [x.name for x in _sort_groups([g("a", 1), g("b", 100)], None)]
    assert ordered == ["b", "a"]            # plain _rank_score order
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_render_helpers.py -k sort_groups -v`
Expected: FAIL（`_sort_groups` 未定義）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/render/renderer.py`，於 `_rank_score` 之後加：

```python
def _sort_groups(groups, emphasis):
    """Rank groups by _rank_score, with emphasis spotlight/demote applied as a
    dominating delta so spotlighted groups float into the detailed top-N and
    demoted ones sink to one-liners."""
    from vibe_resume.core.emphasis import rank_delta

    return sorted(groups, key=lambda g: _rank_score(g) + rank_delta(g.name, emphasis), reverse=True)
```

在 `_render_md` import 區（或函式內）加載 emphasis，並把：

```python
    groups = load_groups(persona=persona, locale=locale_key)
    groups = sorted(groups, key=_rank_score, reverse=True)
```

改為：

```python
    from vibe_resume.core.emphasis import load_emphasis

    groups = load_groups(persona=persona, locale=locale_key)
    groups = _sort_groups(groups, load_emphasis(cfg))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_render_helpers.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/render/renderer.py tests/test_render_helpers.py
git commit -m "feat(render): emphasis spotlight/demote reranking via _sort_groups (#38)"
```

---

### Task 4: CLI `emphasis` 指令 + `--no-emphasis` + config

**Files:**
- Modify: `src/vibe_resume/cli.py`（`emphasis` 指令；enrich/render `--no-emphasis`）
- Modify: `config.example.yaml`
- Test: `tests/test_emphasis_cli.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_emphasis_cli.py`：

```python
from click.testing import CliRunner

from vibe_resume.cli import cli
from vibe_resume.core import emphasis as em


def test_emphasis_set_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    runner = CliRunner()
    r = runner.invoke(cli, ["emphasis", "foreground security work"])
    assert r.exit_code == 0, r.output
    assert em.EMPHASIS_PATH.exists()
    assert em.load_emphasis({}).intent == "foreground security work"

    r2 = runner.invoke(cli, ["emphasis", "--clear"])
    assert r2.exit_code == 0, r2.output
    assert not em.EMPHASIS_PATH.exists()


def test_emphasis_show_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    runner = CliRunner()
    r = runner.invoke(cli, ["emphasis"])
    assert r.exit_code == 0
    assert "no emphasis" in r.output.lower()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_emphasis_cli.py -v`
Expected: FAIL（無 `emphasis` 指令）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/cli.py`，`curate` 指令之後加：

```python
@cli.command()
@click.argument("intent", required=False)
@click.option("--clear", "clear_", is_flag=True, default=False, help="Remove _emphasis.yaml")
@click.pass_context
def emphasis(ctx: click.Context, intent: str | None, clear_: bool) -> None:
    """Set a free-text emphasis ('foreground my security work'); edit the
    generated _emphasis.yaml to add keywords/spotlight/demote. Re-run `render`
    for a light re-rank, or `enrich` for a deep bias-rewrite."""
    from vibe_resume.core.aggregator import load_groups
    from vibe_resume.core.emphasis import clear_emphasis, load_emphasis, write_emphasis

    if clear_:
        click.echo("cleared _emphasis.yaml" if clear_emphasis() else "no _emphasis.yaml to clear")
        return
    if intent:
        rec = write_emphasis(intent)
        click.echo(f"emphasis set: {rec.intent}")
        names = [g.name for g in load_groups()]
        if names:
            click.echo("group names (for spotlight/demote): " + ", ".join(names[:30]))
        click.echo("edit _emphasis.yaml → re-run `render` (light) or `enrich` (deep).")
        return
    cur = load_emphasis({})
    click.echo(f"intent: {cur.intent}\nkeywords: {cur.keywords}\nspotlight: {cur.spotlight}\ndemote: {cur.demote}"
               if cur else "no emphasis set")
```

在 enrich 指令（`def enrich(...)`）與 render 指令（`def render(...)`）各加一個 option（放在其他 `@click.option` 之間）：

```python
@click.option("--no-emphasis", "no_emphasis", is_flag=True, default=False,
              help="Ignore _emphasis.yaml for this run")
```

並在兩個函式簽名加 `no_emphasis: bool` 參數；在各自函式體開頭（取得 `cfg = ctx.obj["config"]` 之後，或 enrich 的 `run_enricher(ctx.obj["config"], ...)` 之前）加：

```python
    if no_emphasis:
        ctx.obj["config"].setdefault("emphasis", {})["enabled"] = False
```

（enrich 指令目前直接傳 `ctx.obj["config"]` 給 `run_enricher`；render 經 `cfg = ctx.obj["config"]`。兩者都是同一 dict，設定 `enabled=False` 後 `load_emphasis(cfg)` 回 None。）

在 `config.example.yaml`，`curate:` 區塊之後加：

```yaml
emphasis:
  enabled: true     # enrich/render honor _emphasis.yaml when present (--no-emphasis overrides)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_emphasis_cli.py -v && uv run pytest tests/ -q`
Expected: PASS（emphasis CLI + 全套無回歸）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/cli.py config.example.yaml tests/test_emphasis_cli.py
git commit -m "feat(cli): emphasis command + --no-emphasis flag + config block (#38)"
```

---

### Task 5: Release 0.10.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.9.0 字串**

Run: `grep -rn "0\.9\.0" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處。

- [ ] **Step 2: 全部改為 0.10.0 並刷新 lockfile**

逐處 `0.9.0` → `0.10.0`，然後 `uv lock`。
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.10.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（em-dash）：

```markdown
## [0.10.0] — 2026-05-29

### Added

- **`emphasis` lever** — `vibe-resume emphasis "<intent>"` writes an editable
  `_emphasis.yaml` (intent / keywords / bias_instruction / spotlight / demote)
  that re-shapes output to a chosen focus (#38). `enrich` injects it as the
  highest-priority bias block; `render` boosts `spotlight` groups into the
  detailed top-N and sinks `demote` groups to one-liners. Depth is implicit:
  re-run `render` for a light re-rank (no LLM) or `enrich` for a deep
  bias-rewrite. Hand-edited keywords/spotlight/demote carry forward when the
  intent changes; `--no-emphasis` / `emphasis --clear` disable it. New
  `emphasis:` config block. Completes #38 (the curate gate shipped in 0.9.0).
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.9.0 → 0.10.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-emphasis-lever-design.md`）：
- EmphasisRecord + load/write/clear + rank_delta + emphasis_block → Task 1。✓
- `emphasis "<text>"` 設 intent + carry-forward + 印 group 清單/提示；`--clear`；無參數印目前 → Task 4 + Task 1。✓
- enrich 注入 EMPHASIS_BLOCK 最高優先（company/contribution 之後）→ Task 2。✓
- render spotlight/demote rank（加權浮上/沉下）→ Task 3 `_sort_groups`。✓
- `--no-emphasis`（經 cfg.emphasis.enabled）+ config 區塊 → Task 4 + Task 1 `load_emphasis(cfg)`。✓
- 深度隱含（render=light / enrich=deep，無新旗標）→ 自然由 Task 2/3 分屬 enrich/render 達成。✓
- 非破壞 / never invent → Task 1 emphasis_block 措辭 + sidecar 檔。✓
- release 0.10.0 → Task 5。✓

**2. Placeholder scan:** 無 TBD/TODO；每個 code step 有完整程式碼。✓

**3. Type consistency:**
- `load_emphasis(cfg=None) -> EmphasisRecord | None`：Task 1 定義；Task 2（enrich_groups/_do_emit）、Task 3（_render_md）、Task 4（cli emphasis show）一致呼叫。✓
- `rank_delta(name, emphasis) -> int` / `emphasis_block(emphasis) -> str` / `write_emphasis(intent)` / `clear_emphasis() -> bool`：Task 1 定義，Task 3/4 一致。✓
- `_build_prompt(..., emphasis: EmphasisRecord | None = None)`：Task 2 定義；enrich_groups 與 emit_jobs 呼叫端一致加 `emphasis=`。✓
- `emit_jobs(..., emphasis=None)`：Task 2 定義；`_do_emit` 呼叫一致。✓
- `_sort_groups(groups, emphasis)`：Task 3 定義；`_render_md` 一致使用。✓
- `EMPHASIS_PATH`：Task 1 模組常數，測試以 monkeypatch 覆寫（Task 1/4）。✓
- `_BOOST`：Task 1 常數，Task 1/3 測試一致引用。✓
