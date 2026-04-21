<p align="center">
  <img src="docs/assets/logo.png" width="120" alt="vibe-resume logo">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.ja.md">日本語</a>
</p>

# vibe-resume

> Turn your AI coding history into a versioned, reviewer-ready résumé — **for the vibe coding era**.

[![CI](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml/badge.svg)](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Locales](https://img.shields.io/badge/locales-10-brightgreen.svg)](docs/resume_locales.md)
[![uv](https://img.shields.io/badge/packaged%20with-uv-261230.svg)](https://github.com/astral-sh/uv)

![vibe-resume hero — AI tool sessions flow through extract→aggregate→enrich→render into 10 locale résumés](docs/assets/hero.png)

`vibe-resume` scans every AI assistant you use on macOS (Claude Code, Cursor, GitHub Copilot, Cline, Continue, Aider, Windsurf, Zed AI, ChatGPT / Claude.ai / Gemini / Grok / Perplexity / Mistral exports, ComfyUI, Midjourney, Suno, ElevenLabs, and your `git` commits) and synthesizes the usage trail into a **Markdown / DOCX / PDF résumé** with built-in git snapshots so every draft is diff-able and rollback-able.

## How it differs

| | vibe-resume | Reactive Resume / OpenResume | Resume-LM / Resume Matcher | HackMyResume / JSON Resume |
|---|---|---|---|---|
| **Primary signal** | AI tool sessions + git commits (auto-extracted) | User-typed content in WYSIWYG | Uploaded PDF + JD | User-typed JSON |
| **Locales** | **10** (en_US/en_EU/en_GB/zh_TW/zh_HK/zh_CN/ja_JP/ko_KR/de_DE/fr_FR) with culture-specific layouts | 1–2 | 1 | Theme-dependent |
| **JP 履歴書 JIS Z 8303 grid** | ✅ `render/japan.py` | ❌ | ❌ | ❌ |
| **Europass labelled personal-info** | ✅ `en_EU` template | ❌ | ❌ | ❌ |
| **Reviewer audit** | 8-point scorecard + trend sparkline | — | ATS score only | — |
| **JD tailoring** | `enrich --tailor JD.txt` (LLM prompt injection) | — | ✅ LLM rewrite | — |
| **Privacy** | Fully local; `claude -p` headless; nothing leaves your machine | Varies (OpenAI-key optional) | Cloud API required | Fully local |
| **Shape** | Python CLI pipeline | Web UI | Web UI | Node CLI |
| **Agent-Skill hosts** | **8** (Claude Code · Gemini CLI · Copilot CLI · Cursor · Warp · OpenClaw · OpenCode · Hermes) — single canonical SKILL.md | — | — | — |

## Why

Hiring in 2026 rewards engineers who can **prove AI-assisted productivity with measurable outcomes** — not just list "Claude Code" as a skill. Reviewers want to see architecture decisions, cross-stack breadth (frontend / backend / DevOps / bug-fix / deployment), and how fast you ship. Your AI tools already log this automatically. `vibe-resume` turns that exhaust into evidence.

## Features

### Local extractors (no login required)
| Source | Where |
|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| Claude Code Archive | `~/ClaudeCodeArchive/current` (optional rsync backup) |
| Cursor | `~/Library/Application Support/Cursor/User/**/state.vscdb` |
| GitHub Copilot (VS Code) | `workspaceStorage/**/chatSessions/` |
| Cline | `globalStorage/saoudrizwan.claude-dev/` or `~/.cline/data/` |
| Continue.dev | `~/.continue/sessions/` |
| Aider | `$HOME/**/.aider.chat.history.md` |
| Windsurf / Cascade | `~/.codeium/windsurf/cascade/` |
| Zed AI | `~/.local/share/zed/threads/` |
| Claude Desktop | MCP config + extensions |
| Git commits | every `.git` in `$HOME` filtered by your author email |

### Cloud export importers (drop a ZIP into `data/imports/<tool>/`)
ChatGPT · Claude.ai · Gemini Takeout · Grok · Perplexity · Mistral Le Chat · Poe

### AIGC extractors
`image_local` (ComfyUI / A1111 PNG metadata) · `midjourney` (IPTC/XMP) · `elevenlabs` (history API) · `suno` (local MP3 ID3) · `runway` / `heygen` (stub)

### Resume intelligence
- **Task-type classifier** — tags each session as frontend / backend / bug-fix / deployment / refactor / testing / etc.
- **Capability breadth** — counts distinct task categories per project; surfaces multi-skill engineers
- **30-day rolling stats** — active-day ratio, daily avg, peak day, longest streak (aligned with Claude Code's 30-day cleanup)
- **XYZ enricher** — uses Claude Code CLI headlessly to turn raw activity into Google-style résumé bullets
- **Tech stack canonicalization** — `postgres` → `PostgreSQL`, `tailwind` → `Tailwind CSS`
- **Domain-tag vs hard-skill separation** — keeps ATS keywords clean
- **Privacy filter** — regex redaction + project blocklist + optional tech abstraction
- **Versioned output** — internal git repo under `data/resume_history/` with `list-versions` / `diff v1 v2` / `rollback`

## Use as an Agent Skill (Claude Code · Gemini CLI · Copilot CLI · Cursor · Warp · OpenClaw · OpenCode)

Beyond the CLI, `vibe-resume` ships as an [Agent Skill](AGENTS.md) that drives the full `extract → aggregate → enrich → render → review → trend` pipeline from natural-language prompts. Inside any supported host you can just say:

> *"Generate my résumé from my AI usage."*
> *"Render my résumé in Japanese and German and review both."*
> *"Tailor my résumé for this JD: data/imports/lumen_labs.txt."*

The skill follows the 2026 converged `SKILL.md` convention: **one canonical file** at [`skills/ai-used-resume/SKILL.md`](skills/ai-used-resume/SKILL.md); every other host path (`.claude/skills/`, `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/`) is a symlink pointing at it. For marketplace installs, [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) and [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) wrap the skill as a Claude Code / OpenAI Codex plugin.

| Host | Discovery | Setup in this repo |
|---|---|---|
| **Claude Code** | `.claude/skills/` | Canonical — auto-loaded |
| **Gemini CLI** (Google) | `.gemini/skills/` | Symlink → canonical |
| **GitHub Copilot CLI** | reads `.claude/skills/` natively | Zero config |
| **Cursor CLI** | reads `AGENTS.md` + `.cursor/rules/` | `AGENTS.md` points at SKILL.md |
| **Warp** (agentic terminal) | reads `.claude/skills/` + `.agents/skills/` + `.warp/skills/` | Zero config (`.agents/skills/` symlink added defensively) |
| **OpenClaw** (250k⭐ in 60 days) | `~/.openclaw/skills/` (user scope only) | User-scope symlink — see below |
| **OpenCode** (terminal CLI agent) | `.opencode/skills/` + `~/.opencode/skills/` | Project-scope symlink included |
| **Hermes Agent** (Nous Research) | repo `skills/<name>/SKILL.md` → installed to `~/.hermes/skills/<category>/<name>/` | Native skill at [`skills/ai-used-resume/SKILL.md`](skills/ai-used-resume/SKILL.md); `hermes skills tap add easyvibecoding/vibe-resume && hermes skills install easyvibecoding/vibe-resume/ai-used-resume` |

### Install — three ecosystem tiers

The 2026 agent-skills ecosystem has converged into **three install paths** —
pick the one that matches your agent, not eight separate `ln -s` commands.

**Tier 1 — 27+ `agentskills.io`-standard hosts (one line installs to all)**
```bash
npx skills add easyvibecoding/vibe-resume --skill ai-used-resume
```
`npx skills` auto-detects every installed CLI/IDE agent on your machine and
routes the skill to the correct directory. This one command covers Claude
Code, Cursor, Windsurf, Gemini CLI, GitHub Copilot, Codex, Qwen Code, Kimi
Code, Roo Code, Kilo Code, Goose, Trae, OpenCode, Amp, Antigravity, and
more. To restrict, pass `-a <slug>`:
```bash
npx skills add easyvibecoding/vibe-resume -a claude -a cursor-agent -a windsurf
```

<details>
<summary>Full list of Tier-1 agent slugs (for <code>-a</code> flag)</summary>

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

Latest list: [vercel-labs/skills](https://github.com/vercel-labs/skills).
</details>

**Tier 2 — OpenClaw (own ClawHub marketplace + 5,400+ skill registry)**
```bash
openclaw skills install easyvibecoding/vibe-resume/ai-used-resume
```

**Tier 3 — Hermes Agent (own `skills.sh` registry + native 5-section body format)**
```bash
hermes skills tap add easyvibecoding/vibe-resume
hermes skills install easyvibecoding/vibe-resume/ai-used-resume --force --yes
```

<details>
<summary>Manual install / symlink fallback (no Node, custom paths, Windows)</summary>

If you can't run `npx skills` or want full control over symlink locations:

```bash
# Tier 1 hosts — symlink from this repo's canonical SKILL.md
mkdir -p ~/.claude/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.claude/skills/ai-used-resume
mkdir -p ~/.gemini/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.gemini/skills/ai-used-resume
mkdir -p ~/.warp/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.warp/skills/ai-used-resume
mkdir -p ~/.opencode/skills && ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.opencode/skills/ai-used-resume

# Cursor reads project-root AGENTS.md zero-config. For system-wide, copy to ~/.cursor/rules/.
```

Windows (elevated PowerShell):
```powershell
New-Item -ItemType SymbolicLink -Path $HOME\.claude\skills\ai-used-resume `
  -Value (Resolve-Path .claude\skills\ai-used-resume)
# repeat for .gemini / .warp / .opencode
```
</details>

### How to trigger the skill once installed

In **every 2026 host**, the skill auto-fires when your prompt matches the
description line of the SKILL.md frontmatter — so natural-language trigger
phrases like **"generate my résumé from my AI usage"**, **"render my résumé
in Japanese"**, **"tailor my résumé for this JD"**, **"score my résumé"**, or
**"show my résumé trend"** are enough in most tools. Most hosts also expose
an explicit invocation path:

| Host | Auto-trigger | Explicit invocation |
|---|---|---|
| **Claude Code** | ✅ via `description` match | `/ai-used-resume` slash command |
| **Gemini CLI** | ✅ `activate_skill` tool loads on match | after install, run `/agents refresh` once to index |
| **GitHub Copilot CLI** | ✅ description match | `gh skill install easyvibecoding/vibe-resume` (uses repo `skills/` layout) |
| **Cursor CLI** | ✅ `AGENTS.md` at project root auto-applies | content also copyable into `.cursor/rules/` |
| **Warp** | ✅ agent picks from available skills | `/ai-used-resume` slash command or searchable skills menu |
| **OpenClaw** | ✅ matches description at load | `/ai-used-resume` or `openclaw skills install easyvibecoding/vibe-resume` |
| **OpenCode** | ✅ via internal `SkillTool` | `/ai-used-resume` slash command |
| **Hermes Agent** | ✅ matches description | `hermes chat -s ai-used-resume -q "generate my résumé"` preload form |

A quick verification prompt for any host: **"Walk me through generating my
résumé from AI usage — don't run anything, just describe the 6 commands in
order."** If the skill is correctly loaded, the response names `extract →
aggregate → enrich → render → review → trend` and matches `uv run vibe-resume`
syntax. End-to-end verified in Hermes with `hermes chat -Q -s ai-used-resume`.

See [`AGENTS.md`](AGENTS.md) for the full matrix, Windows symlink commands, and Hermes Agent install notes.

## Quick start

```bash
# 1. install
uv venv && uv pip install -e ".[dev]"

# 2. fill your profile
cp profile.example.yaml profile.yaml
$EDITOR profile.yaml        # at least name / target_role
# config.yaml auto-bootstraps from config.example.yaml on first run

# 3. (optional) drop cloud ZIP exports into data/imports/<tool>/

# 4. run pipeline
uv run vibe-resume extract          # parallel extract with progress bar
uv run vibe-resume aggregate        # group by project + infer stack
uv run vibe-resume enrich           # XYZ bullets via claude -p
uv run vibe-resume render -f all    # md + docx + pdf + git snapshot
```

## Commands

| Command | What it does |
|---|---|
| `cli.py extract [--only NAME]` | run extractors, cache to `data/cache/*.json` |
| `cli.py aggregate` | group by project, classify task types, infer stack |
| `cli.py enrich [-n N] [--locale L] [--tailor JD.txt] [--persona KEY]` | generate summary + achievements (XYZ for en, noun-phrase for zh/ja/de/fr/ko); `--tailor` biases toward a JD's keywords; `--persona` biases toward a reviewer archetype (see § *Reviewer personas*) |
| `cli.py render -f md\|docx\|pdf\|all [--locale L]` | render + git snapshot |
| `cli.py render --all-locales [-f FMT]` | fan out across every registered locale in one pass |
| `cli.py render --tailor data/imports/jd.txt` | tailor for a specific job description |
| `cli.py review [-v N \| --file PATH] [--locale L] [--jd JD.txt] [--persona KEY]` | score against the 8-point checklist; `--persona` appends a persona-specific lens at the end of the report |
| `cli.py trend [--locale L]` | score history per locale with ASCII sparkline + mean + latest grade |
| `cli.py completion {bash\|zsh\|fish} [--install]` | print or install a shell completion script so `--locale <tab>` expands |
| `cli.py status` | show per-source activity counts |
| `cli.py list-versions` / `cli.py diff 1 2` | resume version history |

## Multi-locale rendering

`vibe-resume` ships per-locale templates so the same `profile.yaml` + project
data renders into reviewer-appropriate output in each market.

**See [`docs/samples/`](docs/samples/README.md)** for illustrative outputs in
`en_EU` (Europass), `ja_JP` (職務経歴書), and `zh_TW` (繁中).

```bash
uv run python cli.py render -f md  --locale en_US     # ATS-optimized US default
uv run python cli.py render -f md  --locale zh_TW     # 台灣繁中履歷
uv run python cli.py render -f all --locale ja_JP     # 履歴書 (DOCX grid) + 職務経歴書 (md/pdf)
uv run python cli.py render -f md  --locale de_DE     # Lebenslauf with Persönliche Daten block
```

| Locale | Style | Photo | Headings | Special |
|---|---|---|---|---|
| `en_US` (default) | XYZ action-verb | forbidden | Summary / Skills / Experience / … | Flat ATS-friendly skills line |
| `en_EU` | XYZ action-verb | optional | Personal information / Work experience / Education and training / … | Europass-styled — labelled personal-info list, CEFR languages, GDPR-minimal (no DOB by default) |
| `en_GB` | XYZ action-verb | forbidden | Personal statement / … | UK spellings, CEFR languages |
| `zh_TW` | noun-phrase | optional | 自我介紹 / 技能專長 / 工作經歷 / … | 全形分隔, 中英技術混排 |
| `zh_HK` | noun-phrase | optional | Personal Profile 個人簡介 / Work Experience 工作經驗 / … | **Bilingual EN + 繁** headings; CEFR; no HKID |
| `zh_CN` | noun-phrase | optional | 个人简介 / 专业技能 / … | 简体, 大厂偏美式 |
| `ja_JP` | noun-phrase | **expected** | 職務要約 / 職務経歴 / … | DOCX = JIS Z 8303 履歴書 grid (`render/japan.py`); md = 職務経歴書 |
| `ko_KR` | noun-phrase | **expected** | 자기소개 / 보유 기술 / 경력 / … | 자기소개서 left as separate doc |
| `de_DE` | noun-phrase | **expected** | Persönliche Daten / Berufserfahrung / … | Renders `dob` / `nationality` when set |
| `fr_FR` | noun-phrase | optional | Profil / Compétences / Expérience / … | 1 page jr / 2 pages senior |

### Per-locale text overrides

`UserProfile` is `extra="allow"`, so any `<field>_<locale>` key sits next to its
canonical English original and templates pick the right one via the
`localized` Jinja filter:

```yaml
title: "Senior Full-stack Engineer"
title_zh_TW: "資深全端工程師"
title_ja_JP: "シニアフルスタックエンジニア"

summary: "Full-stack engineer who…"
summary_zh_TW: "全端工程師，熟悉 React / Next.js…"

experience:
  - title: "Senior Full-stack Engineer"
    title_zh_TW: "資深全端工程師"
    company: "Lumen Labs"
    company_zh_TW: "Lumen Labs（種子輪 AI SaaS）"
    bullets:
      - "Reduced query latency from 1.8s to 620ms..."
    bullets_zh_TW:
      - "查詢中位延遲從 1.8 秒降至 620 毫秒…"
```

Optional locale-conditional personal fields (`dob`, `gender`, `nationality`,
`mil_service`, `photo_path`, `marital_status`) are documented in
`profile.example.yaml`. They render only when (a) the active locale's
`personal_fields` list includes them and (b) the value is non-empty.

The full design rationale and per-locale field matrix is in
`docs/resume_locales.md`.

### Locale resolution chain

The renderer picks a locale by checking four sources in order and stops at the
first one that is set:

1. `--locale` on the CLI (highest priority)
2. `profile.preferred_locale` in `profile.yaml`
3. `config.render.locale` in `config.yaml`
4. `en_US` fallback

```yaml
# profile.yaml — always render ja_JP unless CLI overrides
preferred_locale: ja_JP

# config.yaml — team default
render:
  locale: en_US
  all_locales_formats: ["md", "docx"]   # what --all-locales produces per locale
```

Running `cli.py render --locale zh_TW` always wins over `preferred_locale`;
omit it and `profile.preferred_locale` takes over. The same chain applies
when `enrich` dispatches the LLM prompt, so the right language label is
injected regardless of which knob you turn.

### Batch rendering every locale

For final-cut day when you need the full pack for different markets:

```bash
uv run python cli.py render --all-locales                 # defaults to config.render.all_locales_formats
uv run python cli.py render --all-locales -f docx         # force a specific format
uv run python cli.py render --all-locales --tailor jd.txt # one JD, every locale
```

`--all-locales` iterates the full `LOCALES` registry (currently 10 locales).
Per-locale formats are controlled by `config.render.all_locales_formats`
(default `["md"]`) — bump it to `["md", "docx", "pdf"]` to cut full bundles.
`--locale` and `--all-locales` are mutually exclusive.

## Reviewer personas (`--persona`)

A résumé that wins a Tech Lead screen often loses an HR-first funnel, and
vice versa. `--persona` adds a third axis (orthogonal to locale and JD)
that biases how each bullet is phrased — same candidate, same activity
data, but re-voiced for the expected reader.

| Key | Reader | What this reader skims for |
|---|---|---|
| `tech_lead` | Staff+ engineer / Tech Lead | Named systems, specific perf numbers, trade-off verbs (*migrated / replaced / introduced*) |
| `hr` | HR manager / recruiter | Career trajectory, collaboration, plain-language business impact; acronym soup gets skipped |
| `executive` | VP / hiring manager | Business outcomes in $ / scale / team-size; each role's lead bullet should read as a headline |
| `startup_founder` | Early-stage founder | End-to-end ownership, shipping velocity, resourcefulness; enterprise-process framing gets discounted |
| `academic` | Research hiring committee | Methodological rigour, datasets, benchmarks, citation-style framing |

Compose with locale and JD freely — each dimension hits a different part
of the prompt:

```bash
# Same person, three audiences, Japanese market
uv run vibe-resume enrich --persona tech_lead   --locale ja_JP -n 3
uv run vibe-resume render  -f all              --locale ja_JP
uv run vibe-resume review  --persona tech_lead --locale ja_JP

uv run vibe-resume enrich --persona hr          --locale ja_JP -n 3
uv run vibe-resume render  -f all              --locale ja_JP     # overwrites the draft
uv run vibe-resume review  --persona hr        --locale ja_JP

# Executive lens + JD-tailored + English
uv run vibe-resume enrich --persona executive --tailor data/imports/jd.txt --locale en_US -n 3
uv run vibe-resume render  -f md --locale en_US --tailor data/imports/jd.txt
uv run vibe-resume review  --persona executive --jd data/imports/jd.txt
```

Reviewer personas never fabricate — the bias is a *re-voicing*
instruction; numbers, people, and decisions that the raw activity
doesn't support stay out. The `review --persona` form appends a
short lens-specific advisory block at the bottom of the scorecard.

### Multi-persona prep in one run

Pass comma-separated keys (or `all`) to produce parallel variants for
different audiences without re-extracting:

```bash
# Write three persona-specific enrich caches in one command
uv run vibe-resume enrich --persona tech_lead,hr,executive --locale en_US

# Render each persona's variant — filename includes the persona suffix
uv run vibe-resume render --persona tech_lead --locale en_US      # → resume_vNNN_tech_lead.md
uv run vibe-resume render --persona all      --locale en_US      # fan out across every persona

# Side-by-side diff of bullets across personas (quality iteration)
uv run vibe-resume personas-compare -n 3
```

Each persona writes to `data/cache/_project_groups.<persona>.json` so
variants don't clobber each other. The default `_project_groups.json`
is preserved for persona-less runs. Render filenames include a
`_<persona>` suffix when set.

`personas-compare` is the quality-iteration tool: it aligns the top-N
groups across every persona cache it finds and prints each group's
role label + bullets side by side. If two personas produce the same
output, the bias isn't biting — revise `core/personas.py` or the raw
activity until they differentiate.

## Strategic résumé — target-employer profiles (`--company`, `--level`)

70 bundled company profiles and 6 career-level archetypes let you
tailor enrich + review output against a specific hiring bar — orthogonal
to locale, persona, and JD tailor. Each profile is a YAML at
`core/profiles/<key>.yaml` with fact-check metadata (`last_verified_at`)
so stale data surfaces loudly instead of silently biasing résumés.

**Inspect the bundled catalogue:**

```bash
# Grouped by tier — frontier_ai / ai_unicorn / regional_ai / tw_local /
# us_tier2 / eu / jp / kr
uv run vibe-resume company list
uv run vibe-resume company list --tier jp

# Full profile in human-readable form (must-haves, red flags,
# keyword anchors, enrich_bias, review_tips, verified date)
uv run vibe-resume company show openai

# Age table across all 70 — flags profiles past the 90-day threshold
# (quarterly-refresh cadence matched to current AI-hiring market churn)
uv run vibe-resume company audit
uv run vibe-resume company audit --only-stale --stale-days 90
```

**Apply a company and level when enriching + reviewing:**

```bash
# Tailor bullets for an OpenAI senior-IC résumé
uv run vibe-resume enrich  --company openai --level senior --locale en_US -n 3
uv run vibe-resume render  -f all --locale en_US
uv run vibe-resume review  --company openai --level senior --locale en_US

# Same activity, different employer — each adds an employer-specific
# keyword-coverage score (0/10) to the review card on top of the 8-point
# base rubric
uv run vibe-resume review  --company anthropic --level senior --locale en_US
uv run vibe-resume review  --company rakuten  --level senior --locale ja_JP
```

**Every `--company` apply auto-checks verification age.** If the profile
is older than 90 days, the CLI prints a loud warning and suggests the
refresh path — it never silently biases a résumé against stale research.

**Refresh a stale profile:**

```bash
# Delegate a fact-check to the claude CLI agent (max ~5 web queries).
# The report lands in data/verification_reports/<key>_<YYYY-MM-DD>.md.
uv run vibe-resume company verify openai

# If the agent returns VERDICT: clean, auto-bump the verified date:
uv run vibe-resume company verify openai --apply

# After a manual web-browser fact-check, bump the date yourself:
uv run vibe-resume company mark-verified openai
uv run vibe-resume company mark-verified openai --date 2027-01-15 --yes
```

`mark-verified` rewrites only the one YAML line, preserving comments,
folded-string formatting, and any hand-edited fields. Adding a brand-new
profile is drop-in: write `core/profiles/<key>.yaml`, set
`last_verified_at: "YYYY-MM-DD"`, and it is immediately registered,
packaged into the wheel, and consumable by `--company`.

Career levels (`--level`): `new_grad` · `junior` · `mid` · `senior` ·
`staff_plus` · `research_scientist`. Each archetype bakes in the
lead-bullet signal the reviewer expects at that bracket, so mid-level
bullets don't get promoted into staff claims the candidate cannot defend.

## Reviewer-view audit (`cli.py review`)

![8-point automated reviewer scorecard alongside a rendered résumé and trend sparkline](docs/assets/reviewer_audit.png)

After rendering, score the output against the same 8-point checklist a real
reviewer applies:

```bash
uv run python cli.py review                    # latest version
uv run python cli.py review -v 9               # specific version
uv run python cli.py review -v 12 --jd jd.txt  # add JD-keyword echo scoring
```

Each draft is graded on:

1. **Top fold** — name + target role + at least one concrete metric in the first ~12 lines
2. **Numbers per bullet** — ≥60% of work-section bullets carry a metric
3. **Keyword echo (JD)** — JD's top capitalized terms present in the draft (skipped without `--jd`)
4. **Action-verb first** — past-tense verb at bullet start (XYZ locales)
5. **Density (noun-phrase)** — bullets self-sufficient, no dangling pronouns (noun-phrase locales)
6. **Red flags** — locale-aware photo / DOB / "References available upon request" / consecutive-heading checks
7. **Contact line width** — header line fits printed page width without ugly wrap (CJK chars count double)
8. **Page count** — line+wrap-based estimate vs locale target (US/UK ≤2, DE/JP/KR ≤3)

Outputs `data/reviews/<draft>_review.md` and `.json` for diffing across
iterations. A grade ≥ B/(80%) is the bar before sending the draft to a real
reviewer.

### Score trend (`cli.py trend`)

Every review run drops a JSON artefact into `data/reviews/`, and `trend`
folds them into one per-locale summary so you can see whether each market
version is improving or regressing as you iterate:

```bash
uv run python cli.py trend               # all locales
uv run python cli.py trend --locale zh_TW
```

```
 Locale  Runs  First    Latest        Mean    Grade  Trend
 en_US   6     58/80    v16: 78/80    91.0%   A      ▂▅▆▇██
 ja_JP   3     50/80    v14: 72/80    82.5%   A      ▁▅█
 zh_TW   4     42/80    v15: 74/80    85.0%   A      ▁▃▆█
```

The sparkline uses U+2581..U+2588 Unicode blocks so it renders in any
monospace terminal. Columns: run count, first score, latest score (with
version number), cross-run mean %, grade of the latest run, and the per-run
trend.

## Claude Code 30-day cleanup — important

Claude Code purges session JSONL transcripts older than 30 days by default. To keep history long-term:

```bash
# 1. extend retention
python3 -c "import json,pathlib; p=pathlib.Path.home()/'.claude/settings.json'; \
  d=json.loads(p.read_text()); d['cleanupPeriodDays']=365; \
  p.write_text(json.dumps(d,indent=2,ensure_ascii=False))"

# 2. periodic rsync backup (included)
chmod +x scripts/backup_claude_projects.sh
./scripts/backup_claude_projects.sh
# then register as launchd / cron for weekly backup
```

### Windows backup (Task Scheduler)

`scripts/backup_claude_projects.ps1` is the PowerShell-7 equivalent that uses
`robocopy /MIR /XO` to mirror `%USERPROFILE%\.claude\projects` into
`%USERPROFILE%\ClaudeCodeArchive\current`, with a dated snapshot on the side:

```powershell
# one-off run
pwsh -NoProfile -File scripts\backup_claude_projects.ps1

# dry-run (also works on macOS/Linux — great for smoke-testing)
pwsh -NoProfile -File scripts\backup_claude_projects.ps1 -WhatIf

# register as a weekly task (Sundays 03:00)
schtasks /Create /TN "vibe-resume backup" /XML scripts\vibe-resume-backup.xml
```

`scripts/vibe-resume-backup.xml` is a ready-to-import Task Scheduler template.
Edit the `<WorkingDirectory>` path before importing to point at wherever you
cloned this repo. The PowerShell script is linted by `PSScriptAnalyzer` in CI
on `windows-latest`, and the `-WhatIf` branch is also exercised there.

## Project layout

```
vibe-resume/
├── profile.example.yaml   # committed template — copy to profile.yaml
├── config.example.yaml    # committed template — auto-copied to config.yaml on first run
├── profile.yaml           # your PII (gitignored)
├── config.yaml            # your extractor paths + privacy rules (gitignored)
├── cli.py                 # entry point (also installed as `vibe-resume`)
├── core/
│   ├── schema.py          # Pydantic v2: Activity, ProjectGroup, UserProfile
│   ├── classifier.py      # 18 task categories with bilingual regex
│   ├── tech_canonical.py  # hard-skill vs domain-tag split
│   ├── stats.py           # rolling window stats (30d/7d)
│   ├── privacy.py         # redaction + blocklist + tech abstraction
│   ├── aggregator.py      # grouping + headline + significance ranking
│   ├── enricher.py        # claude -p → XYZ / noun-phrase bullets per locale
│   ├── review.py          # 8-point scorecard + trend sparkline
│   ├── versioning.py      # git snapshots of drafts
│   └── runner.py          # ThreadPoolExecutor pipeline + rich.progress
├── extractors/
│   ├── local/             # 11 local extractors
│   ├── cloud_export/      # 7 ZIP importers
│   └── api/               # 6 AIGC extractors
├── render/
│   ├── renderer.py        # md / docx / pdf
│   ├── japan.py           # JIS Z 8303 履歴書 grid (ja_JP DOCX path)
│   ├── i18n.py            # LOCALES registry + per-locale label dicts
│   └── templates/resume.<locale>.md.j2
├── scripts/
│   ├── backup_claude_projects.sh       # macOS / Linux rsync
│   ├── backup_claude_projects.ps1      # Windows PowerShell 7 (robocopy)
│   ├── vibe-resume-backup.xml          # Task Scheduler import template
│   └── com.vibe-resume.backup.plist    # macOS launchd agent
├── data/
│   ├── imports/           # put downloaded ZIPs here (gitignored except sample_jd.txt)
│   ├── cache/             # per-source extracted JSON (gitignored)
│   ├── resume_history/    # rendered outputs + internal git (gitignored)
│   └── reviews/           # review reports + history (gitignored)
├── docs/samples/          # illustrative locale-specific sample outputs
├── skills/ai-used-resume/                   # canonical Agent Skill (all 8 hosts, via symlinks)
│   ├── SKILL.md                             # 5-section body, agentskills.io compliant
│   └── references/                          # strategic-resume · troubleshooting · extending
├── .claude/skills/ai-used-resume/           → symlink → skills/ai-used-resume/
├── .gemini/skills/ai-used-resume/           → symlink → skills/ai-used-resume/
├── .agents/skills/ai-used-resume/           → symlink → skills/ai-used-resume/ (Codex + Warp)
├── .opencode/skills/ai-used-resume/         → symlink → skills/ai-used-resume/
├── .claude-plugin/plugin.json               # Claude Code plugin manifest (marketplace)
└── .codex-plugin/plugin.json                # OpenAI Codex plugin manifest (marketplace)
```

## Add a new extractor

```python
# extractors/local/mytool.py
from core.schema import Activity, ActivityType, Source
NAME = "mytool"
def extract(cfg: dict) -> list[Activity]:
    return []  # emit Activity objects
```

Register in `core/runner.py` → `LOCAL_EXTRACTORS` and enable in `config.yaml`.

## Known limits

- Full `$HOME` scan (`git_repos`, `aider`) takes 1-3 min first run even with 4× parallel extractors — switch to `scan.mode: whitelist` to scope it. `_find_repos` has a 120s wall-clock deadline to survive FUSE mounts / broken symlinks.
- Grok / Perplexity / Mistral export schemas are **lenient parsed** (schema not officially published); drop a real sample into `data/imports/` if fields don't match.
- Claude Desktop chat contents are encrypted in Local Storage — only MCP config + extensions are extractable.
- PDF rendering requires `pandoc` + XeLaTeX for CJK; falls back to plain pandoc otherwise.

## License

MIT — see [LICENSE](LICENSE).

## Related projects

Searched the 2026 landscape thoroughly — **no direct competitor** does all three of
(1) multi-source AI-tool extraction, (2) 10-locale rendering, and (3) reviewer audit.
The closest adjacent projects cover only one of the three:

- [whoisjayd/gitresume](https://github.com/whoisjayd/gitresume) — closest adjacent tool; extracts from local/remote GitHub repos → résumé bullets. Single-source (git only), single-language. `vibe-resume` adds 18 AI-tool extractors, 10 locales, and the reviewer audit.
- [AmirhosseinOlyaei/AI-Resume-Builder](https://github.com/AmirhosseinOlyaei/AI-Resume-Builder) — generates bullets from PR descriptions and commit messages. Same thesis, narrower source (no Claude Code / Cursor / ChatGPT).
- [AndreaCadonna/resumake-mcp](https://github.com/AndreaCadonna/resumake-mcp) — LaTeX résumé via MCP; render-only, no extraction layer. Complementary to our pipeline's render stage.
- [javiera-vasquez/claude-code-job-tailor](https://github.com/javiera-vasquez/claude-code-job-tailor) — YAML experience → JD-tailored PDF in Claude Code. Complementary at the JD-match stage; our `--tailor` is the same idea but starts from extracted activity rather than hand-maintained YAML.

`vibe-resume` is the only tool in this list that **extracts from multiple AI tools + renders in 10 culture-specific locales + includes reviewer audit with trend tracking**.

