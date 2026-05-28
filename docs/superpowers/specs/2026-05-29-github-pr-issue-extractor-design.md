# GitHub PR / Issue Extractor(含 review thread + 開源貢獻偵測)

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#34](https://github.com/easyvibecoding/vibe-resume/issues/34)

## 背景與動因

最豐富的履歷信號 —— *為什麼*做這個改動、權衡了哪些 trade-off、root-cause 分析、真實效能數字 —— 通常住在 **pull-request 描述與 code-review thread**,而不是 commit subject 或 AI session 標題(那是現有 extractor 抓到的大宗)。PR/issue 還佐證跨團隊協作與 code ownership,對 senior/staff 定位很重要。

現有 pipeline 看不到這些。本 extractor 透過已安裝且已登入的 `gh` CLI,為設定的作者收集 PR/issue 標題+內文、作者自己的 review thread 留言,並偵測這是「自己擁有的專案」還是「開源/外部貢獻」。

這個來源能誠實地拉高兩個最弱的 reviewer 檢查項(numbers-per-bullet、top-fold 可量化結果),因為 PR 常帶真實數字,並讓 enricher 寫出 CAR/STAR 式「challenge → decision/trade-off → outcome」bullet。

## 目標

1. 新增 `github` extractor,經 `gh` CLI 收集設定作者的 PR + issue(標題、內文、自己的 review/issue 留言)。
2. PR/issue 與既有 project group **按 repo basename 對齊合併**(同一專案的 commit + PR + review 落同一組)。
3. **偵測擁有權**:`owner` 屬於使用者 → `owned`;否則 → `external`(開源/外部貢獻),並保留此信號供 enricher 與噪音過濾使用。
4. review thread 的 secret 由**既有 `PrivacyFilter` 自動 redact**,extractor 不自行做 redaction。
5. 單一高價值外部 merged PR **不被既有噪音過濾誤丟**。
6. 完全沿用既有 extractor 契約(`NAME` + `extract(cfg) -> list[Activity]`、runner 註冊、cache JSON、失敗隔離)。

## 非目標

- 不引入 PyGithub 或任何 GitHub SDK 依賴(用 `gh` CLI subprocess,沿用 git_repos 的 subprocess 模式)。
- 不自行處理 token / 環境變數(auth 完全交給 `gh`,符合使用者「禁止設定環境變數」規範)。
- 不做 Jira/Linear pluggable issue-tracker 介面(YAGNI;只留乾淨 extractor 邊界,未來要加另開 issue)。
- 不在 render 層新增獨立「Open Source Contributions」區塊(已列為後續 follow-up issue;本 spec 只在資料層保留 `contribution` 信號)。
- 不改 `_project_key` 的全域行為(避免回歸;對齊以保守的 reconcile pass 達成)。
- v1 不做網路回應快取與增量(`--since`)抓取(以 `max_items` + `max_age_days` 界限取代)。

## 已固化決策(brainstorm 對齊結果)

| 決策點 | 結論 |
|---|---|
| Transport / auth | **`gh` CLI subprocess**(不碰 token、不設環境變數;gh 缺席則靜默回 `[]`) |
| 作者身分 | 預設 `--author @me`(gh 當前登入者);config `author_logins` 可覆寫 |
| 抓取範圍 | 全域搜尋使用者所有 PR/issue,再經 `repos_allow`/`repos_block` 過濾;`max_age_days` 限時間窗 |
| 粒度 | **一筆 PR = 一個 Activity**(不按月聚合;PR/issue 完整內容是本 feature 價值) |
| 自己的 review 留言 | 納入(逐 PR 取 comments,只留自己 login 的留言);由 `fetch_comments` 控制 |
| project 對齊 | **按 repo basename 合併**到既有 group;未命中本地 repo 則自成一組(display name = basename) |
| 開源貢獻 | **偵測擁有權**:`owned`/`external` tag;external merged PR 豁免噪音過濾;enricher 框架用「contributed to」 |

## 架構與檔案邊界

```
src/vibe_resume/extractors/local/github.py   ← 新 extractor (NAME="github")
src/vibe_resume/core/schema.py               ← Source 加 GITHUB = "github"
src/vibe_resume/core/runner.py               ← LOCAL_EXTRACTORS 加 "github"
src/vibe_resume/core/aggregator.py           ← 加 _reconcile_github_projects() + _is_meaningful 豁免
src/vibe_resume/core/enricher.py             ← group 級 contribution 框架提示(最小改動)
config.example.yaml                          ← 加 github: 區塊
tests/test_github_extractor.py               ← 新測試(mock gh subprocess)
tests/test_aggregator.py(既有)             ← 加 basename 合併 + external 豁免測試
```

**單一職責切分**:
- `github.py` 只負責「呼叫 gh → 解析 JSON → 偵測擁有權 → 產 Activity」。
- 「對齊到既有 project group」放在 **aggregator**,因為它是唯一同時看到所有 source 的地方(extractor 們平行跑、互看不到彼此 cache)。
- redaction 完全沿用既有 `PrivacyFilter`(aggregate 階段對 `summary`/`keywords`/`files_touched`/`extra` 字串遞迴洗)。

## gh 互動層(可測試的薄殼)

所有 gh 呼叫收斂進單一函式:

```python
def _gh_json(args: list[str], timeout: int = 30) -> Any:
    """subprocess.run(["gh", *args]) → json.loads(stdout)。
    gh 缺席 / 非 0 return / JSON 解析失敗 → 回 None(呼叫端視情況轉 [] 或跳過)。"""
```

測試只 monkeypatch 這一個函式餵 fixture,**完全不碰真網路**。

- **列 PR**(便宜,~1 次呼叫):
  `gh search prs --author <login> --json number,title,body,url,repository,state,createdAt,closedAt,labels,isDraft --limit <N>`
- **列 issue**(`include_issues` 為真時):
  `gh search issues --author <login> --json number,title,body,url,repository,state,createdAt,closedAt,labels --limit <N>`
- **取自己的 review/issue 留言**(`fetch_comments` 為真時,逐 PR/issue):
  `gh api repos/{owner}/{repo}/pulls/{n}/comments` + `gh api repos/{owner}/{repo}/issues/{n}/comments`,只保留 `user.login` ∈ author_logins 的留言。
- **取變更檔**(`fetch_files` 為真時,逐 PR,預設關):
  `gh api repos/{owner}/{repo}/pulls/{n}/files --jq '.[].filename'`。

`<login>` 解析:`author_logins` 非空則逐一查;為空則用 `@me`(gh 內建語法,指當前登入者)。

`gh search prs --json repository` 回傳的 `repository` 物件結構為 `{"name": "...", "nameWithOwner": "owner/repo"}`(**不保證**有 `owner.login` 巢狀欄位)。故 `owner` / `repo` 一律從 `nameWithOwner.split("/")` 解析:`owner = nameWithOwner.split("/")[0]`、`repo = nameWithOwner.split("/")[1]`。

## Activity 映射

| 欄位 | 值 |
|---|---|
| `source` | `Source.GITHUB`(新增 enum 值 `github`) |
| `session_id` | `owner/repo#123` |
| `timestamp_start` | `createdAt` |
| `timestamp_end` | `closedAt`(無則 `createdAt`) |
| `project` | `owner/repo`(交給 aggregator 對齊) |
| `activity_type` | PR → `ActivityType.CODING`;issue → `ActivityType.OTHER` |
| `summary` | `title` + body 摘頭(上限 ~500 字;進 PrivacyFilter) |
| `keywords` | labels |
| `files_touched` | `fetch_files` 為真時的變更檔路徑,否則 `[]` |
| `raw_ref` | PR/issue 的 `url`(html_url) |
| `user_prompts_count` | 自己的留言數(協作信號) |
| `extra` | 見下表 |

`extra` 欄位:

| key | 值 |
|---|---|
| `kind` | `"pr"` / `"issue"` |
| `number` | PR/issue 編號 |
| `repo` | `owner/repo` |
| `repo_owner` | `owner` |
| `contribution` | `"owned"` / `"external"`(見下節) |
| `state` | `open` / `closed` |
| `merged` | bool(PR 是否合併;issue 為 `false`) |
| `is_draft` | bool(PR draft) |
| `body` | PR/issue 內文(進 PrivacyFilter;上限 ~4000 字) |
| `own_comments` | `list[str]` 自己的留言(進 PrivacyFilter) |
| `review_comment_count` | int |

`extra` 內字串值會被 `PrivacyFilter.apply` 遞迴洗(aggregator.py:84-87 已實作),故 review thread 的 secret/連線字串自動 redact。

## 擁有權偵測(owned vs external)

在 extractor 內,對每筆 PR/issue:

```
owner = repository.nameWithOwner.split("/")[0]
owned_set = set(author_logins) ∪ set(config.github.owned_owners)
contribution = "owned" if owner in owned_set else "external"
```

- `author_logins` 為空(用 `@me`)時,先以 `gh api user --jq .login` 解析出實際 login 填入 owned_set。
- `owned_owners` 讓使用者把自己的 org / 公司 org 也標為 owned(這樣公司內部 repo 的 PR 算 owned,不會被當外部 OSS)。

## project 對齊 pass(實現 basename 合併)

在 `aggregate_from_cache` 載入全部 activities 後、bucketing 前,插入 `_reconcile_github_projects(all_acts)`:

1. 從 `Source.GIT` 的 activities 建 `basename(lower) → 本地完整路徑` 對照表(git_repos 的 `project` 是本地路徑;basename = 路徑最後一段)。
2. 對每個 `Source.GITHUB` activity:取其 `extra.repo` 的 repo basename(`owner/repo` 的 `repo` 部分,lower)。
   - **若**在對照表 → 改寫 `act.project` 成對應本地路徑 → bucketing 時與 commit 落同一 `_project_key`。
   - **否則**保留 `owner/repo`(自成一組,`_humanize_name` 會把 display name 收成 basename)。

**保守**:只改寫 GitHub activity、只在 basename 精確命中**本地實有 repo** 時。不動 `_project_key` 全域邏輯,零回歸風險。

## 噪音過濾豁免(保留單一高價值外部 PR)

`_is_meaningful`(aggregator.py:146)現有規則會丟掉 `total_sessions < min_sessions and capability_breadth <= 1` 的 group。一筆對知名 repo 的 merged PR = 1 session → 會被誤丟。

新增豁免:**group 內若存在任一 `extra.contribution == "external"` 且 `extra.merged == True` 的 GitHub activity,則跳過 session 數下限**(其餘 NOISE_SUBSTRINGS / NOISE_LEAFS / hash-id 規則仍套用)。

理由:單一 external merged PR 是強信號(對知名 OSS 的貢獻),不是噪音。非合併的單一 external PR 信號較弱,維持原過濾。

## enricher 框架提示(最小改動)

`core/enricher.py` 組 prompt 時,對每個 group 推導一個 group 級 `contribution`:若該 group 的 GitHub activities 主要為 `external`,在 prompt 加一行框架指示,要求用「**contributed to** X / 為 X 提交 …」而非「built/owned X」措辭。owned 或無 GitHub activity 的 group 不加(維持現狀)。

(basename 合併保證:external-未克隆的 OSS group 為純 external;owned 的本地專案 group 為純 owned;不會混雜。)

## config 旋鈕

```yaml
github:
  enabled: false          # 預設關:會打網路 + 需 gh + 綁帳號,使用者主動開
  author_logins: []        # 空 → gh 當前登入者 (@me)
  owned_owners: []         # 額外視為「自己」的 owner/org(公司 org 等)
  repos_allow: []          # 空 → 全部 repo;非空 → 只收這些 owner/repo
  repos_block: []          # 排除的 owner/repo
  max_age_days: 1095       # ~3 年時間窗
  max_items: 300           # PR+issue 上限,擋 search API rate-limit
  include_issues: true
  fetch_comments: true     # 自己的 review/issue 留言(核心價值)
  fetch_files: false       # 逐 PR 變更檔清單(額外 API 呼叫,預設關)
```

**預設 `enabled: false`** 的理由:它會在每次 `run` 打網路、消耗 search API 配額、且結果綁定 gh 當前登入帳號。與 AIGC api extractor「需憑證者預設關」一致;使用者主動開啟。

## 錯誤處理與 rate-limit

- gh 未裝 / 未登入 / 非 0 return / JSON 解析失敗 → 對應層回 `[]` 或 `None`,**絕不 raise**(runner 已隔離,extractor 自己也 graceful)。
- 逐 PR 取留言/檔案時某次失敗 → 跳過該項的留言/檔案,保留 PR 本體。
- `gh search` 的 `--limit` = `max_items`;`max_age_days` 過濾掉過舊項;結果新到舊排序。三重界限避免打爆 search API(30 req/min)。

## 註冊

`runner.py::LOCAL_EXTRACTORS` 加入 `"github"`(它用本地 `gh` binary,歸類 local;載入路徑 `vibe_resume.extractors.local.github`)。config key = `"github"`,經既有 `_enabled(cfg, "github")` 閘控。

## 測試(TDD,mock `_gh_json`)

`tests/test_github_extractor.py`:
- happy path:PR + issue + 自己的留言 fixture → 正確 Activity(欄位、session_id、timestamps、extra)。
- 擁有權偵測:owner == login → `owned`;owner 為他人 → `external`;owner ∈ `owned_owners` → `owned`。
- gh 缺席(`_gh_json` 回 None / FileNotFoundError)→ `extract` 回 `[]`。
- 逐 PR 留言抓取部分失敗 → 該 PR 保留、無留言,不整批掛。
- `repos_allow` / `repos_block` 過濾。
- `max_age_days` 過濾掉過舊 PR。
- 只保留自己 login 的留言(他人留言被濾掉)。
- `include_issues: false` → 不抓 issue。
- `fetch_files: false`(預設)→ 不呼叫 files 端點、`files_touched` 為 `[]`。

`tests/test_aggregator.py`(既有檔加測試):
- basename 合併:GitHub PR(`acme/myapp`)+ 同名本地 git repo(`/.../code/myapp`)→ 一個 group。
- 未命中:GitHub PR 的 repo 無本地對應 → 自成一組,display name = basename。
- redaction smoke:`extra.body` 塞 `sk-` 開頭 secret → aggregate 後變 `[REDACTED]`。
- external 豁免:單一 external merged PR(1 session)→ **不被** `_is_meaningful` 丟;單一 external 非合併 PR → 仍被丟。

## 後續 follow-up(本 spec 不含)

- render 層獨立「Open Source Contributions」區塊(動 10 個 locale 模板)。
- GraphQL 批次抓取以降低逐 PR 呼叫數。
- 網路回應快取 / `--since` 增量抓取。
- Jira/Linear pluggable issue-tracker 介面。
