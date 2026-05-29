# Agent Skills + MCP Competency Signal Implementation Plan (#43 / 0.11.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface Agent Skills + MCP competency (authored vs used) as a structured, quantified `AgenticSignals` field on each ProjectGroup, plus a factual enrich hint — replacing the generic `agent-tooling %` collapse.

**Architecture:** New `AgenticSignals` pydantic sub-model on `ProjectGroup` (the shared surface the whole competency epic extends). claude_code/codex capture used-skill names (`Base directory for this skill:`) into `extra["skills_used"]` via a shared `skill_uses_in` helper. The aggregator computes `agentic_signals` per group from existing `files_touched` (skills authored/published, mcp authored), `extra["skills_used"]` (skills used), and `tool_histogram`/`keywords` (`mcp__<server>` used). The enricher appends a factual `AGENTIC_SIGNALS_BLOCK` when present (full senior rubric is #47).

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, ruff, uv. Spec: `docs/superpowers/specs/2026-05-29-agentic-skills-mcp-signal-design.md`.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/schema.py` | `AgenticSignals` model + `ProjectGroup.agentic_signals` | Modify |
| `src/vibe_resume/extractors/base.py` | `skill_uses_in(text)` helper | Modify |
| `src/vibe_resume/extractors/local/claude_code.py` | capture `extra["skills_used"]` | Modify |
| `src/vibe_resume/extractors/local/codex.py` | capture `extra["skills_used"]` | Modify |
| `src/vibe_resume/core/aggregator.py` | `_mcp_server` + `_agentic_signals` + group-loop wiring | Modify |
| `src/vibe_resume/core/enricher.py` | `AGENTIC_SIGNALS_BLOCK` in `_build_prompt` | Modify |
| `tests/test_schema.py` | AgenticSignals defaults/roundtrip | Modify |
| `tests/test_extractors_base.py` | `skill_uses_in` | Modify |
| `tests/test_extractors.py` | claude_code/codex skills_used capture | Modify |
| `tests/test_aggregator.py` | `_agentic_signals` sources | Modify |
| `tests/test_enricher.py` | AGENTIC_SIGNALS_BLOCK | Modify |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.11.0 bump | Modify |

**Execution order:** Task 1 (schema) → Task 2 (base helper) → Task 3 (extractors) → Task 4 (aggregator) → Task 5 (enricher) → Task 6 (release).

---

### Task 1: `AgenticSignals` model + `ProjectGroup.agentic_signals`

**Files:**
- Modify: `src/vibe_resume/core/schema.py` (add model before `ProjectGroup`; add field after `merge_evidence`)
- Test: `tests/test_schema.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_schema.py` 追加：

```python
def test_agentic_signals_defaults_and_group_field():
    from vibe_resume.core.schema import AgenticSignals, ProjectGroup
    s = AgenticSignals()
    assert s.skills_authored == [] and s.skills_used == [] and s.mcp_servers_used == []
    assert s.skills_published is False and s.mcp_authored is False
    g = ProjectGroup(name="x", first_activity="2026-01-01T00:00:00+00:00",
                     last_activity="2026-01-01T00:00:00+00:00", total_sessions=1)
    assert g.agentic_signals is None
    g.agentic_signals = AgenticSignals(skills_authored=["foo"], mcp_servers_used=["browser"])
    back = ProjectGroup(**g.model_dump(mode="json"))
    assert back.agentic_signals.skills_authored == ["foo"]
    assert back.agentic_signals.mcp_servers_used == ["browser"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schema.py::test_agentic_signals_defaults_and_group_field -v`
Expected: FAIL (`AgenticSignals` not importable).

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/schema.py`，於 `class ProjectGroup(BaseModel):` 定義**之前**加入：

```python
class AgenticSignals(BaseModel):
    """Structured agentic-competency signals derived from raw activity.

    Shared surface for the AI-proficiency epic — later issues add fields
    (SDD/TDD #44, orchestration #48). All optional/defaulted for back-compat.
    """

    skills_authored: list[str] = Field(default_factory=list)
    skills_published: bool = False
    skills_used: list[str] = Field(default_factory=list)
    mcp_servers_used: list[str] = Field(default_factory=list)
    mcp_authored: bool = False
```

在 `ProjectGroup` 內，`merge_evidence` 欄位之後加入：

```python
    agentic_signals: "AgenticSignals | None" = Field(
        default=None,
        description="Agent Skills / MCP / methodology competency signals (author vs use)",
    )
```

（`AgenticSignals` 定義在 `ProjectGroup` 之前，字串註解非必需，但保留引號可避免前置順序疑慮；`Field` 已 import。）

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/schema.py tests/test_schema.py
git commit -m "feat(schema): AgenticSignals model + ProjectGroup.agentic_signals (#43)"
```

---

### Task 2: `skill_uses_in` helper

**Files:**
- Modify: `src/vibe_resume/extractors/base.py`
- Test: `tests/test_extractors_base.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_extractors_base.py` 的 base import 行加入 `skill_uses_in`，並追加：

```python
def test_skill_uses_in_extracts_basenames():
    text = ("Base directory for this skill: /Users/me/.claude/skills/foo\n"
            "...\nBase directory for this skill: /x/y/bar/\n")
    assert skill_uses_in(text) == ["foo", "bar"]


def test_skill_uses_in_none_when_absent():
    assert skill_uses_in("just a normal prompt") == []
    assert skill_uses_in("") == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_extractors_base.py -k skill_uses_in -v`
Expected: FAIL (`skill_uses_in` not defined).

- [ ] **Step 3: 實作**

在 `src/vibe_resume/extractors/base.py` import 區加 `import re`，並加入：

```python
_SKILL_BASE_RE = re.compile(r"Base directory for this skill:\s*(\S+)")


def skill_uses_in(text: str) -> list[str]:
    """Skill names (basename of the announced base dir) found in session text,
    e.g. 'Base directory for this skill: …/skills/foo' → 'foo'."""
    return [m.rstrip("/").split("/")[-1] for m in _SKILL_BASE_RE.findall(text or "")]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_extractors_base.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/base.py tests/test_extractors_base.py
git commit -m "feat(extractors): skill_uses_in helper for session skill-usage marker (#43)"
```

---

### Task 3: claude_code + codex capture `skills_used`

**Files:**
- Modify: `src/vibe_resume/extractors/local/claude_code.py`, `src/vibe_resume/extractors/local/codex.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_extractors.py` 追加：

```python
def test_claude_code_captures_skills_used(tmp_path, monkeypatch):
    import vibe_resume.extractors.local.claude_code as cc

    rows = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z",
             "message": {"content": "Base directory for this skill: /x/skills/foo\ndo it"}},
            {"type": "user", "timestamp": "2026-01-01T00:01:00Z",
             "message": {"content": "normal follow-up"}}]
    _write_session(tmp_path, rows)
    monkeypatch.setattr(cc, "git_identity", lambda path, cache=None: (None, None))
    acts = cc.extract({"extractors": {"claude_code": {"path": str(tmp_path)}}})
    assert acts[0].extra["skills_used"] == ["foo"]


def test_codex_captures_skills_used(tmp_path, monkeypatch):
    import vibe_resume.extractors.local.codex as cx

    rows = [{"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z",
             "payload": {"cwd": "/proj", "id": "s1"}},
            {"type": "response_item", "timestamp": "2026-01-01T00:01:00Z",
             "payload": {"type": "message", "role": "user",
                         "content": "Base directory for this skill: /x/skills/bar\ngo"}}]
    f = tmp_path / "rollout-2026-01-01-uuid.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(cx, "git_identity", lambda path, cache=None: (None, None))
    acts = cx.extract({"extractors": {"codex": {"path": str(tmp_path)}}})
    assert acts[0].extra["skills_used"] == ["bar"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_extractors.py -k "captures_skills_used" -v`
Expected: FAIL (no `skills_used` key).

- [ ] **Step 3: 實作**

**claude_code.py:**
- import 改：`from vibe_resume.extractors.base import git_identity, iter_jsonl, sample_spread, skill_uses_in`
- `_process_session` 加累積器（與其他累積器並列）：`skills_used: set[str] = set()`
- 在 user 分支算出 `txt` 後（`if etype == "user":` 區塊內，filter 之外）加入：

```python
            if txt:
                skills_used.update(skill_uses_in(txt))
```

放在 `if txt and not txt.startswith("<")...` 之前（marker 常在被 filter 的注入內容裡，要在 filter 前掃）。
- 在 `extra` 建好（git_remote/toplevel 之後）加入：

```python
    if skills_used:
        extra["skills_used"] = sorted(skills_used)
```

**codex.py:**
- import 改：`from vibe_resume.extractors.base import git_identity, iter_jsonl, sample_spread, skill_uses_in`
- `_process_session` 加 `skills_used: set[str] = set()`
- 在 message 分支算出 `txt` 後（filter 之前）加入：

```python
            if txt:
                skills_used.update(skill_uses_in(txt))
```

- 在 `extra` 建好（git_remote/toplevel 之後）加入：

```python
    if skills_used:
        extra["skills_used"] = sorted(skills_used)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_extractors.py -k "skills_used or claude_code or codex" -v`
Expected: PASS（新測試 + 既有 claude_code/codex 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/claude_code.py src/vibe_resume/extractors/local/codex.py tests/test_extractors.py
git commit -m "feat(extractors): capture used Agent Skills (skills_used) from session markers (#43)"
```

---

### Task 4: aggregator `_agentic_signals` + `_mcp_server`

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py` (helpers + import + group-loop wiring)
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_aggregator.py` 把 import 加 `_agentic_signals`、`_mcp_server` 與 `AgenticSignals`（從 schema）。追加：

```python
from vibe_resume.core.aggregator import _agentic_signals, _mcp_server


def test_mcp_server_extraction():
    assert _mcp_server("mcp__browser__click") == "browser"
    assert _mcp_server("mcp__db__query") == "db"
    assert _mcp_server("Edit") is None
    assert _mcp_server("mcp__only") is None


def _act_sig(files=None, tool_hist=None, keywords=None, skills_used=None):
    extra = {}
    if tool_hist is not None:
        extra["tool_histogram"] = tool_hist
    if skills_used is not None:
        extra["skills_used"] = skills_used
    return Activity(source=Source.CLAUDE_CODE, session_id="s",
                    timestamp_start="2026-01-01T00:00:00+00:00",
                    files_touched=files or [], keywords=keywords or [], extra=extra)


def test_agentic_signals_authored_published_and_mcp_used():
    acts = [_act_sig(files=["skills/foo/SKILL.md", ".claude-plugin/plugin.json"],
                     tool_hist={"mcp__browser__click": 3, "mcp__db__query": 1, "Edit": 5})]
    sig = _agentic_signals(acts, "myrepo")
    assert sig.skills_authored == ["foo"]
    assert sig.skills_published is True
    assert sig.mcp_servers_used == ["browser", "db"]


def test_agentic_signals_skills_used_union_and_mcp_authored():
    acts = [_act_sig(skills_used=["a"]),
            _act_sig(skills_used=["b", "a"], files=["src/foo_mcp_server.py"])]
    sig = _agentic_signals(acts, "r")
    assert sig.skills_used == ["a", "b"]
    assert sig.mcp_authored is True


def test_agentic_signals_none_when_empty():
    assert _agentic_signals([_act_sig(files=["src/main.py"])], "r") is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_aggregator.py -k "mcp_server or agentic_signals" -v`
Expected: FAIL (`_agentic_signals` / `_mcp_server` undefined).

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/aggregator.py`：

import 區把 schema import 加 `AgenticSignals`：

```python
from vibe_resume.core.schema import Activity, AgenticSignals, ProjectGroup, Source
```

在 `_reconcile_local_projects` 之後（或 `_significance` 附近）加入：

```python
_MCP_SERVER_RE = re.compile(r"^mcp__([^_]+(?:_[^_]+)*)__")
_PLUGIN_MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json",
                     ".claude-plugin/marketplace.json")
_MCP_SERVER_FILE_RE = re.compile(r"mcp[_-]?server.*\.py$")


def _mcp_server(tool_name: str) -> str | None:
    """`mcp__<server>__<tool>` → `<server>`; non-MCP tool names → None."""
    if not tool_name.startswith("mcp__"):
        return None
    parts = tool_name.split("__")
    return parts[1] if len(parts) >= 3 and parts[1] else None


def _agentic_signals(acts: list[Activity], group_name: str) -> AgenticSignals | None:
    """Derive Agent Skills / MCP competency signals from a group's activities.
    Authoring from files_touched; usage from skills_used + tool_histogram/keywords."""
    authored: list[str] = []
    published = False
    mcp_authored = False
    used: set[str] = set()
    servers: set[str] = set()
    for a in acts:
        for f in a.files_touched or []:
            fl = f.lower()
            if fl.endswith("/skill.md") or fl == "skill.md":
                parts = f.rstrip("/").split("/")
                name = parts[-2] if len(parts) >= 2 else group_name
                if name and name not in authored:
                    authored.append(name)
            m = re.search(r"(?:^|/)skills/([^/]+)/", f)
            if m and m.group(1) not in authored:
                authored.append(m.group(1))
            if any(mf in fl for mf in _PLUGIN_MANIFESTS):
                published = True
            if "fastmcp" in fl or _MCP_SERVER_FILE_RE.search(fl):
                mcp_authored = True
        used.update((a.extra or {}).get("skills_used") or [])
        names = list((a.extra or {}).get("tool_histogram") or {}) + list(a.keywords or [])
        for nm in names:
            srv = _mcp_server(nm)
            if srv:
                servers.add(srv)
    if not (authored or published or used or servers or mcp_authored):
        return None
    return AgenticSignals(
        skills_authored=authored,
        skills_published=published,
        skills_used=sorted(used),
        mcp_servers_used=sorted(servers),
        mcp_authored=mcp_authored,
    )
```

在 `aggregate_from_cache` 的 group-building loop，把 `ProjectGroup(...)` 建構子加一個 kwarg（display_name 已先算出）：

```python
            metrics=project_metrics,
            canonical_key=prov.get("canonical_key"),
            merged_from=prov.get("merged_from", []),
            merge_evidence=prov.get("evidence"),
            agentic_signals=_agentic_signals(acts, display_name),
        )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_aggregator.py -v`
Expected: PASS（新測試 + 既有全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): compute AgenticSignals per group (skills/MCP author vs use) (#43)"
```

---

### Task 5: enricher `AGENTIC_SIGNALS_BLOCK`

**Files:**
- Modify: `src/vibe_resume/core/enricher.py`
- Test: `tests/test_enricher.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_enricher.py` 追加：

```python
def test_build_prompt_includes_agentic_signals_block():
    from vibe_resume.core.schema import AgenticSignals
    g = _many_act_group(3)
    g.agentic_signals = AgenticSignals(skills_authored=["foo"], skills_published=True,
                                       mcp_servers_used=["browser", "db"])
    p = _build_prompt(g)
    assert "AGENTIC SIGNALS" in p
    assert "foo" in p and "browser" in p and "db" in p


def test_build_prompt_no_agentic_block_when_absent():
    assert "AGENTIC SIGNALS" not in _build_prompt(_many_act_group(3))
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_enricher.py -k agentic -v`
Expected: FAIL (no AGENTIC SIGNALS in prompt).

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/enricher.py`，於 `CONTRIBUTION_BLOCK` 常數附近加入：

```python
AGENTIC_SIGNALS_BLOCK = (
    "\n\nAGENTIC SIGNALS (factual — ground bullets in these only when the raw "
    "activity supports them; never invent):\n{lines}\n"
)
```

在 `_build_prompt` 內，CONTRIBUTION_BLOCK 區塊之後、emphasis block 之前加入：

```python
    sig = g.agentic_signals
    if sig is not None:
        sig_lines: list[str] = []
        if sig.skills_authored:
            line = f"authored skills: {', '.join(sig.skills_authored)}"
            if sig.skills_published:
                line += " (published to a plugin marketplace)"
            sig_lines.append(line)
        if sig.skills_used:
            sig_lines.append(f"used {len(sig.skills_used)} skills: {', '.join(sig.skills_used)}")
        if sig.mcp_servers_used:
            sig_lines.append(
                f"integrated {len(sig.mcp_servers_used)} MCP servers: {', '.join(sig.mcp_servers_used)}")
        if sig.mcp_authored:
            sig_lines.append("authored an MCP server")
        if sig_lines:
            body += AGENTIC_SIGNALS_BLOCK.format(lines="\n".join(f"- {x}" for x in sig_lines))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_enricher.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py tests/test_enricher.py
git commit -m "feat(enricher): factual AGENTIC_SIGNALS_BLOCK from group signals (#43)"
```

---

### Task 6: Release 0.11.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.10.2 字串**

Run: `grep -rn "0\.10\.2" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處。

- [ ] **Step 2: 全部改為 0.11.0 並刷新 lockfile**

逐處 `0.10.2` → `0.11.0`，然後 `uv lock`。
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.11.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（em-dash）：

```markdown
## [0.11.0] — 2026-05-29

### Added

- **Agent Skills + MCP competency signal** (`AgenticSignals` on each project
  group, #43) — distinguishes **authoring** from **usage**: skills authored
  (from `SKILL.md` / `skills/<name>/` / plugin manifests, with a published
  flag), skills used (from session `Base directory for this skill:` markers),
  MCP servers integrated (from `mcp__<server>__` tool calls), and a
  conservative MCP-authoring flag. The enricher now appends a factual agentic-
  signals hint so bullets can foreground this Tier-1 agentic competency instead
  of collapsing it into a generic `agent-tooling %`. First of the competency-
  signal epic; shared `AgenticSignals` surface extended by later releases.
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.10.2 → 0.11.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-agentic-skills-mcp-signal-design.md`）：
- `AgenticSignals` 子模型 + `ProjectGroup.agentic_signals` → Task 1。✓
- `skill_uses_in` helper → Task 2。✓
- claude_code/codex 捕捉 `skills_used` → Task 3。✓
- aggregator `_agentic_signals`（authored/published、skills_used union、mcp_servers_used、mcp_authored）+ `_mcp_server` → Task 4。✓
- 全空→None → Task 4 `test_agentic_signals_none_when_empty`。✓
- 最小 enrich hint(AGENTIC_SIGNALS_BLOCK) → Task 5。✓
- 不動 classifier / 不加 render 區塊 / mcp_authored 保守 → 計畫未含,符合非目標。✓
- release 0.11.0 → Task 6。✓

**2. Placeholder scan:** 無 TBD/TODO；每 code step 有完整程式碼。✓

**3. Type consistency:**
- `AgenticSignals`（skills_authored/skills_published/skills_used/mcp_servers_used/mcp_authored）：Task 1 定義,Task 4 建構、Task 5 讀取、Task 1/4/5 測試一致。✓
- `skill_uses_in(text) -> list[str]`：Task 2 定義,Task 3 extractors 呼叫一致。✓
- `_mcp_server(name) -> str|None` / `_agentic_signals(acts, group_name) -> AgenticSignals|None`：Task 4 定義與測試一致；group-loop 傳 `display_name`。✓
- `extra["skills_used"]`：Task 3 寫入(sorted list)、Task 4 讀取(union)，一致。✓
- `AGENTIC_SIGNALS_BLOCK`：Task 5 常數 + format(lines=...)，一致。✓
