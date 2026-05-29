# Emphasis Lever — 自由文字意圖驅動的 bias + rank 重跑

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#38](https://github.com/easyvibecoding/vibe-resume/issues/38)（SP3 / lever 部分；Gate A `curate` 已於 0.9.0 出貨）
**Milestone**: 0.10.0
**Builds on**: 既有 enrich bias stack（tailor→persona→level→company）與 `renderer._rank_score`（#36）

## 背景與動因

#38 的另一半：使用者想以**選定的重點**重出履歷（"foreground 我的 agent-orchestration 與 security 工作給 senior-backend 職缺"），並讓 pipeline 強化該焦點 —— 最好便宜地重用快取。`curate` gate（0.9.0）已解決去重/噪音；本子專案加上 **emphasis lever**：一個 file-based 的重點控制檔，騎在既有 enrich bias stack 與 render 排序上。

採**確定性核心**：使用者用一句自由文字描述意圖，`emphasis` 指令記錄它並產出可編輯的 `_emphasis.yaml`（keywords / spotlight / demote 由使用者填）。不引入 LLM 自動解讀（YAGNI，留後續）。重跑**深度隱含**於既有階段獨立性：只重跑 `render` = light（重排，無 LLM），重跑 `enrich` = deep（bias 重寫 bullet）。

## 目標

1. `_emphasis.yaml`（pydantic `EmphasisRecord`）：`intent`（自由文字）、`keywords`、`bias_instruction`、`spotlight`、`demote`。
2. `vibe-resume emphasis "<自由文字>"`：寫/更新 `_emphasis.yaml`（設 intent、carry-forward 既有編輯欄位），印出 group 名稱清單與深度提示；`emphasis --clear` 移除。
3. **enrich（deep）**：`_emphasis.yaml` 存在時，`_build_prompt` 追加 `EMPHASIS_BLOCK`（intent+keywords+bias_instruction）為 bias stack **最後＝最高優先**。
4. **render（light）**：`_rank_score` 對 `spotlight` 加權（浮上 detailed top-N）、`demote` 扣分（沉到 one-liner）。
5. enrich/render 加 `--no-emphasis` flag 忽略（預設讀取）。

## 非目標

- **LLM 自動解讀自由文字** → 後續。本版 keywords/spotlight/demote 由使用者手填。
- 不改既有 tailor/persona/level/company bias 順序，只在其後追加 emphasis。
- 不新增 light/deep 旗標：深度由「重跑哪個階段」隱含決定（沿用 pipeline 階段獨立性）。
- 不強制 force-list 進 top-N：只靠 rank 加權（足夠大常數）使 spotlight 自然浮入詳述、demote 沉出。

## 架構

### 1. `EmphasisRecord` — `src/vibe_resume/core/emphasis.py`（新檔）

```python
class EmphasisRecord(BaseModel):
    version: int = 1
    intent: str = ""
    keywords: list[str] = []
    bias_instruction: str = ""
    spotlight: list[str] = []      # group names → rank boost
    demote: list[str] = []         # group names → rank penalty

EMPHASIS_PATH = user_root() / "data" / "cache" / "_emphasis.yaml"
_BOOST = 10_000                    # dominates _rank_score (small ints)

def load_emphasis(use: bool = True) -> EmphasisRecord | None     # None if file absent or use=False
def write_emphasis(intent: str) -> EmphasisRecord                # set intent, carry-forward edits
def clear_emphasis() -> bool
def rank_delta(name: str, emphasis: EmphasisRecord | None) -> int # +/-_BOOST/0
def emphasis_block(emphasis: EmphasisRecord) -> str               # the enrich prompt block
```

`write_emphasis` 載入既有檔（若有）只覆寫 `intent`，保留使用者已填的 keywords/spotlight/demote（carry-forward），寫回 YAML。

### 2. enrich 接入

`enricher._build_prompt` 簽名加 `emphasis: EmphasisRecord | None = None`；在 `return body` 前、CONTRIBUTION_BLOCK 之後，若 `emphasis` 且有內容則 `body += emphasis_block(emphasis)`。`enrich_groups` 與 `_do_emit`（→ `emit_jobs`）讀 `load_emphasis(use_emphasis)` 並傳入（`emit_jobs` 亦加 `emphasis` 參數透傳 `_build_prompt`）。

`emphasis_block` 內容（最高優先語氣）：
```
\n\nHIGHEST-PRIORITY EMPHASIS — the candidate wants this résumé to foreground:
{intent}
Surface these themes/keywords where the raw activity supports them (never invent): {keywords}
{bias_instruction}
This emphasis overrides earlier framing on tie-breaks; do not fabricate to satisfy it.\n
```

### 3. render 接入

`renderer._rank_score(g)` 不變（保持純函式可測），在 `_render_md` 排序處改為：

```python
emphasis = load_emphasis(use_emphasis)
groups = sorted(groups, key=lambda g: _rank_score(g) + rank_delta(g.name, emphasis), reverse=True)
```

spotlight 名稱 +_BOOST 浮上 → 落入 `resolved_top_n` 詳述；demote −_BOOST 沉下 → 收合為 one-liner。`rank_delta(name, None)` 回 0（無 emphasis 時行為不變）。

### 4. CLI

- `vibe-resume emphasis "<text>"`：`write_emphasis` → 印確認 + 目前 group 名稱清單（取自 `load_groups`）+ 深度提示（spotlight/demote→light；keywords/bias→deep）。
- `vibe-resume emphasis --clear`：`clear_emphasis`。
- `vibe-resume emphasis`（無參數）：印目前 `_emphasis.yaml`（或「無」）。
- `enrich` / `render` 加 `--no-emphasis`（預設啟用）→ 傳 `use_emphasis=False`。

### 5. config（可選）

`config.example.yaml` 加：
```yaml
emphasis:
  enabled: true     # enrich/render honor _emphasis.yaml when present (--no-emphasis overrides)
```

## 資料流

```
emphasis "<text>"  → _emphasis.yaml(intent + 使用者填 keywords/spotlight/demote)
render             → light:_rank_score + rank_delta 重排,既有 enriched 快取重選 top-N(無 LLM)
enrich             → deep:_build_prompt 注入 EMPHASIS_BLOCK 重寫 bullet → render
```

## 測試計畫

- `EmphasisRecord` load/save round-trip;`write_emphasis` carry-forward（既有 keywords 保留、intent 更新）;`clear_emphasis`。
- `rank_delta`:spotlight→+_BOOST、demote→−_BOOST、其他→0、None→0。
- `emphasis_block`:含 intent/keywords/bias_instruction。
- `_build_prompt(emphasis=...)`:輸出含 EMPHASIS_BLOCK 且位於 company/contribution 之後;無 emphasis 時不含。
- render 排序:spotlight group 浮到 demote group 之前（注入兩個假 group,比較排序 index）。
- CLI:`emphasis "x"` 寫檔、`emphasis --clear` 移除、`--no-emphasis` 使 render 忽略。

## 安全與非破壞

`_emphasis.yaml` 是 sidecar，不改 raw/curated/enriched 快取。`--no-emphasis` 與「檔案不存在」皆回到既有行為（rank_delta=0、無 bias block）。emphasis 永不捏造：prompt 明示「never invent / do not fabricate」。
