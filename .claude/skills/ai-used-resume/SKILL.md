---
name: ai-used-resume
description: Extract AI tool usage history (Claude Code, Cursor, Copilot, Cline, Continue, Aider, Windsurf, Zed AI, Claude Desktop, ChatGPT/Claude.ai/Gemini/Grok/Perplexity/Mistral/Poe exports, ComfyUI/Midjourney/Suno/ElevenLabs, git commits) from the user's machine and synthesize a versioned, reviewer-scored résumé across 10 locales (en_US / en_EU / en_GB / zh_TW / zh_HK / zh_CN / ja_JP / ko_KR / de_DE / fr_FR) with Markdown / DOCX / PDF output and an 8-point reviewer-audit scorecard. Triggers when the user asks to "generate my resume from AI usage", "render my résumé in Japanese", "tailor my resume for this JD", "show my resume trend", "review my resume", or similar.
---

# vibe-resume — Claude Code Agent Skill

You are operating inside (or next to) the `vibe-resume` project. Use the current working directory first; if `cli.py` and `config.yaml` are not present, ask the user to `cd` into their clone.

## Standard workflow

1. **Check `profile.yaml`.** If it's still the example text, ask the user for name, email, target_role, summary, and optional sections (experience, education, languages, custom_sections). Don't proceed until the name is real.

   - For locale-specific output, suggest `<field>_<locale>` overrides (e.g. `title_zh_TW`, `summary_ja_JP`, `bullets_de_DE`). Reference `profile.example.yaml` for the full key list.

2. **Review `config.yaml`.**
   - `scan.mode` — `full` scans `$HOME` for every `.git`, `whitelist` restricts to `scan.roots`.
   - `privacy.blocklist` — any project names to exclude.
   - `privacy.abstract_tech` — `true` to hide concrete tech names.
   - `render.locale` — team default locale; overridden by `profile.preferred_locale` or CLI `--locale`.
   - `render.all_locales_formats` — what `--all-locales` produces per locale (default `["md"]`).

3. **Run extractors.**
   ```bash
   uv run python cli.py extract
   uv run python cli.py status     # sanity-check per-source counts
   ```

4. **Aggregate.**
   ```bash
   uv run python cli.py aggregate
   ```
   Output: `data/cache/_project_groups.json` + `_window_stats.json`.

5. **Enrich** (recommended — produces LLM-written achievements, not rule-based fallback).
   ```bash
   uv run python cli.py enrich --locale en_US                                # XYZ bullets (en_US / en_GB / en_EU)
   uv run python cli.py enrich --locale ja_JP                                # 名詞片語 bullets (ja/ko/zh/de/fr)
   uv run python cli.py enrich --tailor data/imports/jd.txt --locale en_US -n 1
   uv run python cli.py enrich --persona tech_lead --locale en_US                  # single persona
   uv run python cli.py enrich --persona tech_lead,hr,executive --locale en_US     # prep three personas in one run
   uv run python cli.py enrich --persona all --locale en_US                        # every registered persona
   uv run python cli.py personas-compare                                            # side-by-side diff (quality iteration)
   ```
   - `--locale` selects the prompt shape and language label (prevents e.g. Japanese role_label leaking Simplified Chinese).
   - `--tailor <JD.txt>` injects the JD's extracted keywords into the prompt so achievements surface them verbatim when the raw activity supports it (never invents matches).
   - `--persona <key>` biases bullet phrasing toward a reviewer archetype. Keys: `tech_lead`, `hr`, `executive`, `startup_founder`, `academic`. Accepts **comma-separated list** or `all` — each persona writes to its own cache `data/cache/_project_groups.<persona>.json`, so parallel variants coexist. Orthogonal to `--locale` and `--tailor`.
   - `personas-compare [--personas a,b] [-n N]` prints each group's role + bullets side-by-side across persona variants, so you can see whether the re-voicing meaningfully differentiates. Use this to iterate persona prompt quality.
   - `-n N` limits to the top-N groups; out-of-window groups keep prior enrichment rather than being overwritten.

6. **Render.**
   ```bash
   uv run python cli.py render -f md  --locale en_US
   uv run python cli.py render -f all --locale ja_JP         # md + docx (JIS Z 8303 履歴書) + pdf
   uv run python cli.py render --all-locales                 # fan out every registered locale
   uv run python cli.py render --all-locales --tailor data/imports/jd.txt
   ```

   **Locale resolution chain** (used by render and enrich):
   1. CLI `--locale`
   2. `profile.preferred_locale`
   3. `config.render.locale`
   4. `en_US` fallback

   Each render writes `data/resume_history/resume_v{NNN}_{locale}.{md|docx|pdf}` and commits to an internal git repo.

7. **Review & trend.** Score the output against the 8-point reviewer checklist:
   ```bash
   uv run python cli.py review                              # latest render
   uv run python cli.py review -v 9 --locale zh_TW
   uv run python cli.py review -v 12 --jd data/imports/jd.txt   # with JD keyword echo
   uv run python cli.py trend --locale ja_JP                # per-locale sparkline
   ```
   The 8 checks are: top-fold, numbers-per-bullet, keyword-echo, action-verb-first, density, red-flags (locale-aware), contact-line width, page-count estimate. Bar is grade B / 80% before sending to a real reviewer.

## Locale cheat sheet

| Locale | Style | Photo | Distinctives |
|---|---|---|---|
| `en_US` | XYZ verbs | forbidden | ATS-friendly flat skills line |
| `en_EU` | XYZ verbs | optional | Europass labelled personal-info, CEFR |
| `en_GB` | XYZ verbs | forbidden | UK spelling, Personal statement |
| `zh_TW` | 名詞片語 | optional | 繁中,中英技術混排 |
| `zh_HK` | 名詞片語 | optional | **Bilingual EN+繁 headings**, CEFR, no HKID |
| `zh_CN` | 名词短语 | optional | 简体,大厂偏美式 |
| `ja_JP` | 名詞句 | **expected** | **DOCX = JIS Z 8303 履歴書 grid** (`render/japan.py`); md = 職務経歴書 |
| `ko_KR` | 명사구 | **expected** | 자기소개서 separate doc |
| `de_DE` | Nominalphrasen | **expected** | Emits `dob`/`nationality` when set |
| `fr_FR` | groupes nominaux | optional | 1 page junior / 2 pages senior |

## Useful commands

| Command | Purpose |
|---|---|
| `uv run python cli.py status` | per-source activity counts |
| `uv run python cli.py list-versions` | resume version history (internal git log) |
| `uv run python cli.py diff v001 v002` | diff two resume versions |
| `uv run python cli.py completion zsh --install` | install shell completion so `--locale <tab>` expands |
| `uv run python cli.py company list [--tier X]` | browse 70 bundled employer profiles |
| `uv run python cli.py company show <key>` | full profile (must-haves / red flags / tips) |
| `uv run python cli.py company audit [--only-stale]` | age table; flag profiles past 90-day threshold |
| `uv run python cli.py company verify <key> [--apply]` | delegate fact-check to claude agent; auto-bump date on clean verdict |
| `uv run python cli.py company mark-verified <key>` | bump `last_verified_at` after manual fact-check |
| `scripts/backup_claude_projects.sh` | macOS/Linux rsync of `~/.claude/projects` |
| `pwsh scripts/backup_claude_projects.ps1` | Windows / cross-platform backup (supports `-WhatIf`) |

## Strategic résumé: `--company <key> --level <key>`

Both `enrich` and `review` accept these two extra axes to tailor against
a named employer and seniority bracket:

- **`--company`** — one of 70 bundled keys (see `company list`).
  Injects that profile's `enrich_bias` into the LLM prompt and adds a
  0-10 "Company keyword coverage" score to the review card (counts how
  many `keyword_anchors` the résumé actually surfaces). Apply auto-checks
  `last_verified_at` and prints a loud warning if the profile is older
  than 90 days — prompt the user to run `company verify <key>` before
  biasing against stale research.
- **`--level`** — one of `new_grad` / `junior` / `mid` / `senior` /
  `staff_plus` / `research_scientist`. Bakes in the lead-bullet signal
  the reviewer expects at that bracket, so mid-level work is not
  promoted into unsupported staff claims.

Block injection order in the enrich prompt is deterministic —
`tailor → persona → level → company` — so the most-specific lens lands
closest to the YAML emission point and wins tie-breaks.

Adding a new employer is drop-in: write `core/profiles/<key>.yaml` with
the seven required fields plus `last_verified_at: "YYYY-MM-DD"`; the
loader validates schema + tier + filename match at import time.

## How to help the user

- **Missing tool** — if the user says "my resume is missing X tool", check `extractors/{local,cloud_export,api}/`. If the tool isn't there, add a new extractor following `extractors/base.py`'s contract and register it in `core/runner.py`. Path conventions live in `config.yaml`.
- **Wrong language output** — if an enrich run produces mixed-script output (e.g. Japanese `role_label` with 简体 characters), pass `--locale <target>` so the correct prompt template + lang_label is selected. The noun-phrase prompt has explicit anti-leak rules but depends on the locale flag.
- **Score dropped after a change** — run `cli.py review --diff` (default on) to show Δ vs the previous review of the same locale, then `cli.py trend --locale <L>` for the whole history.
- **New section on résumé** — edit `profile.yaml` (`custom_sections` for awards/talks/hobbies or a bespoke key); for a new template section also edit `render/templates/resume.<locale>.md.j2`.
- **Tailor for multiple JDs** — keep multiple `data/imports/jd_<company>.txt`; enrich+render+review each before the interview cycle. `trend` shows whether tailoring helped.
- **Rollback a draft** — `cli.py list-versions` then `cd data/resume_history && git checkout <sha> -- resume_v001_en_US.md`.
- **Speed** — if extraction is slow, `git_repos`/`aider` scanning `$HOME` is usually the bottleneck. Switch `scan.mode` to `whitelist` and narrow `scan.roots`.

## Schema contract (for adding an extractor)

All extractors return `list[core.schema.Activity]`:
- `source` (enum), `session_id`, `timestamp_start`, `timestamp_end`
- `project`, `activity_type`, `tech_stack`, `keywords`, `summary`
- `user_prompts_count`, `tool_calls_count`, `files_touched`
- `raw_ref` (file:line for traceability), `extra`

Never invent activities. If a tool's data isn't reachable, return `[]` silently.

## End-to-end example: "one JD, every market"

The user: "I want to apply to roles in Japan, Germany, and Taiwan using this JD".

```bash
# 1. One LLM pass per locale (English fallback on failure is automatic)
for loc in ja_JP de_DE zh_TW; do
    uv run python cli.py enrich --tailor data/imports/jd.txt --locale "$loc" -n 3
done

# 2. Batch render those three locales
for loc in ja_JP de_DE zh_TW; do
    uv run python cli.py render -f all --locale "$loc" --tailor data/imports/jd.txt
done

# 3. Review each; bar is B/80%
for loc in ja_JP de_DE zh_TW; do
    uv run python cli.py review --locale "$loc"
done

# 4. Which one improved most vs last iteration?
uv run python cli.py trend
```
