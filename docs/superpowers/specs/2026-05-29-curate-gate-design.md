# Curate Gate — 人工審核去重/噪音剔除 checkpoint(可溯源）

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#38](https://github.com/easyvibecoding/vibe-resume/issues/38)（Gate A 部分；`emphasis` lever 為後續子專案）
**Milestone**: 0.9.0
**Builds on**: #37 / 0.8.0 的 canonical-key 自動合併（`docs/superpowers/specs/2026-05-29-canonical-project-key-dedupe-design.md`）

## 背景與動因

#37（0.8.0）已在 `aggregate` 時用 git remote/toplevel **自動合併**同一邏輯 repo 的 group，但合併是**靜默改寫 `project` 路徑**——合併後從 `_project_groups.json` 看不出哪些路徑被併、依據為何。對「履歷要呈現哪些專案」這種需要人工把關的決策，缺乏審核與覆寫的接縫。

#38 的 Gate A（`curate`）在 `aggregate` 與 `enrich` 之間加一個 **file-based 人工審核 checkpoint**，沿用既有 `enrich` 的 emit→edit→apply 模式（`manifest.json` 機器狀態 + 可編輯 `*.yaml`）。本子專案聚焦 **traceability 最佳**：每一筆合併/剔除都集中在單一可 git-diff 的審核檔、附證據、可覆寫、可重跑。

`emphasis` lever（自由文字意圖 → bias/rank、light/deep 重跑）是 #38 的另一半，列為**獨立後續子專案**（0.10.0），本 spec 不含。

## 目標

1. **provenance 不再靜默**：`aggregate` 的自動合併保留（不退化 0.8.0），但把「合併了哪些路徑、依據為何」記在 `ProjectGroup` 上，使 `_project_groups.json` 本身即可溯源。
2. 新增 `vibe-resume curate`（emit）：讀帶 provenance 的 groups，產出可編輯的 `_curation.yaml`（每 group 一筆，四種 tier），並印 tier 摘要。
3. 新增 `vibe-resume curate --apply`：pydantic 驗證後執行 `keep` / `merge_into` / `drop`，寫 `_project_groups.curated.json`（非破壞）。
4. `enrich` / `render` 在 curated 快取存在時**優先採用**。
5. **持久化**：`_curation.yaml` 以 canonical identity 為 key，重跑 `aggregate→curate` 自動重套先前人工決策。
6. **headless 安全**：無人工編輯時，`--apply` 只套自動層（auto_drop 剔除、auto_merge 已反映於 groups），`needs_decision` 保留為獨立 `keep`。

## 非目標

- **`emphasis` lever**（bias/rank、light/deep 重跑）→ 獨立子專案（0.10.0）。
- **Jaccard over commit subjects** 的相似度偵測 → needs_decision v1 只用「同 basename + 無法 auto-merge」啟發式，Jaccard 延後（YAGNI）。
- 不改 `aggregate` 既有的 `_is_meaningful` 噪音規則（curate 的 auto_drop 是**額外**、可設定、可審核的一層，不取代既有）。
- 不引入新依賴（YAML 用既有 pyyaml；驗證用既有 pydantic）。

## 架構

### 1. Schema：`ProjectGroup` 加 provenance 欄位

`src/vibe_resume/core/schema.py::ProjectGroup` 新增（皆向後相容、預設空）：

```python
canonical_key: str | None = None     # "remote:github.com/me/foo" / "toplevel:/abs/path"
merged_from: list[str] = []          # 被併入此 group 的原始 project 路徑(len>1 表示確實有合併)
merge_evidence: str | None = None    # 人讀證據,例 "same remote github.com/me/foo"
```

非 DB schema（`ProjectGroup` 只是序列化進 `data/cache/*.json` 的 pydantic 模型）；舊 cache 無此欄 → pydantic 預設填補。依 CLAUDE.md 在 schema 文件/CLAUDE.md 同步說明。

### 2. `aggregate`：`_reconcile_local_projects` 記錄 provenance

改 `src/vibe_resume/core/aggregator.py::_reconcile_local_projects`：仍做 #37 的合併（改寫 `act.project` 到代表路徑），但**回傳** `dict[str, _Provenance]`，key 為代表路徑，值含：

- `canonical_key`：該 cluster 的 canonical key
- `merged_from`：cluster 內所有 distinct 原始 `act.project`（排序後）
- `evidence`：`f"same {kind} {value}"`（kind = remote/toplevel）

`aggregate_from_cache` 的 group-building loop 用 `prov_by_rep.get(path_val)` 取出，填入 `ProjectGroup.canonical_key / merged_from / merge_evidence`。單一路徑的 cluster 仍記 `canonical_key`，`merged_from` 長度為 1（表示未合併）。呼叫端由：

```python
_reconcile_local_projects(all_acts)
```

改為：

```python
prov_by_rep = _reconcile_local_projects(all_acts)
```

（既有 `_reconcile_local_projects` 測試斷言「改寫 project」的行為不變；新增「回傳 provenance」的斷言。）

### 3. `curate` emit — `src/vibe_resume/core/curate.py`（新檔）

`vibe-resume curate`（無 `--apply`）：

1. 讀 `load_groups()`（raw `_project_groups.json`）。
2. 對每個 group 判 tier（優先序：auto_drop > needs_decision > auto_merge > keep）：
   - **auto_drop**：`group.path` 命中 `config.curate.noise_globs`（預設 `["**/tmp/**", "**/temp/**", "**/scratch/**", "**/sandbox/**"]`）。`action: drop`。
   - **auto_merge**：`len(group.merged_from) > 1`。`action: keep`（合併已套用），記 `evidence`、`merged_from` 供審核。
   - **needs_decision**：與另一個 group 同 basename（case-insensitive）但 `canonical_key` 不同或缺 → agent 建議 `action: merge_into`、`target` = sessions 較多者、`evidence` 附 `"no remote proof; same basename as <target>. CONFIRM?"`。
   - **keep**：其餘。
3. 沿用先前 `_curation.yaml`：以 canonical identity（`canonical_key` 無則 `name`）match，carry-forward 先前的 `action`/`target`（仿 `emit_jobs` 的 status carry-forward）。
4. 寫 `data/cache/_curation.yaml`（pydantic 模型 dump）+ 印 tier 計數摘要。

### 4. `curate --apply`

1. 讀並 pydantic 驗證 `_curation.yaml`（缺檔 → headless：等同全部依自動層）。
2. 套用：
   - `drop` → 排除該 group。
   - `merge_into: <canonical>` → 把該 group 的 activities 併入 target group（union activities/sessions/sources/tech/date-range，仿既有 group 合併），更新 `merged_from`/`merge_evidence`。
   - `keep` → 原樣。
3. 寫 `data/cache/_project_groups.curated.json`（非破壞，raw 不動）。

### 5. `enrich` / `render` 優先採 curated 快取

`aggregator.load_groups()`（line 504）的 fallback chain 最前面加一層：若 `config.curate.enabled`（預設 true）且 `_project_groups.curated.json` 存在 → 優先載入。`--curated/--no-curated` CLI flag 可覆寫。raw `GROUPS_PATH` 仍是最終 fallback（curate 沒跑過也能 render）。

### 6. Pydantic 模型 — `src/vibe_resume/core/curate.py`

```python
class CurationEntry(BaseModel):
    name: str
    canonical_key: str | None = None
    sessions: int
    tier: Literal["auto_merge", "auto_drop", "needs_decision", "keep"]
    action: Literal["keep", "merge_into", "drop"]
    target: str | None = None        # merge_into 的目標 group name
    evidence: str | None = None
    merged_from: list[str] = []

class CurationRecord(BaseModel):
    version: int = 1
    generated_at: str
    groups: list[CurationEntry]
```

`_curation.yaml` = `CurationRecord` 的 YAML dump（人編輯）；`_project_groups.curated.json` = 套用後的 `list[ProjectGroup]`（機器狀態）。

### 7. CLI 與 config

- `src/vibe_resume/cli.py` 新增 `curate` 指令（`--apply` flag、`--curated/--no-curated` 給 enrich/render 已有的指令）。
- `config.example.yaml` 加：
  ```yaml
  curate:
    enabled: true                  # enrich/render 優先用 _project_groups.curated.json
    noise_globs:
      - "**/tmp/**"
      - "**/temp/**"
      - "**/scratch/**"
      - "**/sandbox/**"
  ```

## 資料流

```
aggregate  _project_groups.json(含 canonical_key/merged_from/merge_evidence)   ← provenance
curate     ─emit→  _curation.yaml(可編輯,四 tier)
           ─apply→ _project_groups.curated.json(非破壞)
enrich     優先讀 curated.json → _project_groups.<persona>.<locale>.json
render     persona 快取 → resume_history/…
```

## 測試計畫

- **schema**：`ProjectGroup` 新欄位預設值 + round-trip 序列化。
- **aggregator**：`_reconcile_local_projects` 回傳 provenance（同 remote 兩路徑 → merged_from 兩筆、evidence 含 remote；單路徑 → merged_from 一筆）；既有「改寫 project」斷言不變。
- **curate emit**：四 tier 分類（auto_drop glob、auto_merge len>1、needs_decision 同 basename 不同 key、keep）；carry-forward（先前 `_curation.yaml` 的人工 `action` 被保留）。
- **curate apply**：`drop` 排除、`merge_into` union、`keep` 原樣；headless（無 yaml → 只套自動層）；寫出 curated.json。
- **consumption**：`load_groups` 在 curated 存在且 enabled 時優先;`--no-curated` 退回 raw。
- **CLI e2e**：`curate` → `curate --apply` → `render` 串接 smoke test。

## 安全與非破壞

raw `_project_groups.json` 永不被 curate 改寫；curated 是 sidecar。每個 checkpoint idempotent、可重跑、git-diffable。`--apply` 對缺 yaml / 壞 yaml 採 headless 自動層 fallback，不 crash。
