# Multi-Agent Orchestration Signal Implementation Plan (#48 / 0.13.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface multi-agent orchestration (subagents / fan-out / supervisor-worker / verify-pipeline / workflow-script / agent-sdk) as a distinct `AgenticSignals.orchestration` tag list instead of collapsing it into `agent-tooling %`.

**Architecture:** Add `orchestration: list[str]` to the shared `AgenticSignals` model. The aggregator's `_agentic_signals` detects pattern tags from each activity's text blob and `skills_used` via a fixed pattern table, emitting distinct tags in a stable order. The enricher adds an orchestration line (flagging the verification stage as a senior signal).

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, ruff, uv. Spec: `docs/superpowers/specs/2026-05-29-orchestration-signal-design.md`.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/schema.py` | `AgenticSignals.orchestration` | Modify |
| `src/vibe_resume/core/aggregator.py` | orchestration detection in `_agentic_signals` | Modify |
| `src/vibe_resume/core/enricher.py` | orchestration line in agentic hint | Modify |
| `tests/test_schema.py` | orchestration default | Modify |
| `tests/test_aggregator.py` | orchestration detection | Modify |
| `tests/test_enricher.py` | orchestration hint line | Modify |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.13.0 bump | Modify |

**Execution order:** Task 1 (schema) → Task 2 (aggregator) → Task 3 (enricher) → Task 4 (release).

---

### Task 1: `AgenticSignals.orchestration`

**Files:**
- Modify: `src/vibe_resume/core/schema.py` (`AgenticSignals`)
- Test: `tests/test_schema.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_schema.py` 追加：

```python
def test_agentic_signals_orchestration_default_and_roundtrip():
    from vibe_resume.core.schema import AgenticSignals
    assert AgenticSignals().orchestration == []
    s = AgenticSignals(orchestration=["fan-out", "verify-pipeline"])
    back = AgenticSignals(**s.model_dump())
    assert back.orchestration == ["fan-out", "verify-pipeline"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schema.py::test_agentic_signals_orchestration_default_and_roundtrip -v`
Expected: FAIL（`orchestration` kwarg 未知）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/schema.py` 的 `AgenticSignals`，`tdd: bool = False` 之後加入：

```python
    orchestration: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/schema.py tests/test_schema.py
git commit -m "feat(schema): AgenticSignals.orchestration tag list (#48)"
```

---

### Task 2: aggregator orchestration detection

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py` (`_agentic_signals`)
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_aggregator.py` 追加（沿用既有 `_act_sig` / `_act_blob`）：

```python
def test_orchestration_from_blob_and_skills():
    assert _agentic_signals([_act_blob(summary="used a sub-agent for X")], "r").orchestration == ["subagents"]
    assert _agentic_signals([_act_sig(skills_used=["dispatching-parallel-agents"])], "r").orchestration == ["fan-out"]
    assert _agentic_signals([_act_blob(summary="adversarial verify with a judge panel")], "r").orchestration == ["verify-pipeline"]
    assert _agentic_signals([_act_blob(summary="built a workflow script, self-pacing")], "r").orchestration == ["workflow-script"]
    assert _agentic_signals([_act_blob(summary="used the Agent SDK")], "r").orchestration == ["agent-sdk"]


def test_orchestration_stable_order_and_distinct():
    sig = _agentic_signals(
        [_act_blob(summary="agent sdk fan-out supervisor worker; adversarial verify; sub-agent")], "r")
    assert sig.orchestration == ["subagents", "fan-out", "supervisor-worker", "verify-pipeline", "agent-sdk"]


def test_orchestration_absent_for_single_agent():
    assert _agentic_signals([_act_blob(summary="prompted the model to write code", files=["a.py"])], "r") is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_aggregator.py -k orchestration -v`
Expected: FAIL（`orchestration` 屬性為 `[]` / signals None）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/aggregator.py`，`_SPECS_TREE_RE` 常數之後加入：

```python
_ORCH_ORDER = ["subagents", "fan-out", "supervisor-worker", "verify-pipeline",
               "workflow-script", "agent-sdk"]
_ORCH_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("subagents", re.compile(r"sub-?agent")),
    ("fan-out", re.compile(r"fan-?out|parallel\s+agents")),
    ("supervisor-worker", re.compile(r"worker\s+topolog|supervisor.{0,12}worker|\bsupervisor\b")),
    ("verify-pipeline", re.compile(r"adversarial.{0,20}verif|judge\s+panel|verify.{0,12}pipeline|synthesi[sz]e")),
    ("workflow-script", re.compile(r"workflow\s+script|workflow\s+orchestrat|self-pac(?:e|ing)")),
    ("agent-sdk", re.compile(r"agent\s+sdk")),
]
_ORCH_SKILL_TAGS = {
    "subagent-driven-development": "subagents",
    "dispatching-parallel-agents": "fan-out",
}
```

在 `_agentic_signals` 函式頂部累積器加 `orch: set[str] = set()`（與 `used`/`servers` 並列）。在迴圈內 `blob` 算好之後加入：

```python
        for tag, pat in _ORCH_PATTERNS:
            if pat.search(blob):
                orch.add(tag)
        for s in (a.extra or {}).get("skills_used") or []:
            tag = _ORCH_SKILL_TAGS.get(s)
            if tag:
                orch.add(tag)
```

把 return 前的「any signal」判斷與 build 更新（加 `orch`）：

```python
    orchestration = [t for t in _ORCH_ORDER if t in orch]
    if not (authored or published or used or servers or mcp_authored or sdd or tdd or orchestration):
        return None
    return AgenticSignals(
        skills_authored=authored,
        skills_published=published,
        skills_used=sorted(used),
        mcp_servers_used=sorted(servers),
        mcp_authored=mcp_authored,
        sdd=sdd,
        tdd=tdd,
        orchestration=orchestration,
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_aggregator.py -v`
Expected: PASS（新 orchestration 測試 + 既有全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): detect multi-agent orchestration patterns (#48)"
```

---

### Task 3: enricher orchestration hint

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (`_build_prompt` agentic block)
- Test: `tests/test_enricher.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_enricher.py` 追加：

```python
def test_build_prompt_agentic_block_includes_orchestration():
    from vibe_resume.core.schema import AgenticSignals
    g = _many_act_group(3)
    g.agentic_signals = AgenticSignals(orchestration=["fan-out", "verify-pipeline"])
    p = _build_prompt(g)
    assert "AGENTIC SIGNALS" in p
    assert "multi-agent orchestration" in p
    assert "fan-out" in p and "verify-pipeline" in p
    assert "verification" in p   # verify-pipeline → senior verification-stage note
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_enricher.py -k orchestration -v`
Expected: FAIL（hint 無 orchestration 行）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/enricher.py` 的 `_build_prompt` agentic-signals 區塊，`if sig.tdd:` 之後（`if sig_lines:` 之前）加入：

```python
        if sig.orchestration:
            line = (f"designed multi-agent orchestration ({', '.join(sig.orchestration)}): "
                    "e.g. fan-out → synthesize → adversarial-verify")
            if "verify-pipeline" in sig.orchestration:
                line += " (with a verification/judge stage)"
            sig_lines.append(line)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_enricher.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py tests/test_enricher.py
git commit -m "feat(enricher): surface multi-agent orchestration in agentic hint (#48)"
```

---

### Task 4: Release 0.13.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.12.0 字串**

Run: `grep -rn "0\.12\.0" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處。

- [ ] **Step 2: 全部改為 0.13.0 並刷新 lockfile**

逐處 `0.12.0` → `0.13.0`，然後 `uv lock`。
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.13.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（em-dash）：

```markdown
## [0.13.0] — 2026-05-29

### Added

- **Multi-agent orchestration signal** (`AgenticSignals.orchestration`, #48) —
  detects subagents, parallel fan-out, supervisor/worker, fan-out→verify
  pipelines, workflow scripts, and Agent SDK usage as distinct pattern tags
  (from activity text + `skills_used`), instead of folding them into a generic
  `agent-tooling %`. The enricher surfaces the topology — flagging a
  verification/judge stage as a senior signal. Completes the competency-signal
  set (tools #43 · methodology #44 · process #48); installed-toolkit #45 next.
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.12.0 → 0.13.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-orchestration-signal-design.md`）：
- `AgenticSignals.orchestration` → Task 1。✓
- aggregator pattern-table 偵測(blob + skills_used)+ 固定順序去重 → Task 2。✓
- 純單代理 → 無 orchestration（且其他空 → None）→ Task 2 `test_orchestration_absent_for_single_agent`。✓
- enrich hint(含 verify-stage 標註)→ Task 3。✓
- 不抓 max fan-out / 不動 classifier → 計畫未含,符合非目標。✓
- release 0.13.0 → Task 4。✓

**2. Placeholder scan:** 無 TBD/TODO;每 code step 有完整程式碼(pattern 表全文 + return 改寫)。✓

**3. Type consistency:**
- `AgenticSignals.orchestration: list[str]`：Task 1 定義,Task 2 set→ordered-list build、Task 3 讀,測試一致。✓
- `_ORCH_ORDER` / `_ORCH_PATTERNS` / `_ORCH_SKILL_TAGS`：Task 2 定義且只在 `_agentic_signals` 用。✓
- `_agentic_signals` return 新增 `orchestration=` kwarg,與 Task 1 欄位名一致。✓
- enricher `sig_lines` / `AGENTIC_SIGNALS_BLOCK`：Task 3 沿用既有結構。✓
