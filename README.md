# vibe-resume

> Turn your AI coding history into a versioned, reviewer-ready résumé — **for the vibe coding era**.

[![CI](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml/badge.svg)](https://github.com/easyvibecoding/vibe-resume/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Locales](https://img.shields.io/badge/locales-9-brightgreen.svg)](docs/resume_locales.md)
[![uv](https://img.shields.io/badge/packaged%20with-uv-261230.svg)](https://github.com/astral-sh/uv)

`vibe-resume` scans every AI assistant you use on macOS (Claude Code, Cursor, GitHub Copilot, Cline, Continue, Aider, Windsurf, Zed AI, ChatGPT / Claude.ai / Gemini / Grok / Perplexity / Mistral exports, ComfyUI, Midjourney, Suno, ElevenLabs, and your `git` commits) and synthesizes the usage trail into a **Markdown / DOCX / PDF résumé** with built-in git snapshots so every draft is diff-able and rollback-able.

<p align="center">
  <em>Scan → Group by project → Classify task types → LLM-enrich to XYZ bullets → Render → Snapshot</em>
</p>

## How it differs

| | vibe-resume | Reactive Resume / OpenResume | Resume-LM / Resume Matcher | HackMyResume / JSON Resume |
|---|---|---|---|---|
| **Primary signal** | AI tool sessions + git commits (auto-extracted) | User-typed content in WYSIWYG | Uploaded PDF + JD | User-typed JSON |
| **Locales** | **9** (en_US/en_EU/en_GB/zh_TW/zh_CN/ja_JP/ko_KR/de_DE/fr_FR) with culture-specific layouts | 1–2 | 1 | Theme-dependent |
| **JP 履歴書 JIS Z 8303 grid** | ✅ `render/japan.py` | ❌ | ❌ | ❌ |
| **Europass labelled personal-info** | ✅ `en_EU` template | ❌ | ❌ | ❌ |
| **Reviewer audit** | 8-point scorecard + trend sparkline | — | ATS score only | — |
| **JD tailoring** | `enrich --tailor JD.txt` (LLM prompt injection) | — | ✅ LLM rewrite | — |
| **Privacy** | Fully local; `claude -p` headless; nothing leaves your machine | Varies (OpenAI-key optional) | Cloud API required | Fully local |
| **Shape** | Python CLI pipeline | Web UI | Web UI | Node CLI |

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

## Quick start

```bash
# 1. install
uv venv && uv pip install -e ".[dev]"

# 2. fill your profile
cp profile.example.yaml profile.yaml
$EDITOR profile.yaml        # at least name / target_role

# 3. (optional) drop cloud ZIP exports into data/imports/<tool>/

# 4. run pipeline
uv run python cli.py extract          # all enabled extractors
uv run python cli.py aggregate        # group by project + infer stack
uv run python cli.py enrich           # XYZ bullets via claude -p
uv run python cli.py render -f all    # md + docx + pdf + git snapshot
```

## Commands

| Command | What it does |
|---|---|
| `cli.py extract [--only NAME]` | run extractors, cache to `data/cache/*.json` |
| `cli.py aggregate` | group by project, classify task types, infer stack |
| `cli.py enrich [-n N] [--locale L] [--tailor JD.txt]` | generate summary + achievements (XYZ for en, noun-phrase for zh/ja/de/fr/ko); `--tailor` biases bullets toward a JD's keywords |
| `cli.py render -f md\|docx\|pdf\|all [--locale L]` | render + git snapshot |
| `cli.py render --all-locales [-f FMT]` | fan out across every registered locale in one pass |
| `cli.py render --tailor data/imports/jd.txt` | tailor for a specific job description |
| `cli.py review [-v N \| --file PATH] [--locale L] [--jd JD.txt]` | score the rendered draft against the 8-point reviewer checklist |
| `cli.py trend [--locale L]` | score history per locale with ASCII sparkline + mean + latest grade |
| `cli.py status` | show per-source activity counts |
| `cli.py list-versions` / `cli.py diff 1 2` | resume version history |

## Multi-locale rendering

`vibe-resume` ships per-locale templates so the same `profile.yaml` + project
data renders into reviewer-appropriate output in each market.

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

`--all-locales` iterates the full `LOCALES` registry (currently 9 locales).
Per-locale formats are controlled by `config.render.all_locales_formats`
(default `["md"]`) — bump it to `["md", "docx", "pdf"]` to cut full bundles.
`--locale` and `--all-locales` are mutually exclusive.

## Reviewer-view audit (`cli.py review`)

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

## Project layout

```
vibe-resume/
├── profile.yaml           # your personal info (gitignored)
├── config.yaml            # extractor toggles, paths, privacy rules, windows
├── cli.py                 # entry point
├── core/
│   ├── schema.py          # Pydantic v2: Activity, ProjectGroup, UserProfile
│   ├── classifier.py      # 18 task categories with bilingual regex
│   ├── tech_canonical.py  # hard-skill vs domain-tag split
│   ├── stats.py           # rolling window stats (30d/7d)
│   ├── privacy.py         # redaction + blocklist + tech abstraction
│   ├── aggregator.py      # grouping + headline + significance ranking
│   ├── enricher.py        # claude -p → XYZ bullets
│   ├── versioning.py      # git snapshots of drafts
│   └── runner.py
├── extractors/
│   ├── local/             # 11 local extractors
│   ├── cloud_export/      # 7 ZIP importers
│   └── api/               # 6 AIGC extractors
├── render/
│   ├── renderer.py        # md / docx / pdf
│   └── templates/resume.md.j2
├── scripts/
│   └── backup_claude_projects.sh
├── data/
│   ├── imports/           # put downloaded ZIPs here
│   ├── cache/             # per-source extracted JSON (gitignored)
│   └── resume_history/    # rendered outputs + internal git (gitignored)
└── .claude/skills/ai-used-resume/SKILL.md   # Claude Code Agent Skill
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

- Full `$HOME` scan (`git_repos`, `aider`) takes 1-3 min first run — switch to `scan.mode: whitelist` to scope it.
- Grok / Perplexity / Mistral export schemas are **lenient parsed** (schema not officially published); drop a real sample into `data/imports/` if fields don't match.
- Claude Desktop chat contents are encrypted in Local Storage — only MCP config + extensions are extractable.
- PDF rendering requires `pandoc` + XeLaTeX for CJK; falls back to plain pandoc otherwise.

## License

MIT — see [LICENSE](LICENSE).

## Related projects

- [sujankapadia/claude-code-analytics](https://github.com/sujankapadia/claude-code-analytics) — session analytics dashboard
- [yudppp/claude-code-history-mcp](https://github.com/yudppp/claude-code-history-mcp) — MCP history server
- [alicoding/claude-parser](https://github.com/alicoding/claude-parser) — Git-like conversation API
- [daaain/claude-code-log](https://github.com/daaain/claude-code-log) — HTML timeline
- [S2thend/cursor-history](https://github.com/S2thend/cursor-history) — Cursor chat export
- [AndreaCadonna/resumake-mcp](https://github.com/AndreaCadonna/resumake-mcp) — LaTeX résumé MCP

`vibe-resume` differs by **aggregating across tools** and producing resume-oriented bullets, not raw dumps.

