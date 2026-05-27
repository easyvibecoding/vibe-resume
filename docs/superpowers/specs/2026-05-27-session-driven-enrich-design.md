# Session-driven enrich / verify + per-locale cache 拆分

**Date**: 2026-05-27
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans

## 背景與動因

Anthropic 自 **2026-06-15** 起調整計費架構([來源](https://codersera.com/blog/anthropic-june-2026-billing-change-claude-code/)、[Claude Code docs](https://code.claude.com/docs/en/costs)):

- `claude -p` headless 一次性執行(以及 Agent SDK / Task tool 派生的 subagent)改吃**新的「Agent SDK 月度額度」池**:Pro $20/月、Max 20x $200/月,企業預設 $0
- 額度用罄後自動降級到「全 API 定價」,無訂閱補貼
- Claude Code 互動 session 主對話(使用者在當前 session 內請主 Claude 處理的工作)走的是**既有 Claude Code 訂閱額度**,與 Agent SDK 額度池分開

本專案目前兩條 LLM 呼叫路徑都是 spawn `claude -p` subprocess,屬於會吃新 Agent SDK 額度池的型態:

| 位置 | 用途 | 觸發來源 |
|---|---|---|
| `core/enricher.py::_call_claude` | 對每個 ProjectGroup 跑 enrichment prompt(XYZ/名詞片語 bullet) | `vibe-resume enrich` |
| `cli.py::company_verify` | 跑 fact-check prompt + web search/fetch 工具 | `vibe-resume company verify <key>` |

額外觀察到一個既有缺陷需要一起解:**enriched cache 沒有 locale 維度**,連跑兩個 locale 後者會覆寫前者。

## 目標

1. **預設不再 spawn `claude -p` subprocess**;CLI 改成輸出 prompt 資料、由 Claude Code 主 session 處理 LLM 工作、再讀回結果
2. **多 locale 並存** — 連跑 `enrich --locale zh_TW` 和 `enrich --locale en_US` 不互蓋,render 能直接拉對應 locale 的 cache
3. **保留 headless 路徑當降級**(CI / cron / 非互動環境)— 但要印警告,說明會吃新 Agent SDK 額度
4. **`company verify` 一併同型重構**
5. **rule-based fallback 保留** — 完全沒 LLM 也能跑

## 非目標

- 不重寫 `_build_prompt` 內部的 prompt 工程細節(prompt 模板與 i18n 全部維持)
- 不改 `Activity` schema、aggregator 邏輯、render/review 流程的核心
- 不引入 Agent SDK Python binding 或其它新依賴
- 不處理 `enrich --persona all` 的並發優化(維持序列)

## 已固化決策

| # | 議題 | 決策 |
|---|---|---|
| 1 | `--mode` 預設值 | **`prompt`(破壞性變更)** — 0.4.0 主版號 bump、CHANGELOG 顯眼標 Breaking |
| 2 | `data/enrich_jobs/` 版控 | **完整 gitignore** + `tests/fixtures/enrich_jobs_sample/` 合成 fixture |
| 3 | `company verify` 是否同 PR | **一個 PR 全做完** |
| 4 | per-locale cache | **加 locale 維度到檔名;舊 cache 刪除重跑** |

---

## 設計總覽

### 1. CLI shape

```bash
# 預設模式(emit + 等待 session 處理):新 0.4.0 預設
uv run vibe-resume enrich --locale en_US [--persona ...] [--tailor ...] [--company ...] [--level ...]
# 行為: 對選定的 group 生成 prompt → dump 到 data/enrich_jobs/<persona>/<locale>/
#       印「下一步」: 在 Claude Code session 內處理 *.prompt.md → 寫 *.yaml → `enrich --ingest --locale <L>`

# 把 Claude Code session 處理完的 YAML 回填到 per-locale enrich cache
uv run vibe-resume enrich --ingest --locale en_US [--persona ...]
# 行為: 讀 manifest → 對每個 *.yaml 跑 _apply_parsed_output → 寫 _project_groups.<persona>.<locale>.json
#       缺檔/解析失敗 → 跳過 + 警告,不中斷

# 降級路徑(舊 subprocess 行為,留給 CI/headless)
uv run vibe-resume enrich --mode subprocess --locale en_US
# 行為: 維持目前 _call_claude 路徑,啟動時印 ⚠ 紅字警告:
#       「會吃 Anthropic Agent SDK 額度池,與 Claude Code 訂閱額度分開」

# 完全不用 LLM(rule-based fallback)
uv run vibe-resume enrich --mode rule-based --locale en_US
```

`company verify` 三模式同型:

```bash
uv run vibe-resume company verify --emit <key>        # dump prompt + manifest 到 data/verification_jobs/<key>_<date>/
uv run vibe-resume company verify --ingest <key>      # 讀 report.md → 寫 verification_reports/ → parse verdict
uv run vibe-resume company verify --mode subprocess <key>   # 舊行為,印警告
```

### 2. 目錄結構(per-locale 拆分)

```
data/
├── cache/
│   ├── _project_groups.json                   # aggregator 輸出(locale-free,raw groups)
│   ├── _project_groups.default.en_US.json     # ← enrich --ingest 寫入,per persona × locale
│   ├── _project_groups.default.zh_TW.json
│   ├── _project_groups.tech_lead.en_US.json
│   └── ...
│
├── enrich_jobs/                                # ← gitignore;短暫 working dir
│   ├── default/
│   │   ├── en_US/
│   │   │   ├── manifest.json
│   │   │   ├── 001_proj-foo.prompt.md
│   │   │   ├── 001_proj-foo.yaml
│   │   │   └── ...
│   │   └── zh_TW/
│   │       ├── manifest.json
│   │       └── ...
│   └── tech_lead/
│       └── en_US/...
│
└── verification_jobs/                          # ← gitignore
    └── ramp_2026-05-27/
        ├── manifest.json
        ├── prompt.md
        └── report.md
```

### 3. 資料 schema 變動

**檔名命名規則**

| 舊 | 新 |
|---|---|
| `_project_groups.json` | (保留,給 aggregator;不含 enrichment) |
| `_project_groups.<persona>.json` | `_project_groups.<persona-or-default>.<locale>.json` |

**`groups_path_for` 簽名擴充**(`core/aggregator.py`)

```python
def groups_path_for(persona: str | None = None, locale: str | None = None) -> Path:
    """Cache path for enriched project groups, scoped to persona × locale.

    Aggregator output (locale-free, raw) stays at GROUPS_PATH.
    Enriched output goes to _project_groups.<persona-or-'default'>.<locale>.json
    so multi-locale runs don't clobber each other.
    """
    if locale is None:
        return GROUPS_PATH                     # raw aggregator output only
    p = persona or "default"
    return GROUPS_PATH.parent / f"_project_groups.{p}.{locale}.json"


def load_groups(
    persona: str | None = None,
    locale: str | None = None,
) -> list[ProjectGroup]:
    """Load enriched groups for (persona, locale), with fallback chain.

    Fallback order:
      1. (persona, locale)        — exact match
      2. (None,    locale)        — default persona, same locale
      3. GROUPS_PATH              — raw aggregator output (no enrichment)
      4. []                       — empty
    """
    ...
```

**Manifest schema**(`core/enrich_jobs.py`,新檔)

```python
class EnrichJobEntry(BaseModel):
    id: str                       # zero-padded index e.g. "001"
    name: str                     # group.name
    prompt_path: str              # relative to manifest dir
    output_path: str              # relative to manifest dir
    status: Literal["pending", "done"]

class EnrichJobManifest(BaseModel):
    version: int = 1
    created_at: datetime
    locale: str                   # required — locale 是 first-class 維度
    persona: str | None
    tailor_keywords: list[str] | None
    company: str | None
    level: str | None
    groups: list[EnrichJobEntry]
```

### 4. 模組劃分

```
core/
├── enricher.py
│   ├── _build_prompt()              # 不動
│   ├── _apply_parsed_output()       # 不動
│   ├── _fallback_summary()          # 不動
│   ├── _call_claude()               # 不動,僅 --mode subprocess 用
│   └── enrich_groups()              # 重構: mode dispatcher + ingest 分支
│
├── enrich_jobs.py                   # 新檔
│   ├── EnrichJobManifest / EnrichJobEntry  # pydantic
│   ├── emit_jobs(groups, ..., out_dir) -> Path
│   └── ingest_jobs(manifest_path) -> tuple[list[ProjectGroup], list[str]]
│                                       # (enriched_groups, warnings)
│
└── aggregator.py
    ├── groups_path_for(persona, locale)    # 擴充簽名
    └── load_groups(persona, locale)        # 擴充簽名 + fallback chain
```

`enrich_groups()` 內部偽碼:

```python
def enrich_groups(
    cfg, cache_dir, *,
    mode: Literal["prompt", "subprocess", "rule-based"] = "prompt",
    ingest: bool = False,
    locale: str | None = None,
    persona: str | None = None,
    tailor: str | None = None,
    company: str | None = None,
    level: str | None = None,
    limit: int | None = None,
):
    locale_key = locale or _resolve_default_locale(cfg)
    if ingest:
        return _do_ingest(persona, locale_key)

    groups = load_groups()  # raw aggregator output (locale-free)
    if not groups:
        console.print("[yellow]no groups — run aggregate first[/yellow]")
        return

    if mode == "rule-based":
        return _enrich_with_fallback(groups, persona, locale_key)

    if mode == "subprocess":
        console.print(
            "[red]⚠ --mode subprocess spawns `claude -p`, which bills against "
            "the Anthropic Agent SDK quota pool (separate from your Claude Code "
            "subscription). Default mode 'prompt' uses your session quota.[/red]"
        )
        return _enrich_with_subprocess(groups, persona, locale_key, ...)  # 舊邏輯

    # mode == "prompt" (default)
    jobs_dir = emit_jobs(
        groups, cfg, persona, locale_key,
        tailor=tailor, company=company, level=level, limit=limit,
    )
    console.print(f"[green]✓[/green] wrote {len(groups)} prompts to {jobs_dir}")
    console.print(
        f"[cyan]Next:[/cyan] in your Claude Code session, process each "
        f"*.prompt.md → write *.yaml (see SKILL.md §4a), then run "
        f"`uv run vibe-resume enrich --ingest --locale {locale_key}"
        f"{' --persona ' + persona if persona else ''}`"
    )
```

### 5. SKILL.md procedure 改動

`§4 Run extractors → aggregate → enrich` 後新增子節:

```markdown
4a. **(預設,省訂閱額度)** Emit + session-driven enrich

   ```bash
   uv run vibe-resume enrich --locale <L>
   # → 寫出 data/enrich_jobs/<persona-or-default>/<L>/manifest.json + N 個 *.prompt.md
   ```

   在當前 Claude Code session 內:

   1. 讀 `data/enrich_jobs/<persona>/<L>/manifest.json`
   2. 對每個 `status: pending` 條目,讀對應的 `*.prompt.md`
   3. 在 session 內生成嚴格 YAML(prompt 已包含完整輸出規格)
   4. 寫到該條目的 `output_path`

   完成後:

   ```bash
   uv run vibe-resume enrich --ingest --locale <L>
   # → 合併 *.yaml 到 _project_groups.<persona>.<L>.json
   ```

   多 locale 並行 OK(各自獨立目錄與 cache 檔):

   ```bash
   uv run vibe-resume enrich --locale en_US     # emit en_US prompts
   uv run vibe-resume enrich --locale zh_TW     # emit zh_TW prompts(不蓋)
   # session 內處理兩個 locale 的 yaml
   uv run vibe-resume enrich --ingest --locale en_US
   uv run vibe-resume enrich --ingest --locale zh_TW
   uv run vibe-resume render --locale en_US     # 讀 _project_groups.default.en_US.json
   uv run vibe-resume render --locale zh_TW     # 讀 _project_groups.default.zh_TW.json
   ```

4b. **(降級,CI / 非互動)** 走 `claude -p` subprocess(會吃 Anthropic Agent SDK
   月度額度,2026-06-15 起與 Claude Code 訂閱額度分開計算):

   ```bash
   uv run vibe-resume enrich --mode subprocess --locale <L>
   ```
```

`Pitfalls` 段刪除「enrich 會覆寫 _project_groups.json,所以 zh_TW → render → en_US enrich → render 的順序較安全」這條 — 新設計下不存在這個問題。

### 6. 影響的 render / review / personas-compare

- **`render/renderer.py::render_draft`**:`load_groups(persona=persona)` 改 `load_groups(persona=persona, locale=resolved_locale)`,locale 從現有 resolution chain 來
- **`core/review.py`**:同樣傳 locale
- **`cli.py::personas_compare`**(`groups_path_for` × persona 列舉):新增 `--locale` 必填參數(predates locale-aware enrich,過去隱含 default cache;新規則明確要求)

### 7. 錯誤處理 / 邊界

| 情境 | 行為 |
|---|---|
| `--ingest` 找不到 manifest | 紅字 + 非零 exit,訊息提示先跑 `enrich --locale <L>` |
| YAML 缺檔 / 解析失敗 | 跳過該 group + 黃字警告,不 abort |
| `--mode subprocess` 但 `which claude` 失敗 | 自動 fallback 到 `rule-based`,印灰字訊息 |
| 同一 (persona, locale) 重複 emit | 覆寫 manifest + prompts,**保留既有 *.yaml**(避免吃掉 session 工作);印警告列出仍存在的 yaml |
| `render` 找不到 per-locale cache | fallback chain (見 `load_groups`);若降到 raw aggregator output,印「請先 enrich --ingest --locale <L>」提示 |

### 8. Backward compatibility & migration

- **Breaking change**(0.4.0 主版號 bump):
  - `enrich` 預設不再產出 enriched cache(改成 emit-only)
  - cache 檔名變了(`_project_groups.<persona>.json` → `_project_groups.<persona>.<locale>.json`)
- **Migration 策略**: 舊 `_project_groups.<persona>.json` **不自動 migrate**(沒有 locale 資訊無法歸位)。CHANGELOG / release notes 明確指示:
  ```
  rm data/cache/_project_groups.*.json   # 舊 enriched cache
  # 重跑 enrich 流程(新版本要指定 --locale)
  ```
- **`render` 寬限**: 若偵測到舊 `_project_groups.<persona>.json` 殘留,印警告但不刪除

### 9. 測試

新增:

- `tests/test_enrich_jobs.py`
  - `test_emit_writes_manifest_and_prompts`
  - `test_emit_includes_bias_blocks`(tailor / persona / level / company 都進 prompt)
  - `test_emit_separates_locales`(zh_TW + en_US 同 persona 各自獨立目錄)
  - `test_ingest_applies_parsed_output`
  - `test_ingest_skips_missing_yaml`
  - `test_ingest_warns_on_bad_yaml`
- `tests/test_cli_enrich_modes.py`
  - `test_default_mode_is_prompt`
  - `test_subprocess_mode_emits_red_warning`
  - `test_ingest_round_trip`(emit → 模擬 session 寫 YAML → ingest → cache 與舊 subprocess 結果一致)
- `tests/test_per_locale_cache.py`
  - `test_groups_path_for_includes_locale`
  - `test_load_groups_fallback_chain`(per-locale > default-persona-same-locale > raw > [])
  - `test_render_reads_per_locale_cache`
- `tests/test_company_verify_jobs.py`
  - `test_emit_writes_verification_prompt`
  - `test_ingest_parses_verdict_and_applies_apply_flag`

`tests/test_cli_e2e.py` fixture 需注入 per-locale cache 而非舊路徑。

---

## git 歷史 audit 結論(問題 #5)

掃了所有 commit + 所有 ref:

| 檢查項 | 結果 | 風險 |
|---|---|---|
| `profile.yaml` 曾入 git | ❌ 無 | — |
| `data/cache/*` / `resume_history/*` / `reviews/*` / `verification_reports/*` 曾入 git | ❌ 無 | — |
| `config.yaml` 曾入 git | ✅ commit `68619d8 → c01d1cf` 之間 | **低**:內容為通用範例路徑(`~/Projects`、`~/Code`、`~/sideProject`),無 PII / 無密鑰 |
| `.env` / `.pem` / `.key` / credentials / secrets 檔 | ❌ 無 | — |
| password / api_key / sk- / ghp_ / Bearer token pattern | ❌ 無 | — |
| `data/imports/*`(非 sample) | ❌ 無(僅 `sample_jd.txt`) | — |

**結論:不需 `git-filter-repo` 歷史清理**。`config.yaml` 在歷史中的內容屬 example-grade,個人化僅止於 `~/sideProject` 這個目錄名(無敏感資訊)。

**補強建議(本 spec 不強制,可拆獨立 PR)**:
1. 加 pre-commit hook(`gitleaks` 或自寫 grep)擋未來誤 commit
2. SECURITY.md 補一段「歷史 config.yaml 內容無敏感資料」備案
3. CI 加一個 `block_user_yaml_in_pr` job:若 PR diff 含 `^profile\.yaml$` 或 `^config\.yaml$` 直接 fail

---

## 實作順序(供 writing-plans)

1. **新增 `core/enrich_jobs.py`** — emit + ingest 純函數 + pydantic models + 單元測試
2. **擴充 `core/aggregator.py`** — `groups_path_for(persona, locale)`、`load_groups(persona, locale)` + fallback chain + 測試
3. **重構 `core/enricher.py::enrich_groups`** — mode dispatcher;舊邏輯搬到 `_enrich_with_subprocess`;加 `--ingest` `--mode` 旗標
4. **同型重構 `cli.py::company_verify`** — `--emit` / `--ingest` / `--mode subprocess`
5. **更新 `render/renderer.py` + `core/review.py` + `cli.py::personas_compare`** — 傳 locale 到 `load_groups`
6. **`render` 加 fallback 提示**(找不到 per-locale cache 時)
7. **SKILL.md §4a/§4b + Pitfalls 改寫 + `references/troubleshooting.md` 補額度說明**
8. **README × 4 語言版同步**(enrich 章節 + 6/15 計費註腳 + 0.4.0 breaking 註記)
9. **CHANGELOG 0.4.0 entry**(含 `### Breaking changes` 段)+ 同步 bump **6 處版本字串**(`pyproject.toml`、`SKILL.md::metadata.version`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` × 2、`.codex-plugin/plugin.json`)
10. **e2e 測試調整 + 新增 per-locale 測試套**(`test_skill_spec.py` 會自動驗版本一致性)
11. **`tests/fixtures/enrich_jobs_sample/` 合成 fixture**(讓 contributor 看 schema 真實樣貌)
12. **Release**:tag `v0.4.0` + `gh release create` + push `main`(切 `easyvibecoding` git identity);詳細步驟見 §發布通路

---

## 發布通路與 0.4.0 版本提升

### 現況版本盤點(全部 0.3.0,2026-04-22 發布)

| 通路 | 入口 / URL | 版本字串位置 | reindex 觸發 |
|---|---|---|---|
| **GitHub Releases** | `github.com/easyvibecoding/vibe-resume/releases` — 最新 tag `v0.3.0` (2026-04-22) | git tag + `gh release create` | 手動 |
| **skills.sh registry** | `npx skills add easyvibecoding/vibe-resume --skill ai-used-resume`;listing 頁 `skills.sh/easyvibecoding`(目前 5 installs) | `SKILL.md::metadata.version` + GitHub `main` HEAD | push 到 `main`(自動,無 publish 指令)— 證據:CHANGELOG「Published fresh tarball so npx skills add … and skills.sh registries pick up」 |
| **Claude Code marketplace** | `/plugin marketplace add easyvibecoding/vibe-resume` 抓 `.claude-plugin/marketplace.json` | `.claude-plugin/marketplace.json::metadata.version` + `marketplace.json::plugins[].version` + `.claude-plugin/plugin.json::version` | push 到 `main`;使用者 `/plugin update` 拉新版 |
| **Codex marketplace** | `.codex-plugin/plugin.json` | `.codex-plugin/plugin.json::version` | push 到 `main`(需 codex-cli ≥ v0.121.0,2026-04-15 後) |

skills.sh 上 `easyvibecoding` 還有兩個姊妹 skill — `vibe-sci`(2 installs)、`hermes-sci`(1 install)— **本 PR 不影響**(獨立 repo)。

### 需要同步 bump 的 6 處版本字串

```
pyproject.toml:3                          version = "0.4.0"
skills/ai-used-resume/SKILL.md:7          version: "0.4.0"
.claude-plugin/plugin.json:4              "version": "0.4.0"
.claude-plugin/marketplace.json:9         "version": "0.4.0"   # marketplace 自身
.claude-plugin/marketplace.json:19        "version": "0.4.0"   # 內含 plugin entry
.codex-plugin/plugin.json:3               "version": "0.4.0"
```

`tests/test_skill_spec.py` 已有「manifest 版本一致性」檢查(若 6 處沒同步會 fail);實作時跑 `uv run pytest tests/test_skill_spec.py` 確認。

### Release 步驟(實作 + 測試通過後)

按順序:

1. CHANGELOG.md 寫 0.4.0 entry,**`### Breaking changes`** 段開頭明列:
   - `enrich` 預設 mode 從(隱含的)subprocess → `prompt`
   - cache 檔名:`_project_groups.<persona>.json` → `_project_groups.<persona>.<locale>.json`
   - migration:`rm data/cache/_project_groups.*.json` + 重跑
   - 6/15 計費背景說明(連結 Anthropic 公告)
2. 6 處版本字串同步 bump 到 `0.4.0`
3. 全測試:`uv run pytest tests/`(50+ 既有 + 本 PR 新增 ≈ 15 個)
4. `uv run ruff check .`
5. `git config user.email easyvibecoding@users.noreply.github.com`(per `~/.claude/rules/github-identities.md`,避免污染工作身份)
6. commit + `git tag v0.4.0`
7. push `main` 到 `easyvibecoding/vibe-resume`(用 keychain PAT inline helper,見 `[[reference_easyvibecoding_push]]`);**使用者明確授權**才直接推 main
8. `gh release create v0.4.0` 寫 release notes(從 CHANGELOG.md 0.4.0 段擷取)
9. 驗證:
   - GitHub Releases 頁出現 v0.4.0
   - skills.sh `easyvibecoding/vibe-resume` 頁 install count 不變但 description 應跟新(自動 reindex,通常 < 1 hr)
   - Claude Code 端跑 `/plugin update vibe-resume`(或重新 `/plugin install`)拉到 0.4.0

### 通路相容性風險

| 通路 | 0.4.0 升級風險 |
|---|---|
| GitHub Releases | 無;只是新 tag |
| skills.sh | 低;只是 SKILL.md 內 Procedure §4 段擴充,description / name / metadata 形狀不變 |
| Claude Code marketplace | 中;**plugin manifest 結構不變**,但裝過 0.3.0 的使用者第一次跑會撞舊 cache 不能 render — 仰賴 §8 的 render fallback 警告 + CHANGELOG migration 指示 |
| Codex marketplace | 同上 |

`.claude-plugin/marketplace.json` 與 `.codex-plugin/plugin.json` 的 `keywords` / `category` / `interface` 形狀**不變**;這次只是 version bump + description 微調(若描述要加「session-driven enrichment」當賣點)。

---

## 不在這個 PR 的後續

- pre-commit `gitleaks` / CI block 規則(audit 補強)— 拆獨立 PR
- `enrich --persona all` 並發優化
- session-driven 的 sub-skill 自動化(目前靠 SKILL.md 手動引導即可)
- 同步更新姊妹 repo `vibe-sci` / `hermes-sci`(若也有 `claude -p` 用法 — 需另查)
