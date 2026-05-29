# Installed-Toolkit Extractor Implementation Plan (#45 / 0.14.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `installed_env` extractor that inventories the installed agentic toolkit (Claude Code plugins, Agent Skills, MCP servers) into one synthetic "Agentic Toolkit" group — capturing only names + coarse transport, never MCP env/args.

**Architecture:** New `Source.INSTALLED_ENV` + `extractors/local/installed_env.py` reading fixed home-dir manifests defensively. Privacy-critical: only names + transport, run through `PrivacyFilter.redact`. Emits one `Activity` (`project="Agentic Toolkit"`); the aggregator's `_is_meaningful` exempts the group from the noise floor, and the enricher frames it as installed/curated (not authored).

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, ruff, uv. Spec: `docs/superpowers/specs/2026-05-29-installed-toolkit-extractor-design.md`.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/schema.py` | `Source.INSTALLED_ENV` | Modify |
| `src/vibe_resume/extractors/local/installed_env.py` | readers + `extract` | Create |
| `src/vibe_resume/core/runner.py` | register `installed_env` | Modify |
| `src/vibe_resume/core/aggregator.py` | `_is_meaningful` exemption | Modify |
| `src/vibe_resume/core/enricher.py` | installed-toolkit framing block | Modify |
| `config.example.yaml` | `installed_env:` block | Modify |
| `tests/test_schema.py` | Source value | Modify |
| `tests/test_installed_env.py` | readers + extract + privacy | Create |
| `tests/test_aggregator.py` | `_is_meaningful` exemption | Modify |
| `tests/test_enricher.py` | framing block | Modify |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.14.0 bump | Modify |

**Execution order:** Task 1 (Source) → Task 2 (readers) → Task 3 (extract + register + config) → Task 4 (`_is_meaningful`) → Task 5 (enricher) → Task 6 (release).

---

### Task 1: `Source.INSTALLED_ENV`

**Files:**
- Modify: `src/vibe_resume/core/schema.py` (`Source` enum)
- Test: `tests/test_schema.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_schema.py` 追加：

```python
def test_source_installed_env_value():
    from vibe_resume.core.schema import Source
    assert Source.INSTALLED_ENV.value == "installed-env"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schema.py::test_source_installed_env_value -v`
Expected: FAIL（`Source` 無 `INSTALLED_ENV`）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/schema.py` 的 `Source` enum 末尾（`GITHUB = "github"` 附近）加入：

```python
    INSTALLED_ENV = "installed-env"
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/schema.py tests/test_schema.py
git commit -m "feat(schema): Source.INSTALLED_ENV (#45)"
```

---

### Task 2: installed_env readers (plugins / skills / mcp + transport)

**Files:**
- Create: `src/vibe_resume/extractors/local/installed_env.py`
- Test: `tests/test_installed_env.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_installed_env.py`：

```python
import json

import vibe_resume.extractors.local.installed_env as ie


def test_read_plugins(tmp_path, monkeypatch):
    p = tmp_path / "installed_plugins.json"
    p.write_text(json.dumps({"market-a": {"pr-toolkit": {}, "commit": {}},
                             "market-b": {"superpowers": {}}}))
    monkeypatch.setattr(ie, "_PLUGINS_JSON", p)
    assert ie._read_plugins() == ["pr-toolkit", "commit", "superpowers"]


def test_read_plugins_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ie, "_PLUGINS_JSON", tmp_path / "nope.json")
    assert ie._read_plugins() == []


def test_read_skills(tmp_path, monkeypatch):
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "SKILL.md").write_text("x")
    (tmp_path / "bar").mkdir()
    (tmp_path / "bar" / "SKILL.md").write_text("x")
    monkeypatch.setattr(ie, "_SKILLS_DIR", tmp_path)
    assert ie._read_skills() == ["bar", "foo"]


def test_transport_detection():
    assert ie._transport({"command": "npx", "args": ["-y", "x"]}) == "npx"
    assert ie._transport({"command": "/usr/bin/uvx"}) == "uvx"
    assert ie._transport({"url": "http://localhost:1234"}) == "http"
    assert ie._transport({"command": "/opt/bin/myserver"}) == "binary"


def test_read_mcp_servers_names_and_transport_only_no_secrets(tmp_path, monkeypatch):
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {
        "browser": {"command": "npx", "args": ["-y", "browser-mcp"], "env": {"TOKEN": "sk-secret-xyz"}},
        "db": {"url": "http://localhost:5432/x?password=hunter2"},
    }}))
    monkeypatch.setattr(ie, "_MCP_CONFIG_PATHS", [cfg])
    servers = ie._read_mcp_servers()
    assert servers == [{"name": "browser", "transport": "npx"},
                       {"name": "db", "transport": "http"}]
    blob = json.dumps(servers)
    assert "sk-secret-xyz" not in blob and "hunter2" not in blob
    assert "browser-mcp" not in blob and "args" not in blob and "env" not in blob
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_installed_env.py -v`
Expected: FAIL（模組不存在）。

- [ ] **Step 3: 實作**

Create `src/vibe_resume/extractors/local/installed_env.py`：

```python
"""Inventory the installed/configured agentic toolkit (Claude Code plugins,
standalone Agent Skills, configured MCP servers). Privacy-critical: only
names + coarse transport are captured — never MCP env/args/url values."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibe_resume.core.privacy import PrivacyFilter
from vibe_resume.core.schema import Activity, ActivityType, Source

NAME = "installed_env"

_CLAUDE_DIR = Path.home() / ".claude"
_PLUGINS_JSON = _CLAUDE_DIR / "plugins" / "installed_plugins.json"
_SKILLS_DIR = _CLAUDE_DIR / "skills"
_MCP_CONFIG_PATHS = [
    Path.home() / ".claude.json",
    _CLAUDE_DIR / "settings.json",
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _read_plugins() -> list[str]:
    data = _load_json(_PLUGINS_JSON)
    names: list[str] = []
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, dict):
                for name in v:
                    if name not in names:
                        names.append(name)
    return names


def _read_skills() -> list[str]:
    if not _SKILLS_DIR.exists():
        return []
    return sorted({p.parent.name for p in _SKILLS_DIR.glob("*/SKILL.md")})


def _transport(server_cfg: dict) -> str:
    if server_cfg.get("url") or server_cfg.get("type") == "http":
        return "http"
    cmd = (server_cfg.get("command") or "").rsplit("/", 1)[-1]
    if cmd == "npx":
        return "npx"
    if cmd == "uvx":
        return "uvx"
    return "binary"


def _read_mcp_servers() -> list[dict]:
    out: dict[str, str] = {}
    for path in _MCP_CONFIG_PATHS:
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            continue
        for name, scfg in servers.items():
            if name not in out and isinstance(scfg, dict):
                out[name] = _transport(scfg)
    return [{"name": n, "transport": t} for n, t in out.items()]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_installed_env.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/installed_env.py tests/test_installed_env.py
git commit -m "feat(installed_env): plugin/skill/MCP readers (names + transport only) (#45)"
```

---

### Task 3: `extract()` + runner register + config

**Files:**
- Modify: `src/vibe_resume/extractors/local/installed_env.py` (`extract`)
- Modify: `src/vibe_resume/core/runner.py` (`LOCAL_EXTRACTORS`)
- Modify: `config.example.yaml`
- Test: `tests/test_installed_env.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_installed_env.py` 追加：

```python
def test_extract_builds_one_toolkit_activity(tmp_path, monkeypatch):
    from vibe_resume.core.schema import Source

    plugins = tmp_path / "installed_plugins.json"
    plugins.write_text(json.dumps({"m": {"pr-toolkit": {}}}))
    skills_dir = tmp_path / "skills"
    (skills_dir / "vibe").mkdir(parents=True)
    (skills_dir / "vibe" / "SKILL.md").write_text("x")
    mcp = tmp_path / ".claude.json"
    mcp.write_text(json.dumps({"mcpServers": {"browser": {"command": "npx", "env": {"K": "sk-zzz"}}}}))
    monkeypatch.setattr(ie, "_PLUGINS_JSON", plugins)
    monkeypatch.setattr(ie, "_SKILLS_DIR", skills_dir)
    monkeypatch.setattr(ie, "_MCP_CONFIG_PATHS", [mcp])

    acts = ie.extract({"privacy": {"redact_patterns": ["sk-[A-Za-z0-9]{2,}"]}})
    assert len(acts) == 1
    a = acts[0]
    assert a.source == Source.INSTALLED_ENV
    assert a.project == "Agentic Toolkit"
    assert a.extra["counts"] == {"plugins": 1, "skills": 1, "mcp_servers": 1}
    assert a.extra["plugins"] == ["pr-toolkit"]
    assert a.extra["skills"] == ["vibe"]
    assert a.extra["mcp_servers"] == [{"name": "browser", "transport": "npx"}]
    assert "sk-zzz" not in json.dumps(a.model_dump(mode="json"))


def test_extract_empty_when_nothing_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(ie, "_PLUGINS_JSON", tmp_path / "no.json")
    monkeypatch.setattr(ie, "_SKILLS_DIR", tmp_path / "noskills")
    monkeypatch.setattr(ie, "_MCP_CONFIG_PATHS", [tmp_path / "no.claude.json"])
    assert ie.extract({}) == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_installed_env.py -k extract -v`
Expected: FAIL（`extract` 未定義）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/extractors/local/installed_env.py` 末尾加入：

```python
def extract(cfg: dict[str, Any]) -> list[Activity]:
    plugins = _read_plugins()
    skills = _read_skills()
    servers = _read_mcp_servers()
    if not (plugins or skills or servers):
        return []
    pf = PrivacyFilter(cfg)
    plugins = [pf.redact(p) for p in plugins]
    skills = [pf.redact(s) for s in skills]
    servers = [{"name": pf.redact(s["name"]), "transport": s["transport"]} for s in servers]
    np_, ns, nm = len(plugins), len(skills), len(servers)
    now = datetime.now(UTC)
    return [Activity(
        source=Source.INSTALLED_ENV,
        session_id="installed-toolkit",
        timestamp_start=now,
        timestamp_end=now,
        project="Agentic Toolkit",
        activity_type=ActivityType.CODING,
        user_prompts_count=np_ + ns + nm,
        tool_calls_count=0,
        summary=f"Curates {np_} Claude Code plugins, {ns} Agent Skills, {nm} MCP servers",
        raw_ref="installed-toolkit",
        extra={
            "plugins": plugins,
            "skills": skills,
            "mcp_servers": servers,
            "counts": {"plugins": np_, "skills": ns, "mcp_servers": nm},
        },
    )]
```

在 `src/vibe_resume/core/runner.py` 的 `LOCAL_EXTRACTORS`（`"github",` 之後）加入：

```python
    "installed_env",
```

在 `config.example.yaml`，`github:` 區塊之後加入：

```yaml
  installed_env:
    enabled: false           # reads ~/.claude (plugins/skills) + MCP configs; opt in
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_installed_env.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/installed_env.py src/vibe_resume/core/runner.py config.example.yaml tests/test_installed_env.py
git commit -m "feat(installed_env): synthetic Agentic Toolkit activity + register + config (#45)"
```

---

### Task 4: `_is_meaningful` exemption for the toolkit group

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py` (`_is_meaningful`)
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_aggregator.py` 追加：

```python
def test_installed_env_group_survives_noise_filter():
    act = Activity(source=Source.INSTALLED_ENV, session_id="installed-toolkit",
                   timestamp_start="2026-01-01T00:00:00+00:00", project="Agentic Toolkit")
    g = _grp("Agentic Toolkit", [act])   # 1 session, breadth 0
    assert _is_meaningful("agentic toolkit", g, min_sessions=2) is True
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_aggregator.py -k installed_env_group -v`
Expected: FAIL（1-session breadth-0 組被丟）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/aggregator.py` 的 `_is_meaningful`，於 `leaf in NOISE_LEAFS` 的 `return False` 之後、external-merged-PR 豁免附近加入：

```python
    # The curated installed-toolkit inventory is signal, not noise.
    if any(a.source == Source.INSTALLED_ENV for a in g.activities):
        return True
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_aggregator.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): exempt installed-toolkit group from noise filter (#45)"
```

---

### Task 5: enricher installed-toolkit framing

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (`_build_prompt`)
- Test: `tests/test_enricher.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_enricher.py` 追加：

```python
def test_build_prompt_installed_toolkit_framing():
    a = Activity(source=Source.INSTALLED_ENV, session_id="installed-toolkit",
                 timestamp_start="2026-01-01T00:00:00+00:00", project="Agentic Toolkit",
                 summary="Curates 3 Claude Code plugins, 5 Agent Skills, 2 MCP servers")
    g = ProjectGroup(name="Agentic Toolkit", first_activity="2026-01-01T00:00:00+00:00",
                     last_activity="2026-01-01T00:00:00+00:00", total_sessions=1, activities=[a])
    p = _build_prompt(g)
    assert "installed" in p.lower() and "curate" in p.lower()
    assert "do not claim authorship" in p.lower()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_enricher.py -k installed_toolkit -v`
Expected: FAIL（無 framing）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/enricher.py`，於 `CONTRIBUTION_BLOCK` 常數附近加入：

```python
INSTALLED_TOOLKIT_BLOCK = (
    "\n\nNOTE: This group is the candidate's *installed / curated* agentic "
    "toolkit (plugins, Agent Skills, MCP servers), not project work. Frame it "
    "as \"curates a production agentic toolkit (N plugins, M skills, P MCP "
    "servers)\" — do not claim authorship of merely-installed skills.\n"
)
```

在 `_build_prompt`，於 agentic-signals 區塊之後、emphasis block 之前加入：

```python
    if any(a.source == Source.INSTALLED_ENV for a in g.activities):
        body += INSTALLED_TOOLKIT_BLOCK
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_enricher.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py tests/test_enricher.py
git commit -m "feat(enricher): frame installed-toolkit group as curated (not authored) (#45)"
```

---

### Task 6: Release 0.14.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.13.0 字串**

Run: `grep -rn "0\.13\.0" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處。

- [ ] **Step 2: 全部改為 0.14.0 並刷新 lockfile**

逐處 `0.13.0` → `0.14.0`，然後 `uv lock`。
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.14.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（em-dash）：

```markdown
## [0.14.0] — 2026-05-29

### Added

- **Installed-toolkit extractor** (`installed_env`, opt-in, #45) — inventories
  the configured agentic toolkit: Claude Code plugins
  (`~/.claude/plugins/installed_plugins.json`), standalone Agent Skills
  (`~/.claude/skills/<name>/`), and configured MCP servers (`mcpServers` in
  `~/.claude.json` / settings / Claude Desktop config). Emits one synthetic
  "Agentic Toolkit" group (exempt from the noise filter) that the enricher
  frames as installed/curated — distinct from authored (#43) and used (#43).
  **Privacy-critical: only names + coarse transport are captured — never MCP
  `env`/`args`/`url` values — and names run through `redact_patterns`.**
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.13.0 → 0.14.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-installed-toolkit-extractor-design.md`）：
- `Source.INSTALLED_ENV` → Task 1。✓
- readers(plugins/skills/mcp + transport,只名+type)→ Task 2。✓
- 隱私(無 env/args/url 值;名過 redact)→ Task 2 `test_..._no_secrets` + Task 3 redact + 斷言。✓
- 1 synthetic Activity / "Agentic Toolkit" → Task 3。✓
- runner 註冊 + opt-in config → Task 3。✓
- `_is_meaningful` 豁免 → Task 4。✓
- enrich installed/curated framing(不誤claim authorship)→ Task 5。✓
- 語意分類 / 跨 surface dedupe / project .mcp.json = 非目標 → 計畫未含。✓
- release 0.14.0 → Task 6。✓

**2. Placeholder scan:** 無 TBD/TODO；每 code step 有完整程式碼(含 extractor 全模組)。✓

**3. Type consistency:**
- `_read_plugins()->list[str]` / `_read_skills()->list[str]` / `_transport(dict)->str` / `_read_mcp_servers()->list[dict]`：Task 2 定義,Task 3 `extract` 一致呼叫。✓
- `extract(cfg)->list[Activity]`(`Source.INSTALLED_ENV`、project="Agentic Toolkit"、extra counts/plugins/skills/mcp_servers)：Task 3 定義,Task 1 Source、Task 4/5 偵測 `a.source == Source.INSTALLED_ENV` 一致。✓
- 路徑常數 `_PLUGINS_JSON`/`_SKILLS_DIR`/`_MCP_CONFIG_PATHS`：Task 2 定義,測試 monkeypatch 一致。✓
- `INSTALLED_TOOLKIT_BLOCK`:Task 5 常數 + `_build_prompt` 偵測,一致。✓
