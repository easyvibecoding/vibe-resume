# Installed-Toolkit Extractor (plugins / Agent Skills / MCP servers inventory)

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#45](https://github.com/easyvibecoding/vibe-resume/issues/45)
**Milestone**: 0.14.0
**Epic**: competency signals — environment-maturity source, distinct from #43 usage.

## 背景與動因

#43 從 session log 挖**usage**(invoked skill / called `mcp__…`);本 issue 讀**安裝清單**(已設定 plugins / Agent Skills / MCP servers)—— 不同*來源*。三者構成完整光譜:**authored > used > installed/curated**。一個精選的 agentic 工具箱(整套 workflow skills + domain skills + 數個 MCP servers)是環境成熟度的具體證據,目前完全未捕捉(現有 `claude_desktop` extractor 讀桌面*聊天*,非安裝清單)。

## 目標

1. 新 local extractor `installed_env`,**opt-in**(讀 home dir,預設 `enabled: false`),inventory:Claude Code plugins、standalone Agent Skills、設定的 MCP servers。
2. emit 1 個 synthetic `Activity`(`Source.INSTALLED_ENV`,`project="Agentic Toolkit"`),inventory 放 summary + extra。aggregator 把它變成一個「Agentic Toolkit」組;`_is_meaningful` 豁免不丟。
3. **隱私硬性**:只存名稱 + 粗 transport;**絕不**存 MCP `env`/`args` 值;名稱過 `PrivacyFilter.redact`。
4. enrich 框為 **installed / curated**(非 authored),達成 authored > used > installed 區分。

## 非目標

- **語意分類**(workflow / backend / AI-agent…)→ 需 curated map、脆弱,留後續。v1 給名稱 + 計數 + MCP transport。
- **與 #43 authored skills 的跨 surface 去重** → 複雜;改以 installed/curated framing 避免誤 claim authorship。
- project `.mcp.json` 掃描 → 留後續(先讀固定 home 路徑)。
- 不引入新依賴。

## 架構

### 1. `Source.INSTALLED_ENV = "installed-env"` — `schema.py`

### 2. extractor `src/vibe_resume/extractors/local/installed_env.py`

模組常數(可 monkeypatch 測試)：

```python
_CLAUDE_DIR = Path.home() / ".claude"
_PLUGINS_JSON = _CLAUDE_DIR / "plugins" / "installed_plugins.json"
_SKILLS_DIR = _CLAUDE_DIR / "skills"
_MCP_CONFIG_PATHS = [
    Path.home() / ".claude.json",
    _CLAUDE_DIR / "settings.json",
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
]
```

讀取(全防禦式,缺檔/壞 JSON → 跳過)：
- `_read_plugins() -> list[str]`：`installed_plugins.json` 為 dict;對每個 value 若為 dict,其 keys 為 plugin 名;collect distinct。
- `_read_skills() -> list[str]`：`_SKILLS_DIR.glob("*/SKILL.md")` → name = 父目錄名。
- `_read_mcp_servers() -> list[dict]`：各 config 的 `mcpServers`(dict);每個 server 取 **name** + `transport`(`_transport(cfg)`:有 `url` → "http";`command` basename ∈ {npx}→"npx"、{uvx}→"uvx"、否則 "binary")。**只**取 name + transport,忽略 `args`/`env`。distinct by name。

### 3. 隱私

- 不讀/不存 `env`/`args`/`url` 值(`url` 只用來判 transport=http,不存 url 本身)。
- 所有 plugin/skill/server 名過 `PrivacyFilter(cfg).redact()`(防名稱含敏感字串)。

### 4. 輸出

若三者皆空 → 回 `[]`(extractor 無聲)。否則 1 個 Activity:

```python
Activity(
    source=Source.INSTALLED_ENV,
    session_id="installed-toolkit",
    timestamp_start=now, timestamp_end=now,
    project="Agentic Toolkit",
    activity_type=ActivityType.CODING,
    user_prompts_count=<total items>,
    summary=f"Curates {np} Claude Code plugins, {ns} Agent Skills, {nm} MCP servers",
    extra={"plugins": [...], "skills": [...],
           "mcp_servers": [{"name":..,"transport":..}], 
           "counts": {"plugins":np,"skills":ns,"mcp_servers":nm}},
)
```

### 5. aggregator `_is_meaningful` 豁免

含 `Source.INSTALLED_ENV` activity 的組回 `True`(curated 信號非噪音,仿 A6 external-merged-PR 豁免)。

### 6. runner 註冊 + config

- `runner.py::LOCAL_EXTRACTORS` 加 `"installed_env"`。
- `config.example.yaml` 加:
  ```yaml
  installed_env:
    enabled: false   # reads ~/.claude (plugins/skills) + MCP configs; opt in
  ```
  （`_enabled` 已對缺 key / `enabled:false` 回 False,故預設不跑。）

### 7. enrich framing

enricher 對 `Source.INSTALLED_ENV` 組(或 project=="Agentic Toolkit")加提示:「This is the candidate's *installed/curated* toolkit — frame as 'curates a production agentic toolkit (N plugins, M skills, P MCP servers)'; do NOT claim authorship of merely-installed skills.」

## 測試計畫(tmp home,monkeypatch 路徑常數)

- `_read_plugins`:fixture `installed_plugins.json` → plugin 名 + count;缺檔 → []。
- `_read_skills`:`skills/foo/SKILL.md` + `skills/bar/SKILL.md` → ["bar","foo"]。
- `_read_mcp_servers`:`{"mcpServers":{"browser":{"command":"npx","args":[...],"env":{"KEY":"secret"}},"db":{"url":"http://..."}}}` → `[{"name":"browser","transport":"npx"},{"name":"db","transport":"http"}]`;**斷言 "secret" / args / url 不在輸出任何欄位**。
- `extract`:三來源齊 → 1 Activity,source=INSTALLED_ENV,counts 正確,extra 無 env/args;全缺 → []。
- privacy:名稱含 `sk-…` → redact。
- aggregator:`_is_meaningful` 對 INSTALLED_ENV 組回 True。

## 安全與非破壞

opt-in(預設不跑)。只讀固定 home 路徑、防禦式 parse、缺檔靜默。**絕不**輸出 env/args/url 值(隱私核心)。新 Source 向後相容。
