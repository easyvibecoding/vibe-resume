<p align="center">
  <img src="docs/assets/logo.png" width="120" alt="vibe-resume logo">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>日本語</strong>
</p>

# vibe-resume

> AI コーディング履歴をバージョン管理された、レビュー用意の整った履歴書に変換する —— **vibe coding 時代のために**。

[![CI](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml/badge.svg)](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Locales](https://img.shields.io/badge/locales-10-brightgreen.svg)](docs/resume_locales.md)
[![uv](https://img.shields.io/badge/packaged%20with-uv-261230.svg)](https://github.com/astral-sh/uv)

![vibe-resume hero — AI ツールのセッションが extract→aggregate→enrich→render を経て 10 言語の履歴書になる](docs/assets/hero.png)

`vibe-resume` は、macOS 上で使用したあらゆる AI アシスタント(Claude Code、Cursor、GitHub Copilot、Cline、Continue、Aider、Windsurf、Zed AI、ChatGPT / Claude.ai / Gemini / Grok / Perplexity / Mistral のクラウドエクスポート、さらに ComfyUI、Midjourney、Suno、ElevenLabs、そして `git` コミット)をスキャンし、その利用履歴を **Markdown / DOCX / PDF の履歴書**にまとめます。git スナップショットが組み込まれているので、草稿のすべてのバージョンを差分表示・ロールバックできます。

## 他ツールとの違い

| | vibe-resume | Reactive Resume / OpenResume | Resume-LM / Resume Matcher | HackMyResume / JSON Resume |
|---|---|---|---|---|
| **主シグナル** | AI ツールセッション + git コミット(自動抽出) | ユーザーが手入力する WYSIWYG | アップロード PDF + JD | ユーザー手書きの JSON |
| **ロケール数** | **10** (en_US/en_EU/en_GB/zh_TW/zh_HK/zh_CN/ja_JP/ko_KR/de_DE/fr_FR) 各文化対応レイアウト | 1–2 | 1 | theme 依存 |
| **JIS Z 8303 履歴書グリッド** | ✅ `render/japan.py` | ❌ | ❌ | ❌ |
| **Europass ラベル付き個人情報** | ✅ `en_EU` テンプレート | ❌ | ❌ | ❌ |
| **レビュー監査** | 8 項目スコアカード + トレンドスパークライン | — | ATS スコアのみ | — |
| **JD テーラリング** | `enrich --tailor JD.txt`(LLM プロンプト注入) | — | ✅ LLM 書き直し | — |
| **プライバシー** | 完全ローカル;`claude -p` ヘッドレス、データは手元から出ない | 状況による(OpenAI キー任意) | クラウド API 必須 | 完全ローカル |
| **形態** | Python CLI パイプライン | Web UI | Web UI | Node CLI |

## なぜ

2026 年の採用は、「Claude Code」を単にスキルとして並べるのではなく、**AI 協業による生産性を定量成果で証明できる**エンジニアを重視します。レビュアーは、アーキテクチャ判断、スタック横断の幅(フロントエンド / バックエンド / DevOps / バグ修正 / デプロイ)、そして出荷スピードを見ています。あなたの AI ツールはすでにこれらを自動で記録しています。`vibe-resume` はその「使用の残滓」を証拠に変えます。

## 機能

### ローカル extractor(ログイン不要)
| ソース | 場所 |
|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| Claude Code Archive | `~/ClaudeCodeArchive/current`(任意の rsync バックアップ) |
| Cursor | `~/Library/Application Support/Cursor/User/**/state.vscdb` |
| GitHub Copilot (VS Code) | `workspaceStorage/**/chatSessions/` |
| Cline | `globalStorage/saoudrizwan.claude-dev/` または `~/.cline/data/` |
| Continue.dev | `~/.continue/sessions/` |
| Aider | `$HOME/**/.aider.chat.history.md` |
| Windsurf / Cascade | `~/.codeium/windsurf/cascade/` |
| Zed AI | `~/.local/share/zed/threads/` |
| Claude Desktop | MCP 設定 + extensions |
| Git コミット | `$HOME` 配下のすべての `.git` を author email でフィルタ |

### クラウドエクスポート取り込み(ZIP を `data/imports/<tool>/` に置く)
ChatGPT · Claude.ai · Gemini Takeout · Grok · Perplexity · Mistral Le Chat · Poe

### AIGC extractor
`image_local`(ComfyUI / A1111 PNG メタデータ)· `midjourney`(IPTC/XMP)· `elevenlabs`(history API)· `suno`(ローカル MP3 ID3)· `runway` / `heygen`(stub)

### 履歴書インテリジェンス
- **タスク分類器** —— 各セッションを frontend / backend / bug-fix / deployment / refactor / testing などにタグ付け
- **能力の幅** —— プロジェクトごとの相異カテゴリ数を数え、マルチスキル人材を可視化
- **30 日ローリング統計** —— アクティブ日数比、日平均、ピーク日、最長連続日(Claude Code の 30 日クリーンアップと整合)
- **XYZ エンリッチャー** —— Claude Code CLI をヘッドレスで呼び出し、ノイジーな活動を Google 風の履歴書箇条書きに変換
- **技術スタック正規化** —— `postgres` → `PostgreSQL`、`tailwind` → `Tailwind CSS`
- **ハードスキル vs ドメインタグ分離** —— ATS キーワードを綺麗に保つ
- **プライバシーフィルタ** —— regex 遮蔽 + プロジェクトブロックリスト + 任意の技術抽象化
- **バージョン管理出力** —— `data/resume_history/` 配下の内部 git リポに `list-versions` / `diff v1 v2` / `rollback`

## クイックスタート

```bash
# 1. インストール
uv venv && uv pip install -e ".[dev]"

# 2. プロフィール入力
cp profile.example.yaml profile.yaml
$EDITOR profile.yaml        # 最低でも name / target_role

# 3. (任意)クラウド ZIP エクスポートを data/imports/<tool>/ に配置

# 4. パイプライン実行
uv run python cli.py extract          # 有効化されているすべての extractor
uv run python cli.py aggregate        # プロジェクト分類 + スタック推定
uv run python cli.py enrich           # claude -p で XYZ 箇条書き生成
uv run python cli.py render -f all    # md + docx + pdf + git スナップショット
```

## コマンド

| コマンド | 機能 |
|---|---|
| `cli.py extract [--only NAME]` | extractor 実行、`data/cache/*.json` にキャッシュ |
| `cli.py aggregate` | プロジェクト分類、タスクカテゴリ、スタック推定 |
| `cli.py enrich [-n N] [--locale L] [--tailor JD.txt]` | summary + achievements 生成(英語は XYZ、中日独仏韓は名詞句);`--tailor` で bullet を JD キーワード寄りに |
| `cli.py render -f md\|docx\|pdf\|all [--locale L]` | レンダリング + git スナップショット |
| `cli.py render --all-locales [-f FMT]` | 登録済みロケール全てを一括レンダリング |
| `cli.py render --tailor data/imports/jd.txt` | 特定 JD 用にテーラリング |
| `cli.py review [-v N \| --file PATH] [--locale L] [--jd JD.txt]` | 8 項目レビュアーチェックでスコアリング |
| `cli.py trend [--locale L]` | ロケール別スコア履歴、平均、最新評価 |
| `cli.py completion {bash\|zsh\|fish} [--install]` | シェル補完スクリプト出力/インストール |
| `cli.py status` | ソース別のアクティビティ数 |
| `cli.py list-versions` / `cli.py diff 1 2` | 履歴書バージョン履歴 |

## 多言語ロケールレンダリング

`vibe-resume` は各ロケール専用テンプレートを内蔵し、同じ `profile.yaml` とプロジェクトデータから、各地域のレビュアーが期待する版面を出力します。

```bash
uv run python cli.py render -f md  --locale en_US     # ATS 最適化 US デフォルト
uv run python cli.py render -f md  --locale ja_JP     # 職務経歴書(md/pdf)
uv run python cli.py render -f all --locale ja_JP     # 履歴書 DOCX グリッド + 職務経歴書
uv run python cli.py render -f md  --locale de_DE     # Persönliche Daten 付き Lebenslauf
```

| ロケール | スタイル | 写真 | 見出し例 | 特色 |
|---|---|---|---|---|
| `en_US`(デフォルト) | XYZ 動詞起点 | 禁止 | Summary / Skills / Experience / … | フラットな ATS 対応スキル行 |
| `en_EU` | XYZ 動詞起点 | 任意 | Personal information / Work experience / Education and training / … | Europass スタイル —— ラベル付き個人情報、CEFR、GDPR 極小化(DOB はデフォルト非表示) |
| `en_GB` | XYZ 動詞起点 | 禁止 | Personal statement / … | イギリス綴り、CEFR |
| `zh_TW` | 名詞句 | 任意 | 自我介紹 / 技能專長 / 工作經歷 / … | 繁体、全角分隔、中英技術混在 |
| `zh_HK` | 名詞句 | 任意 | Personal Profile 個人簡介 / Work Experience 工作經驗 / … | **バイリンガル見出し EN + 繁**、CEFR、HKID は出力しない |
| `zh_CN` | 名詞句 | 任意 | 个人简介 / 专业技能 / … | 簡体、大企業向け(アメリカ寄り) |
| `ja_JP` | 名詞句 | **必須** | 職務要約 / 職務経歴 / … | DOCX = JIS Z 8303 履歴書グリッド(`render/japan.py`)、md = 職務経歴書 |
| `ko_KR` | 名詞句 | **必須** | 자기소개 / 보유 기술 / 경력 / … | 자기소개서は別ドキュメント扱い |
| `de_DE` | 名詞句 | **必須** | Persönliche Daten / Berufserfahrung / … | `dob` / `nationality` が入力されたときのみ出力 |
| `fr_FR` | 名詞句 | 任意 | Profil / Compétences / Expérience / … | ジュニア 1 ページ、シニア 2 ページ |

### ロケール別テキスト上書き

`UserProfile` は `extra="allow"` なので、任意の `<field>_<locale>` キーが英語原フィールドと並存でき、テンプレートは `localized` Jinja フィルタで正しいものを選びます:

```yaml
title: "Senior Full-stack Engineer"
title_ja_JP: "シニアフルスタックエンジニア"
title_zh_TW: "資深全端工程師"

summary: "Full-stack engineer who…"
summary_ja_JP: "FastAPIとpgvectorを核にRAG検索基盤を設計し…"

experience:
  - title: "Senior Full-stack Engineer"
    title_ja_JP: "シニアフルスタックエンジニア"
    company: "Lumen Labs"
    company_ja_JP: "Lumen Labs(シード期 AI SaaS)"
    bullets:
      - "Reduced query latency from 1.8s to 620ms..."
    bullets_ja_JP:
      - "クエリ中央値レイテンシを 1.8 秒から 620 ミリ秒に短縮…"
```

任意のロケール条件個人情報フィールド(`dob` / `gender` / `nationality` / `mil_service` / `photo_path` / `marital_status`)は `profile.example.yaml` で解説されています。(a) 現在のロケールの `personal_fields` に該当キーがあり、(b) 値が空でないときだけ出力されます。

設計判断と各ロケールのフィールド対応表は `docs/resume_locales.md` に集約しています。

### ロケール解決チェーン

レンダラーは以下の順にロケールを決定し、最初に値がある箇所で停止します:

1. CLI の `--locale`(最優先)
2. `profile.yaml` の `profile.preferred_locale`
3. `config.yaml` の `config.render.locale`
4. `en_US` フォールバック

```yaml
# profile.yaml —— CLI が上書きしない限り ja_JP で出力
preferred_locale: ja_JP

# config.yaml —— チーム共通デフォルト
render:
  locale: en_US
  all_locales_formats: ["md", "docx"]   # --all-locales が各ロケール用に出す形式
```

`cli.py render --locale zh_TW` は常に `preferred_locale` を上書きし、省略時は `preferred_locale` が引き継ぎます。`enrich` が LLM を呼ぶ際も同じチェーンを通るため、どのノブを回しても言語ラベルが正しく注入されます。

### 全ロケールの一括レンダリング

市場ごとに一式を用意したい最終日:

```bash
uv run python cli.py render --all-locales                 # config.render.all_locales_formats を使用
uv run python cli.py render --all-locales -f docx         # フォーマットを強制
uv run python cli.py render --all-locales --tailor jd.txt # 1 つの JD を全ロケールに適用
```

`--all-locales` は `LOCALES` レジストリ全体(現在 10 件)を走査します。各ロケールの出力形式は `config.render.all_locales_formats`(デフォルト `["md"]`)で管理され、`["md", "docx", "pdf"]` にすればフルセットを一気に生成できます。`--locale` と `--all-locales` は排他です。

## レビュアー視点の監査(`cli.py review`)

![8 項目の自動レビュアースコアカードとレンダリング済み履歴書、トレンドスパークライン](docs/assets/reviewer_audit.png)

レンダリング後、実際のレビュアーと同じ 8 項目チェックリストでスコアリングします:

```bash
uv run python cli.py review                    # 最新版
uv run python cli.py review -v 9               # 特定バージョン
uv run python cli.py review -v 12 --jd jd.txt  # JD キーワード一致度を追加
```

各草稿は以下の 8 項目で評価されます:

1. **Top fold** —— 氏名、志望職種、1 つ以上の具体的指標が最初の 12 行以内にあるか
2. **Numbers per bullet** —— 職務経歴 bullet の 60% 以上に定量指標があるか
3. **Keyword echo (JD)** —— JD の主要な大文字語が草稿に現れているか(`--jd` が無ければスキップ)
4. **Action-verb first** —— XYZ ロケールで bullet が過去形動詞で始まるか
5. **Density (noun-phrase)** —— 名詞句ロケールで bullet が自己完結し、宙に浮いた代名詞が無いか
6. **Red flags** —— ロケール別に写真 / DOB / "References available upon request" / 連続見出しなどを検査
7. **Contact line width** —— ヘッダー行が印刷幅で折り返して崩れないか(CJK 文字は 2 倍幅)
8. **Page count** —— 行数と折り返しから推定するページ数 vs ロケール推奨(US/UK ≤2、DE/JP/KR ≤3)

`data/reviews/<draft>_review.md` と `.json` を出力し、版をまたいで diff 可能です。実在のレビュアーに提出する前は B/(80%) 以上が目安。

### スコアトレンド(`cli.py trend`)

`review` を走らせるたびに `data/reviews/` に JSON が残り、`trend` はそれをロケール別にまとめて、どの市場バージョンが進歩/後退しているかを一目で示します:

```bash
uv run python cli.py trend               # 全ロケール
uv run python cli.py trend --locale ja_JP
```

```
 Locale  Runs  First    Latest        Mean    Grade  Trend
 en_US   6     58/80    v16: 78/80    91.0%   A      ▂▅▆▇██
 ja_JP   3     50/80    v14: 72/80    82.5%   A      ▁▅█
 zh_TW   4     42/80    v15: 74/80    85.0%   A      ▁▃▆█
```

スパークラインは U+2581..U+2588 の Unicode ブロックで描画され、どの等幅端末でも崩れません。列は: 実行回数、初回スコア、最新スコア(バージョン番号付)、実行全体の平均 %、最新の評価、実行ごとの推移。

## Claude Code 30 日クリーンアップ —— 重要

Claude Code はデフォルトで 30 日以上経過したセッション JSONL を削除します。長期保存したい場合は:

```bash
# 1. 保持日数を伸ばす
python3 -c "import json,pathlib; p=pathlib.Path.home()/'.claude/settings.json'; \
  d=json.loads(p.read_text()); d['cleanupPeriodDays']=365; \
  p.write_text(json.dumps(d,indent=2,ensure_ascii=False))"

# 2. 定期 rsync バックアップ(スクリプト同梱)
chmod +x scripts/backup_claude_projects.sh
./scripts/backup_claude_projects.sh
# launchd / cron に週次で登録
```

### Windows バックアップ(Task Scheduler)

`scripts/backup_claude_projects.ps1` は PowerShell 7 版の同等スクリプトで、`robocopy /MIR /XO` により `%USERPROFILE%\.claude\projects` を `%USERPROFILE%\ClaudeCodeArchive\current` にミラーし、日付つきスナップショットも保存します:

```powershell
# 単発実行
pwsh -NoProfile -File scripts\backup_claude_projects.ps1

# ドライラン(macOS/Linux でも動くので冒煙テストに便利)
pwsh -NoProfile -File scripts\backup_claude_projects.ps1 -WhatIf

# 週次タスクとして登録(毎週日曜 03:00)
schtasks /Create /TN "vibe-resume backup" /XML scripts\vibe-resume-backup.xml
```

`scripts/vibe-resume-backup.xml` は Task Scheduler にそのまま取り込めるテンプレートです。取り込み前に `<WorkingDirectory>` を実際の clone 先に書き換えてください。CI は `windows-latest` で `PSScriptAnalyzer` による厳格検査と `-WhatIf` ブランチの実行を行っています。

## プロジェクト構成

```
vibe-resume/
├── profile.yaml           # 個人情報(gitignored)
├── config.yaml            # extractor スイッチ、パス、プライバシー規則、ウィンドウ
├── cli.py                 # エントリーポイント
├── core/
│   ├── schema.py          # Pydantic v2: Activity、ProjectGroup、UserProfile
│   ├── classifier.py      # 18 タスクカテゴリ(バイリンガル regex)
│   ├── tech_canonical.py  # ハードスキル vs ドメインタグ
│   ├── stats.py           # ローリング統計(30d/7d)
│   ├── privacy.py         # 遮蔽 + ブロックリスト + 技術抽象
│   ├── aggregator.py      # 分類 + headline + 重要度ランキング
│   ├── enricher.py        # claude -p → XYZ bullet
│   ├── versioning.py      # 草稿の git スナップショット
│   └── runner.py
├── extractors/
│   ├── local/             # 11 個のローカル extractor
│   ├── cloud_export/      # 7 個の ZIP インポーター
│   └── api/               # 6 個の AIGC extractor
├── render/
│   ├── renderer.py        # md / docx / pdf
│   └── templates/resume.md.j2
├── scripts/
│   ├── backup_claude_projects.sh       # macOS / Linux rsync
│   ├── backup_claude_projects.ps1      # Windows PowerShell 7(robocopy)
│   ├── vibe-resume-backup.xml          # Task Scheduler 取り込みテンプレート
│   └── com.vibe-resume.backup.plist    # macOS launchd agent
├── data/
│   ├── imports/           # ダウンロードした ZIP を置く
│   ├── cache/             # ソース別 extractor JSON(gitignored)
│   └── resume_history/    # レンダリング出力 + 内部 git(gitignored)
└── .claude/skills/ai-used-resume/SKILL.md   # Claude Code Agent Skill
```

## 新しい extractor を追加する

```python
# extractors/local/mytool.py
from core.schema import Activity, ActivityType, Source
NAME = "mytool"
def extract(cfg: dict) -> list[Activity]:
    return []  # Activity オブジェクトを返す
```

`core/runner.py` の `LOCAL_EXTRACTORS` に登録し、`config.yaml` で有効化するだけです。

## 既知の制約

- 全 `$HOME` スキャン(`git_repos`、`aider`)は初回 1–3 分かかります —— `scan.mode: whitelist` に切り替えると範囲を絞れます。
- Grok / Perplexity / Mistral のエクスポート schema は**緩く解析**しています(公式スキーマが未公開のため)。フィールドが合わない場合は `data/imports/` に実サンプルを置いてください。
- Claude Desktop のチャット本文は Local Storage に暗号化されています —— MCP 設定 + extensions のみ取得可能です。
- PDF レンダリングで CJK を出すには `pandoc` + XeLaTeX が必要です。無い場合は素の pandoc にフォールバックします。

## ライセンス

MIT —— [LICENSE](LICENSE) を参照。

## 関連プロジェクト

- [sujankapadia/claude-code-analytics](https://github.com/sujankapadia/claude-code-analytics) —— セッション分析ダッシュボード
- [yudppp/claude-code-history-mcp](https://github.com/yudppp/claude-code-history-mcp) —— MCP history server
- [alicoding/claude-parser](https://github.com/alicoding/claude-parser) —— Git-like conversation API
- [daaain/claude-code-log](https://github.com/daaain/claude-code-log) —— HTML タイムライン
- [S2thend/cursor-history](https://github.com/S2thend/cursor-history) —— Cursor チャットエクスポート
- [AndreaCadonna/resumake-mcp](https://github.com/AndreaCadonna/resumake-mcp) —— LaTeX 履歴書 MCP

`vibe-resume` の差別化ポイントは、**ツールを横断して集約**し、生データの dump ではなく「履歴書向け」の bullet を生成することです。
