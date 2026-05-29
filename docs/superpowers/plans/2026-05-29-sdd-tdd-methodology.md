# SDD/TDD Methodology Signal Implementation Plan (#44 / 0.12.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect Spec-Driven (SDD) and Test-Driven (TDD) development as `AgenticSignals` booleans, and fix the classifier bug where a bare `spec` token mis-books spec-driven work as testing.

**Architecture:** Tighten the classifier TESTING regex (drop bare `\bspec\b`, add `\.spec\.`/`_spec` test-specific forms). Add `sdd`/`tdd` booleans to the shared `AgenticSignals` model and detect them in the aggregator's `_agentic_signals` from the group's text blob + Spec-Kit artifact filenames. Extend the enricher's agentic-signals hint with methodology lines.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, ruff, uv. Spec: `docs/superpowers/specs/2026-05-29-sdd-tdd-methodology-design.md`.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/classifier.py` | tighten TESTING regex (drop bare `spec`) | Modify |
| `src/vibe_resume/core/schema.py` | `AgenticSignals.sdd` / `.tdd` | Modify |
| `src/vibe_resume/core/aggregator.py` | detect sdd/tdd in `_agentic_signals` | Modify |
| `src/vibe_resume/core/enricher.py` | sdd/tdd lines in agentic-signals hint | Modify |
| `tests/test_classifier.py` | bare-spec fix | Modify |
| `tests/test_schema.py` | sdd/tdd defaults | Modify |
| `tests/test_aggregator.py` | sdd/tdd detection | Modify |
| `tests/test_enricher.py` | sdd/tdd hint lines | Modify |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.12.0 bump | Modify |

**Execution order:** Task 1 (classifier fix) → Task 2 (schema) → Task 3 (aggregator) → Task 4 (enricher) → Task 5 (release).

---

### Task 1: Tighten TESTING regex (drop bare `spec`)

**Files:**
- Modify: `src/vibe_resume/core/classifier.py:46`
- Test: `tests/test_classifier.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_classifier.py` 追加：

```python
def test_bare_spec_is_not_testing():
    # spec-driven work must NOT be booked as testing (the #44 bug)
    assert Category.TESTING not in classify(_act(summary="refined specs/auth/spec.md per OpenSpec"))
    assert Category.TESTING not in classify(_act(summary="規格驅動開發 spec-kit"))


def test_real_testing_still_detected():
    assert Category.TESTING in classify(_act(summary="ran pytest"))
    assert Category.TESTING in classify(_act(summary="added tests"))
    assert Category.TESTING in classify(_act(files_touched=["src/auth.spec.ts"]))
    assert Category.TESTING in classify(_act(files_touched=["auth_spec.rb"]))
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_classifier.py -k "bare_spec or real_testing" -v`
Expected: `test_bare_spec_is_not_testing` FAILS（裸 spec 目前 match TESTING）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/classifier.py`，把 TESTING rule（line 46）：

```python
    (Category.TESTING, re.compile(r"\b(?:pytest|vitest|jest|unittest|mocha|cypress|playwright|smoke\s*test|\bspec\b|\btests?\b|測試)\b")),
```

改為：

```python
    (Category.TESTING, re.compile(r"(?:\bpytest\b|\bvitest\b|\bjest\b|\bunittest\b|\bmocha\b|\bcypress\b|\bplaywright\b|smoke\s*test|\.spec\.|_spec\b|\btests?\b|測試)")),
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_classifier.py -v`
Expected: PASS（新測試 + 既有 classifier 測試,包括 `"Wrote pytest coverage"`→TESTING、`"寫了 pytest 測試"`→TESTING 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/classifier.py tests/test_classifier.py
git commit -m "fix(classifier): bare 'spec' no longer mis-books spec-driven work as testing (#44)"
```

---

### Task 2: `AgenticSignals.sdd` / `.tdd`

**Files:**
- Modify: `src/vibe_resume/core/schema.py` (`AgenticSignals`)
- Test: `tests/test_schema.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_schema.py` 追加：

```python
def test_agentic_signals_sdd_tdd_defaults():
    from vibe_resume.core.schema import AgenticSignals
    s = AgenticSignals()
    assert s.sdd is False and s.tdd is False
    s2 = AgenticSignals(sdd=True, tdd=True)
    from vibe_resume.core.schema import AgenticSignals as A
    back = A(**s2.model_dump())
    assert back.sdd is True and back.tdd is True
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schema.py::test_agentic_signals_sdd_tdd_defaults -v`
Expected: FAIL（`AgenticSignals` 無 `sdd` 欄位 → TypeError on kwarg）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/schema.py` 的 `AgenticSignals` 內，`mcp_authored` 之後加入：

```python
    sdd: bool = False
    tdd: bool = False
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/schema.py tests/test_schema.py
git commit -m "feat(schema): AgenticSignals.sdd / .tdd methodology flags (#44)"
```

---

### Task 3: aggregator sdd/tdd detection

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py` (`_agentic_signals`)
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_aggregator.py` 追加（沿用既有 `_act_sig`，並加 summary 參數版本的 helper）：

```python
def _act_blob(summary="", files=None):
    return Activity(source=Source.CLAUDE_CODE, session_id="s",
                    timestamp_start="2026-01-01T00:00:00+00:00",
                    summary=summary, files_touched=files or [], extra={})


def test_agentic_signals_sdd_from_keyword_and_artifact():
    assert _agentic_signals([_act_blob(summary="drove this with OpenSpec")], "r").sdd is True
    assert _agentic_signals([_act_blob(files=["specs/auth/spec.md"])], "r").sdd is True
    assert _agentic_signals([_act_blob(summary="規格驅動")], "r").sdd is True


def test_agentic_signals_tdd_from_keyword():
    assert _agentic_signals([_act_blob(summary="strict test-driven, failing test first")], "r").tdd is True
    assert _agentic_signals([_act_blob(summary="red-green-refactor loop")], "r").tdd is True


def test_agentic_signals_sdd_tdd_false_for_plain_group():
    sig = _agentic_signals([_act_blob(summary="added a fastapi endpoint", files=["src/api.py"])], "r")
    assert sig is None   # no agentic signal at all → None


def test_agentic_signals_only_sdd_still_builds():
    sig = _agentic_signals([_act_blob(summary="openspec planning")], "r")
    assert sig is not None and sig.sdd is True and sig.tdd is False
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_aggregator.py -k "sdd or tdd" -v`
Expected: FAIL（`_agentic_signals` 不偵測 sdd/tdd / 回傳 None 或無屬性）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/aggregator.py`，`_mcp_server` / `_PLUGIN_MANIFESTS` 常數附近加入：

```python
_SDD_RE = re.compile(r"openspec|spec[-_ ]?kit|spec-driven|規格驅動")
_TDD_RE = re.compile(r"test-driven|\btdd\b|red[-/ ]green|failing\s+test")
_SPECKIT_ARTIFACTS = {"spec.md", "plan.md", "tasks.md", "data-model.md", "constitution.md"}
_SPECS_TREE_RE = re.compile(r"(?:^|/)specs/[^/]+/")
```

在 `_agentic_signals` 內，於 `for a in acts:` 迴圈中（在 files 掃描與 mcp 掃描之間或之後）加入 sdd/tdd 累積；並在最後的 build 一併納入。完整改寫 `_agentic_signals` 的迴圈尾與 return：

在迴圈內 `used.update(...)` 之前加入 blob 與旗標累積（在函式頂部先初始化 `sdd = False` / `tdd = False`，與 `mcp_authored` 並列）：

```python
        blob = " ".join([a.summary or "", " ".join(a.keywords or []),
                         " ".join(a.files_touched or [])]).lower()
        if _SDD_RE.search(blob):
            sdd = True
        if _TDD_RE.search(blob):
            tdd = True
        for f in a.files_touched or []:
            base = f.rstrip("/").split("/")[-1].lower()
            if base in _SPECKIT_ARTIFACTS or _SPECS_TREE_RE.search(f):
                sdd = True
```

把函式頂部累積器宣告由：

```python
    authored: list[str] = []
    published = False
    mcp_authored = False
    used: set[str] = set()
    servers: set[str] = set()
```

改為（加 `sdd`/`tdd`）：

```python
    authored: list[str] = []
    published = False
    mcp_authored = False
    sdd = False
    tdd = False
    used: set[str] = set()
    servers: set[str] = set()
```

把「any signal」判斷與 return 由：

```python
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

改為：

```python
    if not (authored or published or used or servers or mcp_authored or sdd or tdd):
        return None
    return AgenticSignals(
        skills_authored=authored,
        skills_published=published,
        skills_used=sorted(used),
        mcp_servers_used=sorted(servers),
        mcp_authored=mcp_authored,
        sdd=sdd,
        tdd=tdd,
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_aggregator.py -v`
Expected: PASS（新 sdd/tdd 測試 + 既有 agentic_signals / reconcile 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): detect SDD/TDD methodology signals (#44)"
```

---

### Task 4: enricher sdd/tdd hint lines

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (`_build_prompt` agentic block)
- Test: `tests/test_enricher.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_enricher.py` 追加：

```python
def test_build_prompt_agentic_block_includes_sdd_tdd():
    from vibe_resume.core.schema import AgenticSignals
    g = _many_act_group(3)
    g.agentic_signals = AgenticSignals(sdd=True, tdd=True)
    p = _build_prompt(g)
    assert "AGENTIC SIGNALS" in p
    assert "spec-driven development" in p
    assert "test-driven development" in p
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_enricher.py -k sdd_tdd -v`
Expected: FAIL（hint 無 sdd/tdd 行）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/enricher.py` 的 `_build_prompt` agentic-signals 區塊內，`if sig.mcp_authored:` 之後（`if sig_lines:` 之前）加入：

```python
        if sig.sdd:
            sig_lines.append(
                "drove spec-driven development (OpenSpec / Spec-Kit): "
                "spec → plan → tasks → implementation")
        if sig.tdd:
            sig_lines.append("practices test-driven development (failing test first)")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_enricher.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py tests/test_enricher.py
git commit -m "feat(enricher): surface SDD/TDD methodology in agentic-signals hint (#44)"
```

---

### Task 5: Release 0.12.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.11.0 字串**

Run: `grep -rn "0\.11\.0" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處。

- [ ] **Step 2: 全部改為 0.12.0 並刷新 lockfile**

逐處 `0.11.0` → `0.12.0`，然後 `uv lock`。
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.12.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（em-dash）：

```markdown
## [0.12.0] — 2026-05-29

### Added

- **SDD / TDD methodology signal** (`AgenticSignals.sdd` / `.tdd`, #44) —
  detects Spec-Driven Development (OpenSpec / Spec-Kit / `specs/<feature>/`
  trees / spec-kit artifacts) and Test-Driven Development (test-driven /
  red-green / failing-test-first), distinct from mere test presence. The
  enricher surfaces these as methodology bullets.

### Fixed

- **Bare `spec` no longer mis-books spec-driven work as testing** (#44). The
  classifier TESTING regex dropped the bare `\bspec\b` token (kept `.spec.` /
  `_spec` / `tests`), so `spec.md` / `specs/` / OpenSpec stop inflating the
  `testing %` and instead feed the new SDD signal.
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.11.0 → 0.12.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-sdd-tdd-methodology-design.md`）：
- TESTING regex 收緊(裸 spec 移除)→ Task 1。✓
- `AgenticSignals.sdd` / `.tdd` → Task 2。✓
- aggregator sdd/tdd 偵測(keyword + spec-kit artifact + specs 樹;tdd keyword)→ Task 3。✓
- 只有 sdd/tdd 也建 signals → Task 3 `test_agentic_signals_only_sdd_still_builds` + return 判斷。✓
- enrich hint sdd/tdd 行 → Task 4。✓
- 不加 classifier Category.SDD → 計畫未含,符合非目標。✓
- release 0.12.0 → Task 5。✓

**2. Placeholder scan:** 無 TBD/TODO；每 code step 有完整程式碼(含 regex 全文與 `_agentic_signals` 改寫前後對照)。✓

**3. Type consistency:**
- `AgenticSignals.sdd` / `.tdd`(bool)：Task 2 定義,Task 3 set/return、Task 4 讀、Task 2/3/4 測試一致。✓
- `_agentic_signals(acts, group_name) -> AgenticSignals|None`：簽名不變,Task 3 只擴充內部與 return;新增累積器 `sdd`/`tdd` 與既有並列。✓
- TESTING regex:Task 1 全文替換,既有 pytest/tests/測試 token 保留。✓
- enricher `sig_lines` / `AGENTIC_SIGNALS_BLOCK`：Task 4 沿用 #43 既有結構,只多兩行。✓
