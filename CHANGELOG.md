# Changelog

All notable changes to `vibe-resume`. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (on `main`, not yet tagged)
- **`cli.py trend`** — per-locale review score history with ASCII
  sparkline, mean %, and grade of latest run.
- **`cli.py render --all-locales`** batch mode + `config.render.all_locales_formats`
  to control which formats fan out per locale (default `["md"]`).
- **Locale resolution chain** on renderer: CLI `--locale` >
  `profile.preferred_locale` > `config.render.locale` > `en_US`.
- **JD tokenizer hardening** (`core.review.parse_jd_keywords`): prefers
  known tech names (`_JD_TECH_PRIORITY`), skips structural noise
  (`_JD_STOPWORDS`); keyword echo went 10/12 → 12/12 on the sample JD.
- 18 additional unit tests (41 total now) — parse_jd_keywords /
  find_previous_review / ReviewReport.grade boundaries / _pick_template /
  _build_prompt across en_US, zh_TW, zh_CN, ja_JP, de_DE.
- **`en_EU` locale** — Europass-styled English CV. Labelled Personal
  information list (not a centered strip), Occupation/Employer fields
  under each experience block (matches Europass XML schema labels),
  CEFR languages section, GDPR-minimal personal data.
- **`cli.py enrich --tailor JD.txt`** — injects `parse_jd_keywords`
  output into the enrich prompt as a "Tailor hint" block so
  achievements surface JD keywords verbatim when the raw activity
  supports them (explicit "never invent a match" rule). Verified on
  `rag-search-platform`: non-tailor run produced metric-rich but
  keyword-neutral bullets; tailor run surfaced FastAPI / pgvector /
  Next.js / TypeScript / Docker / AWS verbatim and added `RAG` to
  `tech_stack`.
- README: `trend` / `render --all-locales` / locale resolution chain /
  `enrich --tailor` sections.

### Verified (on top of the 0.1 list)
- `cli.py enrich --locale ko_KR -n 1` → native Korean output
  (풀스택 엔지니어, 설계·배포, 구현, 단축), tech nouns stay English
  (FastAPI / pgvector / Next.js / Docker / AWS / Claude Code).
- `cli.py enrich --locale zh_CN -n 1` → all Simplified Chinese
  (全栈工程师, 设计, 构建, 部署, 重构, 修复), zero Traditional-only
  character leak.

### Verified
- Enrichment prompt dispatch produces **native output** in every
  noun-phrase locale we ran end-to-end with `claude -p`:
  - zh_TW: 「設計並部署基於 FastAPI 與 pgvector 的 RAG 搜尋平台…」
  - ja_JP: 「FastAPIとpgvectorを核にRAG検索基盤を設計し…」 *(headline 「フルスタック + DevOps」, no 简体 leakage)*
  - de_DE: 「Full-Stack-Engineer für RAG-Suchplattform mit FastAPI…」
  - fr_FR: 「Ingénieur full-stack sur plateforme RAG Python/FastAPI…」
  - Tech nouns (FastAPI, PostgreSQL, Next.js) stay English per the
    prompt rule; metric numbers from source data flow through unchanged.

### Planned for v0.2

- **More locales**: `zh_HK` (bilingual EN+繁), `en_SG` (NRIC-aware). *(`en_EU` done above.)*
- **`cli.py render --tailor` + review `--jd`** integrated into a single "target" object (one JD passed once, used everywhere).
- **Windows backup**: `scripts/backup_claude_projects.ps1` + Task Scheduler XML, paired with the existing macOS launchd and Linux cron docs.
- **PDF cover page**: optional one-page hero summary before the main resume (`render.cover_page: true`); useful for de_DE Lebenslauf + JP 履歴書 bundles.
- **Extractor hardening**: real-sample validation for Grok / Perplexity / Mistral / Poe cloud exports — schemas are currently lenient-parsed.
- **JP 履歴書 legacy cells**: optional 通勤時間 / 扶養家族 / 配偶者 cells (some traditional employers still expect these).
- **Shell completions**: `cli.py completion install {bash,zsh,fish}` so `uv run vibe-resume render --locale <tab>` works.
- **Prompt coverage**: verify ko_KR / zh_CN LLM output end-to-end (same way we verified zh_TW/ja_JP/de_DE/fr_FR in 0.1).

## [0.1.0] — 2026-04-20

First public-ready cut: end-to-end pipeline from AI-tool extractors through
LLM enrichment to multi-locale rendering, plus an automated reviewer audit.

### Added

- **Local extractors** (11): Claude Code · Claude Code Archive · Cursor ·
  Cline · Continue.dev · Aider · Windsurf / Cascade · Copilot (VS Code) ·
  Zed · Claude Desktop (config + extensions) · `git` commits filtered by
  author email.
- **Cloud export importers** (7): ChatGPT · Claude.ai · Gemini Takeout ·
  Grok · Perplexity · Mistral · Poe (drop ZIPs into `data/imports/<tool>/`).
- **AIGC extractors** (6): ComfyUI / A1111 PNG metadata · Midjourney IPTC ·
  ElevenLabs · Suno · Runway · HeyGen.
- **Aggregation pipeline**: 18-category bilingual task classifier,
  capability-breadth ranking, 30-day rolling window stats, project grouping
  with significance ranking.
- **LLM enrichment** (`core/enricher.py`): headless `claude -p` invocation
  with two prompt shapes —
  - `style="xyz"` (en_US / en_GB) — Google XYZ action-verb bullets
  - `style="noun_phrase"` (zh / ja / de / fr / ko) — fact-first noun-phrase
    bullets with explicit anti-leak rules so a Japanese `role_label` cannot
    drift to `全栈` instead of `フルスタック`.
  `--limit N` now preserves out-of-window groups instead of overwriting
  them with a fallback summary.
- **Multi-locale rendering** with 9 templates:
  | Locale | Template | Notable specifics |
  |---|---|---|
  | `en_US` | `resume.en_US.md.j2` | ATS-friendly flat skills line, XYZ verbs |
  | `en_GB` | `resume.en_GB.md.j2` | UK spellings, `Personal statement` heading, CEFR languages |
  | `zh_TW` | `resume.zh_TW.md.j2` | 繁中 noun-phrase, 兩行 contact, `localized()` field fallback |
  | `zh_CN` | `resume.zh_CN.md.j2` | 简体, 大厂友善 default (no photo / 政治面貌) |
  | `ja_JP` | `resume.ja_JP.md.j2` (職務経歴書) + `render/japan.py` (履歴書 DOCX grid, JIS Z 8303) |
  | `ko_KR` | `resume.ko_KR.md.j2` | 이력서 sections; 자기소개서 left as separate doc |
  | `de_DE` | `resume.de_DE.md.j2` | `Persönliche Daten` block; renders `dob` / `nationality` when set |
  | `fr_FR` | `resume.fr_FR.md.j2` | Profil / Compétences / Expérience / Centres d'intérêt |
  | (default) | `resume.md.j2` | locale-agnostic fallback when no `.<locale>.j2` exists |
- **i18n machinery** (`render/i18n.py`):
  - `LOCALES` dict captures per-locale style / photo rule / personal-field list / heading labels / date format / filename style.
  - `format_date(value, locale)` Jinja filter — handles ISO inputs, "Present"-style tokens (normalized per language), and CJK literal patterns like `%Y年%m月`.
  - `localized(obj, key, locale)` Jinja filter — reads `<key>_<locale>` when set, falls back to canonical key (powered by `UserProfile.model_config = ConfigDict(extra="allow")`).
- **Profile schema** (`core/schema.py`): formal optional fields for
  `dob` / `gender` / `nationality` / `marital_status` / `mil_service` /
  `photo_path`. Locale templates only emit them when the active locale's
  `personal_fields` list includes them and the value is set.
- **DOCX rendering**:
  - Photo-expected locales (`de_DE`, `ko_KR`) use an invisible 1×2 layout
    table so the photo sits in the true top-right next to the
    name/title/contacts block.
  - `ja_JP` is dispatched to `render/japan.py` which emits a JIS-style
    履歴書 with photo cell, ふりがな row, 学歴・職歴 grid, 免許・資格,
    志望動機 sections.
- **PDF rendering**: pandoc + XeLaTeX with CJK font, falls back to plain
  pandoc if XeLaTeX is missing.
- **Reviewer audit** (`core/review.py`, `cli.py review`): 8-point scorecard
  (top fold · numbers per bullet · keyword echo (JD) · action-verb first ·
  density · red flags · contact-line width · page-count estimate). Outputs
  human + JSON scorecards, with `--diff` to show Δ vs the previous review
  of the same locale and line-number examples for non-conforming bullets.
- **Versioning** (`core/versioning.py`): every render commits a snapshot
  to an internal git repo at `data/resume_history/`, with
  `cli.py list-versions` and `cli.py diff` for navigation.
- **Privacy filter** (`core/privacy.py`): regex redaction of API keys /
  emails / passwords; project blocklist; optional tech-name abstraction.
- **Claude Code agent skill**: `.claude/skills/ai-used-resume/SKILL.md`
  ships an in-Claude entry point.
- **Backup script**: `scripts/backup_claude_projects.sh` rsync-backs
  `~/.claude/projects` so the 30-day cleanup window doesn't erase history.
- **Docs**: `docs/resume_locales.md` (per-region research, decision matrix,
  reviewer-view checklist) and `docs/review_v007.md` (worked example
  scorecard from the first end-to-end run).

### Known limits

- Full `$HOME` git scan takes 1–3 min on first run; switch to
  `scan.mode: whitelist` for faster iteration.
- `claude_desktop` extractor only sees MCP config + extensions; chat
  contents are encrypted in Local Storage.
- Grok / Perplexity / Mistral cloud exports are lenient-parsed (no
  official schema); drop a real sample into `data/imports/<tool>/` if a
  field doesn't map.
- `ja_JP` 履歴書 grid covers core JIS cells but skips legacy
  通勤時間 / 扶養家族 / 印鑑欄.
