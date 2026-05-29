# Agent Skills + MCP Competency Signal (author vs use)

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#43](https://github.com/easyvibecoding/vibe-resume/issues/43)
**Milestone**: 0.11.0
**Epic**: AI-proficiency / Harness-Engineering competency signals — first of the
sequence #43 → #44 → #48 → #45 → #47 → #46 (#49 leaderboard handled separately).
This issue establishes the shared `AgenticSignals` surface the later issues extend.

## 背景與動因

Agent Skills 與 MCP 是 2026「Agentic Engineer」市場的 Tier-1 競爭力,但在原始活動資料裡**充沛卻幾乎完全沒被表面化**:今天全折進泛用的 `agent-tooling` 類別百分比,履歷上沒有量化、可見的「authored/published N Agent Skills」或「integrated N MCP servers」。

實測多來源資料:~58 個 skill authoring/usage 信號(`SKILL.md`、`skills/<name>/`、`Base directory for this skill: …`)、~509 個 `mcp__<server>__<tool>` tool-call 信號。現況:`agent-tooling` 是 classifier 的單一 regex(`classifier.py:53`);`domain_tags` 只來自 LLM enrich;`tool_histogram`(claude_code extra)已含 `mcp__` 名稱但 aggregator 沒讀。

## 目標

1. 新增結構化 `AgenticSignals` 子模型(`ProjectGroup.agentic_signals`),作為**整個 competency epic 的共用 surface**(#44/#48/#45 往同模型加欄位)。
2. 區分 **authoring**(資深信號)與 **usage**:
   - `skills_authored` / `skills_published`(從 `files_touched`)
   - `skills_used`(從 session「Base directory for this skill:」— 需 extractor 捕捉)
   - `mcp_servers_used`(從 `tool_histogram` / `keywords` 的 `mcp__<server>__`)
   - `mcp_authored`(保守路徑啟發式)
3. 提供最小 enrich hint,讓 enricher 能據實寫出 bullet(完整 senior rubric 措辭留給 #47)。

## 非目標

- 不重寫 classifier 的 `agent-tooling` regex(結構化 signals 才是真修);`\bspec\b` 誤分類修正屬 **#44**。
- 不在 render 模板加專屬「Agentic Competencies」區塊(資料 + enrich hint 已足;呈現/評分留給 #47、score 留給 #49)。
- 不做內容級 MCP-authoring 偵測(讀檔內容判 FastMCP import / pyproject mcp dep)— `mcp_authored` 僅用 `files_touched` 路徑啟發式,保守;深掃留後續。
- 不引入新依賴。

## 架構

### 1. `AgenticSignals` 子模型 — `src/vibe_resume/core/schema.py`

```python
class AgenticSignals(BaseModel):
    skills_authored: list[str] = []     # skill names from SKILL.md / skills/<name>/ in files_touched
    skills_published: bool = False      # a plugin/marketplace manifest was touched
    skills_used: list[str] = []         # distinct skills invoked (session "Base directory for this skill:")
    mcp_servers_used: list[str] = []    # distinct mcp__<server> from tool_histogram / keywords
    mcp_authored: bool = False          # conservative: fastmcp / *mcp[_-]server*.py path marker
```

`ProjectGroup` 加 `agentic_signals: AgenticSignals | None = None`(向後相容,舊 cache → None)。後續 issue 往 `AgenticSignals` 加欄位(sdd/tdd #44、orchestration #48 …)。

### 2. extractor 捕捉 `skills_used`(claude_code + codex)

共用 helper（`extractors/base.py`)：

```python
_SKILL_BASE_RE = re.compile(r"Base directory for this skill:\s*(\S+)")

def skill_uses_in(text: str) -> list[str]:
    """Return skill names (basename of the announced base dir) found in text."""
    return [m.rstrip("/").split("/")[-1] for m in _SKILL_BASE_RE.findall(text or "")]
```

- `claude_code._process_session`:對每個 entry 的文字內容(user/assistant/system 任一含此 marker 的)累積 distinct skill 名 → `extra["skills_used"]`(僅在非空時寫)。
- `codex._process_session`:同樣對 message 內容掃描(codex 也載入 skills);無命中則不寫。
- 兩者皆用既有迭代,不新增檔案讀取。需重抽 `extract` 該信號才進新 cache。

### 3. aggregator 計算 `_agentic_signals(activities) -> AgenticSignals | None`

`src/vibe_resume/core/aggregator.py`,在 group-building loop 為每組計算:

- **skills_authored / skills_published**:掃所有 `a.files_touched`:
  - `…/SKILL.md` → skill 名 = 其父目錄 basename(`skills/foo/SKILL.md` → `foo`;頂層 `SKILL.md` → repo basename)
  - 路徑含 `/skills/<name>/`(非 SKILL.md 行)→ skill 名 `<name>`
  - 任一 `.claude-plugin/plugin.json` / `.codex-plugin/plugin.json` / `.claude-plugin/marketplace.json` → `skills_published=True`
- **skills_used**:union 各 `a.extra["skills_used"]`(去重、排序)
- **mcp_servers_used**:掃每個 activity 的 `extra.get("tool_histogram", {})` keys **與** `a.keywords`,擷取 `^mcp__([^_]+(?:_[^_]+)*)__` 的 `<server>` 段 → distinct、排序
- **mcp_authored**:任一 `files_touched` 路徑(lower)含 `fastmcp`,或 basename 配 `.*mcp[_-]?server.*\.py$` → True;否則 False
- 全部空/False → 回 `None`(group.agentic_signals 保持 None,輸出乾淨)

`mcp__` server 擷取規則:`mcp__<server>__<tool>` → 取第一個 `__` 與第二個 `__` 之間。實作用 `name.split("__")` → 若 `len>=3 and parts[0]==""`... 實際格式 `mcp__server__tool`:`split("__")` = `["mcp","server","tool"]` → server = `parts[1]`。helper:`_mcp_server(name) -> str|None`。

### 4. 最小 enrich hint

`enricher.py`:新增 `AGENTIC_SIGNALS_BLOCK`,在 `_build_prompt` 末尾(emphasis block 之前或之後皆可,屬事實 context)當 `g.agentic_signals` 有內容時追加,內容據實列出 authored/published skills、used skills、mcp servers used、mcp_authored,並註明「Ground bullets in these only when the raw activity supports them; never invent.」。完整 senior rubric(formula、anti-patterns、verification framing)留給 #47。

## 資料流

```
extract  claude_code/codex → extra["skills_used"](session marker);tool_histogram 已含 mcp__
aggregate 每組算 agentic_signals(authored/published/used skills、mcp_servers_used、mcp_authored)
enrich   有 signals → _build_prompt 追加 AGENTIC_SIGNALS_BLOCK(事實提示)
```

## 測試計畫

- **schema**:`AgenticSignals` 預設、`ProjectGroup.agentic_signals` 預設 None、round-trip。
- **base helper**:`skill_uses_in` 解析 marker(單/多/無)、basename 擷取;`_mcp_server` 解析。
- **extractors**:claude_code/codex session 含「Base directory for this skill: …/foo」→ `extra["skills_used"]==["foo"]`;無 marker → 無此 key。
- **aggregator `_agentic_signals`**:
  - `files_touched=["skills/foo/SKILL.md", ".claude-plugin/plugin.json"]` → skills_authored=["foo"], published=True
  - `tool_histogram={"mcp__browser__click":3, "mcp__db__query":1, "Edit":5}` → mcp_servers_used=["browser","db"]
  - skills_used union across activities
  - `files_touched=["src/foo_mcp_server.py"]` → mcp_authored=True;一般檔 → False
  - 全空 → None
- **enricher**:group 有 agentic_signals → `_build_prompt` 含 AGENTIC_SIGNALS_BLOCK + skill/mcp 名;無 → 不含。

## 安全與非破壞

`agentic_signals` 為 optional、預設 None,舊 cache 相容。只讀既有 `files_touched` / `tool_histogram` / `keywords` 與新增的 `skills_used`;不抓檔案內容、不連網。enrich hint 明示 never invent,維持 no-fabrication 契約。
