<p align="center">
  <img src="docs/assets/logo.png" width="120" alt="vibe-resume logo">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <strong>简体中文</strong> ·
  <a href="README.ja.md">日本語</a>
</p>

# vibe-resume

> 把你的 AI 协作历史变成可版本化、审核友好的简历 —— **for the vibe coding era**。

[![CI](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml/badge.svg)](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Locales](https://img.shields.io/badge/locales-10-brightgreen.svg)](docs/resume_locales.md)
[![uv](https://img.shields.io/badge/packaged%20with-uv-261230.svg)](https://github.com/astral-sh/uv)

![vibe-resume hero — AI 工具会话流经 extract→aggregate→enrich→render 生成 10 语简历](docs/assets/hero.png)

`vibe-resume` 扫描你 macOS 上用过的所有 AI 助手(Claude Code、Cursor、GitHub Copilot、Cline、Continue、Aider、Windsurf、Zed AI,以及 ChatGPT / Claude.ai / Gemini / Grok / Perplexity / Mistral 的云端导出,还有 ComfyUI、Midjourney、Suno、ElevenLabs 以及你的 `git` commit),将使用轨迹整合为 **Markdown / DOCX / PDF 简历**,并内置 git 快照,让每一版草稿都能 diff 和回滚。

## 与其他工具的差异

| | vibe-resume | Reactive Resume / OpenResume | Resume-LM / Resume Matcher | HackMyResume / JSON Resume |
|---|---|---|---|---|
| **主要信号源** | AI 工具会话 + git commit(自动提取) | 用户手填的 WYSIWYG 内容 | 上传 PDF + JD | 用户手写 JSON |
| **Locale 数** | **10** (en_US/en_EU/en_GB/zh_TW/zh_HK/zh_CN/ja_JP/ko_KR/de_DE/fr_FR) 含文化专属排版 | 1–2 | 1 | 看 theme |
| **日本 JIS Z 8303 履歴書栅格** | ✅ `render/japan.py` | ❌ | ❌ | ❌ |
| **Europass 带标签个人资料** | ✅ `en_EU` 模板 | ❌ | ❌ | ❌ |
| **简历审核器** | 8 项评分表 + 趋势稀疏图 | — | 仅 ATS 分数 | — |
| **JD 定制** | `enrich --tailor JD.txt`(LLM prompt 注入) | — | ✅ LLM 重写 | — |
| **隐私** | 全本地;`claude -p` 无头模式,数据不出本机 | 视情况(可选 OpenAI key) | 必须走云端 API | 全本地 |
| **形态** | Python CLI pipeline | Web UI | Web UI | Node CLI |
| **Agent-Skill 兼容 host 数** | **8**(Claude Code · Gemini CLI · Copilot CLI · Cursor · Warp · OpenClaw · OpenCode · Hermes)—— 单一 canonical SKILL.md | — | — | — |

## 为什么

2026 年的招聘更青睐能**用量化成果证明 AI 协作生产力**的工程师,而不是简单在简历上罗列「Claude Code」作为技能。审核者想看到架构决策、跨栈广度(前端 / 后端 / DevOps / 修 bug / 部署),以及你交付的速度。你的 AI 工具其实已经自动记录了这一切。`vibe-resume` 把这些「使用痕迹」转换成可用的证据。

## 功能

### 本地 extractor(免登录)
| 来源 | 路径 |
|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| Claude Code Archive | `~/ClaudeCodeArchive/current`(可选 rsync 备份) |
| Cursor | `~/Library/Application Support/Cursor/User/**/state.vscdb` |
| GitHub Copilot (VS Code) | `workspaceStorage/**/chatSessions/` |
| Cline | `globalStorage/saoudrizwan.claude-dev/` 或 `~/.cline/data/` |
| Continue.dev | `~/.continue/sessions/` |
| Aider | `$HOME/**/.aider.chat.history.md` |
| Windsurf / Cascade | `~/.codeium/windsurf/cascade/` |
| Zed AI | `~/.local/share/zed/threads/` |
| Claude Desktop | MCP 配置 + extensions |
| Git commit | `$HOME` 里所有 `.git`,按 author email 过滤 |

### 云端导出导入器(将 ZIP 丢到 `data/imports/<tool>/`)
ChatGPT · Claude.ai · Gemini Takeout · Grok · Perplexity · Mistral Le Chat · Poe

### AIGC extractor
`image_local`(ComfyUI / A1111 PNG metadata)· `midjourney`(IPTC/XMP)· `elevenlabs`(history API)· `suno`(本地 MP3 ID3)· `runway` / `heygen`(stub)

### 简历智能处理
- **任务类别分类器** —— 把每次会话标注为 frontend / backend / bug-fix / deployment / refactor / testing 等
- **能力广度** —— 统计每个项目的相异类别数,凸显跨技能工程师
- **30 天滚动统计** —— 活跃天数比、日均、峰值日、最长连续天(对齐 Claude Code 30 天清理周期)
- **XYZ enricher** —— 通过 Claude Code CLI 无头模式把噪声活动转为 Google 风格简历条目
- **技术栈规范化** —— `postgres` → `PostgreSQL`、`tailwind` → `Tailwind CSS`
- **硬技能 vs 领域标签分离** —— 让 ATS 关键字保持干净
- **隐私过滤** —— regex 遮蔽 + 项目黑名单 + 可选技术抽象化
- **版本化输出** —— `data/resume_history/` 下的内部 git repo,含 `list-versions` / `diff v1 v2` / `rollback`

## 作为 Agent Skill 使用(Claude Code · Gemini CLI · Copilot CLI · Cursor · Warp · OpenClaw · OpenCode · Hermes)

本 repo 同时也是 **Agent Skill**。当用户的提问命中 `description` frontmatter 时,host 会自动加载整份 SKILL.md 并按指示执行完整 pipeline。

| Host | 发现路径 | 本 repo 的配置 |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | Canonical —— 自动加载 |
| **Gemini CLI**(Google) | `.gemini/skills/<name>/SKILL.md` | 以 symlink 指向 canonical |
| **GitHub Copilot CLI** | 原生读取 `.claude/skills/`(2026-04 changelog) | 零配置 |
| **Cursor CLI** | `AGENTS.md` + `.cursor/rules/` | `AGENTS.md` 指向 SKILL.md |
| **Warp**(agentic terminal) | 读 `.claude/skills/` + `.agents/skills/` + `.warp/skills/` | 零配置;已补 `.agents/skills/` symlink |
| **OpenClaw**(250k⭐) | `~/.openclaw/skills/`(仅 user scope) | 需要 user-scope symlink |
| **OpenCode**(终端 CLI agent) | `.opencode/skills/` + `~/.opencode/skills/` | 已含 project-scope symlink |
| **Hermes Agent**(Nous Research) | repo `skills/<name>/SKILL.md` → 安装到 `~/.hermes/skills/<category>/<name>/` | 原生 skill 在 [`skills/ai-used-resume/SKILL.md`](skills/ai-used-resume/SKILL.md);走 `hermes skills tap add` + `hermes skills install` |

### 安装 —— 三条生态血统

2026 年 agent-skills 生态已收敛成**三条安装路径** —— 按你的 agent 选一条,不用再写八条 `ln -s`。

**Tier 1 —— 27+ 家 `agentskills.io` 标准 host(一行装到所有)**
```bash
npx skills add easyvibecoding/vibe-resume --skill ai-used-resume
```
`npx skills` 会自动检测机器上装了哪些 CLI / IDE agent,并路由到对应目录。这一行就覆盖 Claude Code、Cursor、Windsurf、Gemini CLI、GitHub Copilot、Codex、Qwen Code、Kimi Code、Roo Code、Kilo Code、Goose、Trae、OpenCode、Amp、Antigravity 等。要限定特定 agent,加 `-a <slug>`:
```bash
npx skills add easyvibecoding/vibe-resume -a claude -a cursor-agent -a windsurf
```

<details>
<summary>Tier-1 完整 agent slug 对照表(<code>-a</code> 参数用)</summary>

| Agent | slug |  | Agent | slug |
|---|---|---|---|---|
| Amp | `amp` |  | Kilo Code | `kilocode` |
| Antigravity | `agy` |  | Kimi Code | `kimi` |
| Auggie CLI | `auggie` |  | Kiro CLI | `kiro-cli` |
| Claude Code | `claude` |  | Mistral Vibe | `vibe` |
| CodeBuddy CLI | `codebuddy` |  | opencode | `opencode` |
| Codex CLI | `codex` |  | Pi Coding Agent | `pi` |
| Cursor | `cursor-agent` |  | Qoder CLI | `qodercli` |
| Forge | `forge` |  | Qwen Code | `qwen` |
| Gemini CLI | `gemini` |  | Roo Code | `roo` |
| GitHub Copilot | `copilot` |  | SHAI (OVHcloud) | `shai` |
| Goose | `goose` |  | Tabnine CLI | `tabnine` |
| IBM Bob | `bob` |  | Trae | `trae` |
| iFlow CLI | `iflow` |  | Windsurf | `windsurf` |
| Junie | `junie` |  |  |  |

最新列表见 [vercel-labs/skills](https://github.com/vercel-labs/skills)。
</details>

**Tier 2 —— OpenClaw(自有 ClawHub marketplace + 5,400+ skill registry)**
```bash
openclaw skills install easyvibecoding/vibe-resume/ai-used-resume
```

**Tier 3 —— Hermes Agent(自有 `skills.sh` registry + 原生 5-section body 格式)**
```bash
hermes skills tap add easyvibecoding/vibe-resume
hermes skills install easyvibecoding/vibe-resume/ai-used-resume --force --yes
```

<details>
<summary>手动安装 / symlink 备援(没装 Node、路径定制、Windows)</summary>

如果不能跑 `npx skills`,或需要完全控制 symlink 位置:

```bash
# Tier 1 host —— 从 repo canonical SKILL.md symlink 出去
mkdir -p ~/.claude/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.claude/skills/ai-used-resume
mkdir -p ~/.gemini/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.gemini/skills/ai-used-resume
mkdir -p ~/.warp/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.warp/skills/ai-used-resume
mkdir -p ~/.opencode/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.opencode/skills/ai-used-resume

# Cursor 读 project root 的 AGENTS.md 零配置。要跨项目用就复制到 ~/.cursor/rules/。
```

Windows(管理员 PowerShell):
```powershell
New-Item -ItemType SymbolicLink -Path $HOME\.claude\skills\ai-used-resume `
  -Value (Resolve-Path .claude\skills\ai-used-resume)
# .gemini / .warp / .opencode 同样处理
```
</details>

### 安装后怎么触发

**所有 2026 host 都**支持 `description` 比对的自动触发 —— 自然语言就够了,例如:**"帮我从 AI 使用记录生成简历"**、**"渲染成日文简历"**、**"针对这份 JD 定制简历"**、**"给我的简历打分"**、**"显示简历分数趋势"**。多数 host 同时提供显式调用:

| Host | 自动触发 | 显式调用 |
|---|---|---|
| **Claude Code** | ✅ 靠 `description` 比对 | `/ai-used-resume` slash command |
| **Gemini CLI** | ✅ `activate_skill` 工具加载 | 安装后在 REPL 跑一次 `/agents refresh` 建索引 |
| **GitHub Copilot CLI** | ✅ description 比对 | `gh skill install easyvibecoding/vibe-resume` |
| **Cursor CLI** | ✅ project root 的 `AGENTS.md` 自动生效 | 内容也可复制到 `.cursor/rules/` |
| **Warp** | ✅ agent 会从可用 skill 列表选 | `/ai-used-resume` 或搜索 skill 菜单 |
| **OpenClaw** | ✅ 加载时比对 description | `/ai-used-resume` 或 `openclaw skills install` |
| **OpenCode** | ✅ 内建 `SkillTool` | `/ai-used-resume` slash command |
| **Hermes Agent** | ✅ description 比对 | `hermes chat -s ai-used-resume -q "帮我生成简历"` 预加载形式 |

快速验证安装是否成功,给任一 host 发这句:**"不用真跑,只要按顺序描述从 AI 使用记录生成简历需要哪 6 条命令"**。如果回应能说出 `extract → aggregate → enrich → render → review → trend` 并用 `uv run vibe-resume` 语法,说明 skill 已正确加载(已在 Hermes 上通过 `hermes chat -Q -s ai-used-resume` 实测验证)。

## 快速上手

```bash
# 1. 安装
uv venv && uv pip install -e ".[dev]"

# 2. 填入个人档
cp profile.example.yaml profile.yaml
$EDITOR profile.yaml        # 至少填 name / target_role
# config.yaml 不存在时会首跑自动从 config.example.yaml bootstrap

# 3. (可选)把云端 ZIP 导出丢到 data/imports/<tool>/

# 4. 跑 pipeline
uv run vibe-resume extract          # 4× 并行 extract + 进度条
uv run vibe-resume aggregate        # 按项目分组 + 推断技术栈
uv run vibe-resume enrich           # 通过 claude -p 生成 XYZ bullet
uv run vibe-resume render -f all    # md + docx + pdf + git 快照
```

## 命令

| 命令 | 功能 |
|---|---|
| `cli.py extract [--only NAME]` | 执行 extractor,缓存到 `data/cache/*.json` |
| `cli.py aggregate` | 按项目分组、分类任务、推断技术栈 |
| `cli.py enrich [-n N] [--locale L] [--tailor JD.txt]` | 生成 summary + achievements(英文用 XYZ,中日德法韩用名词短语);`--tailor` 让 bullet 偏向 JD 关键字 |
| `cli.py render -f md\|docx\|pdf\|all [--locale L]` | 渲染 + git 快照 |
| `cli.py render --all-locales [-f FMT]` | 一次渲染全部已注册 locale |
| `cli.py render --tailor data/imports/jd.txt` | 针对特定 JD 定制 |
| `cli.py review [-v N \| --file PATH] [--locale L] [--jd JD.txt]` | 按 8 项 reviewer 清单打分 |
| `cli.py trend [--locale L]` | 按 locale 显示历次评分 + 平均 + 最新等级 |
| `cli.py completion {bash\|zsh\|fish} [--install]` | 生成或安装 shell 补全脚本 |
| `cli.py status` | 显示各来源的活动数 |
| `cli.py list-versions` / `cli.py diff 1 2` | 简历版本历史 |

## 多语 locale 渲染

`vibe-resume` 内置各 locale 专属模板,同一份 `profile.yaml` 和项目数据可以渲染成不同地区审核者习惯的版式。

**示范输出请见 [`docs/samples/`](docs/samples/README.md)**:`en_EU`(Europass)、`ja_JP`(職務経歴書)、`zh_TW`(繁中)三份对照范例。

```bash
uv run python cli.py render -f md  --locale en_US     # ATS 优化美式默认
uv run python cli.py render -f md  --locale zh_CN     # 简体中文简历
uv run python cli.py render -f all --locale ja_JP     # 履歴書 (DOCX 格子) + 職務経歴書 (md/pdf)
uv run python cli.py render -f md  --locale de_DE     # Lebenslauf 含 Persönliche Daten 区块
```

| Locale | 风格 | 照片 | 标题示例 | 要点 |
|---|---|---|---|---|
| `en_US`(默认) | XYZ 动词开头 | 禁用 | Summary / Skills / Experience / … | 扁平 ATS 友好技能行 |
| `en_EU` | XYZ 动词开头 | 可选 | Personal information / Work experience / Education and training / … | Europass 版式 —— 带标签个人资料,CEFR 语言,GDPR 极简(默认不露 DOB) |
| `en_GB` | XYZ 动词开头 | 禁用 | Personal statement / … | 英式拼写、CEFR |
| `zh_TW` | 名词短语 | 可选 | 自我介紹 / 技能專長 / 工作經歷 / … | 繁体、全角分隔、中英技术混排 |
| `zh_HK` | 名词短语 | 可选 | Personal Profile 個人簡介 / Work Experience 工作經驗 / … | **双语标题 EN + 繁**;CEFR;不放 HKID |
| `zh_CN` | 名词短语 | 可选 | 个人简介 / 专业技能 / … | 简体、大厂偏美式 |
| `ja_JP` | 名词短语 | **必需** | 職務要約 / 職務経歴 / … | DOCX = JIS Z 8303 履歴書格子(`render/japan.py`);md = 職務経歴書 |
| `ko_KR` | 名词短语 | **必需** | 자기소개 / 보유 기술 / 경력 / … | 자기소개서 留作独立文档 |
| `de_DE` | 名词短语 | **必需** | Persönliche Daten / Berufserfahrung / … | 填了 `dob` / `nationality` 才会输出 |
| `fr_FR` | 名词短语 | 可选 | Profil / Compétences / Expérience / … | 初级 1 页、资深 2 页 |

### 各 locale 文本覆写

`UserProfile` 是 `extra="allow"`,所以任何 `<field>_<locale>` key 都能和英文原字段并存,模板会用 `localized` Jinja filter 选正确版本:

```yaml
title: "Senior Full-stack Engineer"
title_zh_CN: "高级全栈工程师"
title_ja_JP: "シニアフルスタックエンジニア"

summary: "Full-stack engineer who…"
summary_zh_CN: "全栈工程师,熟悉 React / Next.js…"

experience:
  - title: "Senior Full-stack Engineer"
    title_zh_CN: "高级全栈工程师"
    company: "Lumen Labs"
    company_zh_CN: "Lumen Labs(种子轮 AI SaaS)"
    bullets:
      - "Reduced query latency from 1.8s to 620ms..."
    bullets_zh_CN:
      - "查询中位延迟从 1.8 秒降至 620 毫秒…"
```

可选的 locale 条件个人字段(`dob` / `gender` / `nationality` / `mil_service` / `photo_path` / `marital_status`)在 `profile.example.yaml` 有完整说明。只有当 (a) 当前 locale 的 `personal_fields` 包含该字段,且 (b) 值不为空,才会输出。

完整设计理由和各 locale 字段矩阵在 `docs/resume_locales.md`。

### Locale 解析链

渲染器按以下四个来源判断 locale,遇到第一个有值的即停:

1. CLI 的 `--locale`(最高)
2. `profile.yaml` 的 `profile.preferred_locale`
3. `config.yaml` 的 `config.render.locale`
4. `en_US` fallback

```yaml
# profile.yaml —— 若 CLI 没覆写就一律渲染 ja_JP
preferred_locale: ja_JP

# config.yaml —— 团队默认
render:
  locale: en_US
  all_locales_formats: ["md", "docx"]   # --all-locales 各 locale 的格式
```

`cli.py render --locale zh_CN` 永远胜过 `preferred_locale`;省略 `--locale` 则由 `preferred_locale` 接管。`enrich` 调 LLM 时也走同一条链,确保语言标签注入正确。

### 一次渲染全部 locale

需要为各市场打包完整版时:

```bash
uv run python cli.py render --all-locales                 # 使用 config.render.all_locales_formats
uv run python cli.py render --all-locales -f docx         # 强制特定格式
uv run python cli.py render --all-locales --tailor jd.txt # 一份 JD 用到所有 locale
```

`--all-locales` 会遍历 `LOCALES` 注册表(目前 10 个)。每 locale 输出格式由 `config.render.all_locales_formats` 控制(默认 `["md"]`),改成 `["md", "docx", "pdf"]` 可一次打齐全包。`--locale` 与 `--all-locales` 互斥。

## Reviewer-view 审核(`cli.py review`)

![8 项自动 reviewer 评分表,旁边是一份已渲染简历和趋势稀疏图](docs/assets/reviewer_audit.png)

渲染后,按真 reviewer 用的 8 项清单打分:

```bash
uv run python cli.py review                    # 最新版
uv run python cli.py review -v 9               # 指定版本
uv run python cli.py review -v 12 --jd jd.txt  # 加入 JD 关键字覆盖率
```

每份草稿按以下 8 项评:

1. **Top fold** —— 姓名、目标岗位、至少一个具体指标是否出现在前 12 行
2. **Numbers per bullet** —— 工作经历的 bullet 是否 ≥60% 带量化指标
3. **Keyword echo (JD)** —— JD 的主要大写词是否在简历中重现(无 `--jd` 时跳过)
4. **Action-verb first** —— XYZ locale 下,bullet 是否以过去式动词开头
5. **Density (noun-phrase)** —— 名词短语 locale 下,bullet 是否自给自足、无悬空代词
6. **Red flags** —— 按 locale 检查照片 / DOB / "References available upon request" / 连续标题等
7. **Contact line width** —— contact 首行是否会换行破版(中日韩字双宽)
8. **Page count** —— 按行数估算页数 vs locale 建议(US/UK ≤2、DE/JP/KR ≤3)

输出 `data/reviews/<draft>_review.md` 和 `.json` 可跨版 diff。交给真 reviewer 前建议至少 B/(80%)。

### 评分趋势(`cli.py trend`)

每次 review 都在 `data/reviews/` 留 JSON,`trend` 按 locale 汇总显示进步 / 退步:

```bash
uv run python cli.py trend               # 所有 locale
uv run python cli.py trend --locale zh_CN
```

```
 Locale  Runs  First    Latest        Mean    Grade  Trend
 en_US   6     58/80    v16: 78/80    91.0%   A      ▂▅▆▇██
 ja_JP   3     50/80    v14: 72/80    82.5%   A      ▁▅█
 zh_CN   4     42/80    v15: 74/80    85.0%   A      ▁▃▆█
```

稀疏图用 U+2581..U+2588 Unicode block,任何 monospace 终端都能渲染。列:跑了几次、首次分数、最新分数(含版号)、跨版平均百分比、最新等级、逐次趋势。

## Claude Code 30 天清理 —— 重要

Claude Code 默认会删除超过 30 天的 session JSONL 文件。要长期保留:

```bash
# 1. 延长保留天数
python3 -c "import json,pathlib; p=pathlib.Path.home()/'.claude/settings.json'; \
  d=json.loads(p.read_text()); d['cleanupPeriodDays']=365; \
  p.write_text(json.dumps(d,indent=2,ensure_ascii=False))"

# 2. 定期 rsync 备份(附赠脚本)
chmod +x scripts/backup_claude_projects.sh
./scripts/backup_claude_projects.sh
# 再注册为 launchd / cron 每周备份
```

### Windows 备份(Task Scheduler)

`scripts/backup_claude_projects.ps1` 是 PowerShell 7 版本,用 `robocopy /MIR /XO` 将 `%USERPROFILE%\.claude\projects` 镜像到 `%USERPROFILE%\ClaudeCodeArchive\current`,并留一份日期快照:

```powershell
# 一次执行
pwsh -NoProfile -File scripts\backup_claude_projects.ps1

# Dry-run(macOS/Linux 也能跑,适合冒烟测试)
pwsh -NoProfile -File scripts\backup_claude_projects.ps1 -WhatIf

# 注册为每周任务(周日 03:00)
schtasks /Create /TN "vibe-resume backup" /XML scripts\vibe-resume-backup.xml
```

`scripts/vibe-resume-backup.xml` 是可直接导入 Task Scheduler 的模板。导入前把 `<WorkingDirectory>` 改成 repo 的实际位置。CI 在 `windows-latest` 上用 `PSScriptAnalyzer` 严格检查这个脚本,`-WhatIf` 分支也实际跑过一次。

## 项目结构

```
vibe-resume/
├── profile.example.yaml   # 已提交的模板 —— 复制成 profile.yaml
├── config.example.yaml    # 已提交的模板 —— 首跑自动复制成 config.yaml
├── profile.yaml           # 你的 PII(gitignored)
├── config.yaml            # 你的 extractor 路径和隐私规则(gitignored)
├── cli.py                 # 入口(也以 `vibe-resume` 安装为 entry)
├── core/
│   ├── schema.py          # Pydantic v2: Activity、ProjectGroup、UserProfile
│   ├── classifier.py      # 18 类任务标签(双语 regex)
│   ├── tech_canonical.py  # 硬技能 vs 领域标签拆分
│   ├── stats.py           # 滚动时间窗统计(30d/7d)
│   ├── privacy.py         # 遮蔽 + 黑名单 + 技术抽象
│   ├── aggregator.py      # 分组 + headline + 重要度排序
│   ├── enricher.py        # claude -p → 各 locale 的 XYZ / 名词短语 bullet
│   ├── review.py          # 8 项评分 + 趋势 sparkline
│   ├── versioning.py      # 草稿 git 快照
│   └── runner.py          # ThreadPoolExecutor pipeline + rich.progress
├── extractors/
│   ├── local/             # 11 个本地 extractor
│   ├── cloud_export/      # 7 个 ZIP 导入器
│   └── api/               # 6 个 AIGC extractor
├── render/
│   ├── renderer.py        # md / docx / pdf
│   ├── japan.py           # JIS Z 8303 履歴書栅格(ja_JP DOCX 专用)
│   ├── i18n.py            # LOCALES 注册表 + 各 locale 标签字典
│   └── templates/resume.<locale>.md.j2
├── scripts/
│   ├── backup_claude_projects.sh       # macOS / Linux rsync
│   ├── backup_claude_projects.ps1      # Windows PowerShell 7 (robocopy)
│   ├── vibe-resume-backup.xml          # Task Scheduler 导入模板
│   └── com.vibe-resume.backup.plist    # macOS launchd agent
├── data/
│   ├── imports/           # 把下载的 ZIP 放这(gitignored,仅保留 sample_jd.txt)
│   ├── cache/             # 各来源 extractor JSON(gitignored)
│   ├── resume_history/    # 渲染输出 + 内部 git(gitignored)
│   └── reviews/           # 评分报告和历史(gitignored)
├── docs/samples/          # 各 locale 示范输出
├── .claude/skills/ai-used-resume/SKILL.md   # 第 1–7 个 host 的 canonical skill
└── skills/ai-used-resume/SKILL.md           # Hermes 原生 skill(第 8 个 host)
```

## 新增一个 extractor

```python
# extractors/local/mytool.py
from core.schema import Activity, ActivityType, Source
NAME = "mytool"
def extract(cfg: dict) -> list[Activity]:
    return []  # 生成 Activity 对象
```

再到 `core/runner.py` → `LOCAL_EXTRACTORS` 注册、`config.yaml` 启用即可。

## 已知限制

- 全 `$HOME` 扫描(`git_repos`、`aider`)首次要 1–3 分钟,即便 4× 并行 extractor 也一样 —— 改成 `scan.mode: whitelist` 可缩小范围。`_find_repos` 有 120 秒墙钟死线,FUSE 挂载 / 断掉的 symlink 不会卡死整个流程。
- Grok / Perplexity / Mistral 导出 schema 为**宽松解析**(官方未公开 schema);字段对不上时,把真 sample 放到 `data/imports/` 协助修正。
- Claude Desktop 聊天内容在 Local Storage 以加密形式存 —— 只能提取 MCP 配置 + extensions。
- PDF 渲染中日韩字符需要 `pandoc` + XeLaTeX;没装则回退到纯 pandoc。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。

## 相关项目

- [sujankapadia/claude-code-analytics](https://github.com/sujankapadia/claude-code-analytics) —— session 分析仪表盘
- [yudppp/claude-code-history-mcp](https://github.com/yudppp/claude-code-history-mcp) —— MCP history server
- [alicoding/claude-parser](https://github.com/alicoding/claude-parser) —— Git-like conversation API
- [daaain/claude-code-log](https://github.com/daaain/claude-code-log) —— HTML 时间线
- [S2thend/cursor-history](https://github.com/S2thend/cursor-history) —— Cursor 聊天导出
- [AndreaCadonna/resumake-mcp](https://github.com/AndreaCadonna/resumake-mcp) —— LaTeX 简历 MCP

`vibe-resume` 的差异在于**跨工具聚合**并生成「简历向」的条目,而不是原始 dump。
