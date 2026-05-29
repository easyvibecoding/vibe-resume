# Canonical-key 跨路徑專案去重（同一 repo 多處工作目錄合併）

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#37](https://github.com/easyvibecoding/vibe-resume/issues/37)
**Milestone**: 0.8.0（先獨立出貨；其 canonical-key 引擎供 #38 `curate` gate 重用）

## 背景與動因

`aggregate` 目前以 activity 的**路徑**（`_project_key`：取路徑後兩段）分組，所以**同一個邏輯 repo** 在多個位置工作時，會產生多個永不合併的 group。履歷因此把一個專案重複計成兩筆（或把高 session 的專案拆成數個小的而被埋沒）。

真實會發生、今日仍被拆開的型態：

1. **同 repo、兩個工作目錄** — 例如同一 repo 同時 checkout 在 `~/dev/foo` 與 `~/side/foo`（或目錄改名）。兩者 `git remote get-url origin` 相同、commit 歷史相同，卻成兩個 group。最糟：專案在履歷上出現**兩筆獨立的詳述條目**。
2. **子套件當成獨立 cwd** — 例如 `repo/packages/x` 或 `repo/client`。從該路徑 `git rev-parse --show-toplevel` 會回到母 repo，卻被當成獨立專案。
3. **同 basename、不同母目錄** — 例如 `~/work/CRM`（git+github）與 `~/test/CRM`（codex 工作副本）。同專案，兩個 group。
4. **sanitized/備份快照目錄** — 例如 `foo` 與 `foo-sanitized-YYYYMMDD`，同 remote，計兩次。

0.7.0 的 `_reconcile_github_projects` 只把 **GitHub PR** activity 依 repo basename 併進本地 group（#34），**不**處理兩個*本地* group（git / claude-code / codex / CLI session）其實是同一 repo 的情形。本 spec 補上這塊。

## 目標

1. 為「路徑帶有 git 身分」的 activity，在 **extract 時**捕捉其 git **remote**（正規化）與 **toplevel**，存入 `Activity.extra`。
2. aggregator 依 **canonical key**（remote → toplevel → 既有路徑 key 的優先序）把同一邏輯 repo 的所有 group **合併為一**，union 其 activities/sessions/sources/tech/日期範圍（沿用既有分組，靠改寫 `project` 達成，仿 A5）。
3. **過度合併防護**：只用身分證明（remote / toplevel）合併，絕不用 basename / name-prefix。
4. 完全非破壞：`_project_groups.json` 的產生邏輯不變，raw activity 不被破壞；無 git 身分或路徑已消失時，行為與今日完全相同（fallback 既有路徑 key）。
5. canonical-key 推導邏輯做成**可重用 helper**，供 #38 的 `curate` auto-merge tier 直接沿用。

## 非目標

- **`project_aliases` 手動映射**（no-remote 的兩個 clone 無法自動證明同一性時的手動對應）— #37 不做。#38 issue 明述此 fallback「lives here（#38 的 curate gate）」，故列為 out-of-scope，spec 標註。
- **把 GitHub activity 也統一進同一 canonical key** — 維持 0.7.0 的 GitHub basename reconcile 不動，避免擴大範圍（未來可在 #38 統一）。
- 不引入新依賴（沿用 `subprocess` + `gh`/`git` CLI 模式）。
- 不改任何 CLI 行為旗標 / pipeline 階段（僅 aggregate 內部多一個 reconcile pass）。

## 架構

三層，新增一個共用 helper、三個 extractor 各加一次捕捉、aggregator 加一個 reconcile pass。

### 1. 共用 helper：`extractors/base.py::git_identity(path, cache) -> (remote | None, toplevel | None)`

對給定路徑解析 git 身分，集中正規化邏輯（DRY；三個 extractor 共用一份規則）。

- `git -C <path> rev-parse --show-toplevel` → `toplevel`（同時判定是否在 git work-tree；非 work-tree → 回 `(None, None)`）。
- `git -C <path> remote get-url origin` → 正規化後得 `remote`（可能 None：work-tree 但無 origin）。
- **memoize**：以 `path` 為 key 用傳入的 `cache: dict` 快取（claude_code / codex 大量 session 常共用同一 cwd，避免重複 shell）。
- **安全**：每次 git 呼叫 5s timeout；`FileNotFoundError` / `SubprocessError` / 非零退出 → 該項視為 None；整體絕不拋例外。

#### 正規化規則（remote）

把不同寫法的同一 remote 收斂成單一字串：

- 去 scheme：`https://`、`http://`、`ssh://`、`git://`、`git@`（SCP 式 `git@host:owner/repo`）
- host-alias 正規化：SSH host 別名（如 `github-easyvibecoding`）與真實 host 視為等價 —— 做法：取「host + path」後，**只比對 path 段（owner/repo）並保留 host 的註冊域名**。實作上採保守規則：strip 已知 alias 前綴差異、統一 `:` 與 `/` 分隔（`git@github.com:owner/repo` → `github.com/owner/repo`）。
- 去結尾 `.git`
- 全轉小寫、去結尾 `/`

範例：`git@github.com:Acme/Project-A.git`、`https://github.com/acme/project-a` → 皆為 `github.com/acme/project-a`。

> host-alias 完全等價化（`github-easyvibecoding:` ↔ `github.com/`）需要讀 `~/.ssh/config`，超出本 spec 範圍；採「分隔符正規化 + `.git`/大小寫」即可覆蓋絕大多數真實案例。剩餘極端 alias 差異留給 #38 的 `project_aliases`。

### 2. 三個 extractor 在 extract 時捕捉

各自對其專案路徑呼叫 `git_identity`，把結果寫入 `extra`（None 則不寫該鍵）：

- `git_repos`：repo 路徑本身即 work-tree root → `extra["git_remote"]` / `extra["git_toplevel"]`。每個 repo 一次（repos 已去重）。
- `claude_code`：對 `cwd`（session 的 `cwd`）呼叫；cwd 可能是子套件，`toplevel` 會解析到母 repo（覆蓋型態 2）。
- `codex`：同 `claude_code`，對 `cwd` 呼叫。

每個 extractor 在 `extract()` 內建一個 `cache: dict` 傳給 `git_identity`，跨同檔案的多 session 共用。

### 3. aggregator：canonical key + reconcile pass

接在 `_reconcile_github_projects(all_acts)` **之後**（先做本地 canonical 合併，GitHub basename reconcile 維持原樣）：

- `_canonical_key(act) -> str | None`：
  1. `extra["git_remote"]` 有值 → `f"remote:{git_remote}"`
  2. 否則 `extra["git_toplevel"]` 有值 → `f"toplevel:{git_toplevel}"`
  3. 否則 → `None`（走既有路徑 `_project_key`，行為不變）
- `_reconcile_local_projects(acts) -> None`：
  - 以 canonical key 把 activities 分群（key 為 None 的略過）。
  - 每個 cluster 選一個**代表路徑**：優先取 cluster 中出現過的 `git_toplevel`（真實目錄 root），否則取最高頻的 `act.project`。
  - 把 cluster 內所有 activity 的 `act.project` 改寫成代表路徑 → 既有 `_project_key` 分組自然收斂成一組（仿 A5「改寫 project」手法，display/headline 邏輯不受影響）。

### 過度合併防護

只用 `remote:` / `toplevel:` 鍵合併。兩個都叫 `test` 但 remote 不同 → 不同 canonical key → 不併；`foo` / `foo-cron` / `foo-landing` remote 各異 → 各自獨立。防護內建於「以 remote/toplevel 為 key」，不需額外規則。no-remote 且 toplevel 不同的兩個 clone 無法自動證同 → **保持分開**（這正是 #38 `project_aliases` 要解的案例）。

## 資料契約（`Activity.extra` 新鍵）

| 鍵 | 型別 | 說明 |
|---|---|---|
| `git_remote` | `str`（正規化）| work-tree 的 origin remote；無則不寫 |
| `git_toplevel` | `str`（絕對路徑）| `git rev-parse --show-toplevel`；非 git work-tree 則不寫 |

兩者皆 optional、向後相容（舊 cache 無此鍵 → canonical key 回 None → 行為同今日）。`PrivacyFilter` 對 str 值已會 redact，但 remote/toplevel 通常不含 secret；不需特別處理。

## 測試計畫

- **`tests/test_extractors_base.py`（或既有）**：`git_identity`
  - 正規化：scheme（https / ssh / `git@` SCP 式）、`:` ↔ `/`、結尾 `.git`、大小寫 → 同一字串
  - work-tree 無 origin → `(None, toplevel)`
  - 非 git work-tree（rev-parse 非零）→ `(None, None)`
  - memoize：同 path 只 shell 一次（用 call counter 驗證）
  - git 不存在 / timeout → `(None, None)`，不拋例外
- **`tests/test_aggregator.py`**：`_canonical_key` + `_reconcile_local_projects`
  - 同 remote、不同路徑（型態 1）→ 合併成一組
  - 子套件 `toplevel` 指向母 repo（型態 2）→ 併入母 repo
  - **同 basename、不同 remote → 不併**（過度合併防護）
  - no-remote、不同 toplevel → 不變（保持分開）
  - 代表路徑選擇：優先 toplevel
- **既有 extractor 測試（重要 — 同 B1 的相依修復）**：三個 extractor 現在多一次 git 呼叫
  - 既有測試的 `fake_run` 需依**子指令分派**（新增 `rev-parse` / `remote` 回應），否則 git log 的假輸出會被誤當 remote 解析
  - `test_git_repos_parses_numstat`、`claude_code` / `codex` happy-path 必須續綠

## 效能與安全

- git 呼叫次數上界：git_repos = 去重後 repo 數；claude_code / codex = 去重 cwd 數（memoize）。每次最多 2 個 git 子呼叫（rev-parse + remote），5s timeout。
- 失敗、路徑消失、無 git → 一律 fallback 既有路徑 key，非破壞。
- aggregate 不再額外 shell（key 來自 extract 時已存的 extra），符合「key 計算在 extract 時」的決策。

## 與後續（#38）的關係

`_canonical_key` 與 `git_identity` 即 #38 `curate` gate 的 **auto-merge tier 引擎**；`_curation.yaml` 的 `canonical_key` 欄位直接來自此處。no-remote 手動對應（`project_aliases`）與 needs_decision 人工確認層，全部留給 #38。
