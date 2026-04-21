---
name: ai-used-resume
description: Extract AI tool usage history (Claude Code, Cursor, Copilot, Cline, Continue, Aider, Windsurf, Zed AI, Claude Desktop, ChatGPT/Claude.ai/Gemini/Grok/Perplexity/Mistral/Poe exports, ComfyUI/Midjourney/Suno/ElevenLabs, git commits) from the user's machine and synthesize a versioned, reviewer-scored résumé across 10 locales (en_US / en_EU / en_GB / zh_TW / zh_HK / zh_CN / ja_JP / ko_KR / de_DE / fr_FR) with Markdown / DOCX / PDF output and an 8-point reviewer-audit scorecard. Triggers when the user asks to "generate my resume from AI usage", "render my résumé in Japanese", "tailor my resume for this JD", "show my resume trend", "review my resume", or similar.
license: MIT
compatibility: Requires Python 3.12+ and uv. Optional pandoc (PDF rendering) and claude CLI (LLM enrichment; falls back to rule-based). Works on macOS and Linux.
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
   uv run vibe-resume extract
   uv run vibe-resume status     # sanity-check per-source counts
   ```

4. **Aggregate.**
   ```bash
   uv run vibe-resume aggregate
   ```
   Output: `data/cache/_project_groups.json` + `_window_stats.json`.

5. **Enrich** (recommended — produces LLM-written achievements, not rule-based fallback).
   ```bash
   uv run vibe-resume enrich --locale en_US                                # XYZ bullets (en_US / en_GB / en_EU)
   uv run vibe-resume enrich --locale ja_JP                                # 名詞片語 bullets (ja/ko/zh/de/fr)
   uv run vibe-resume enrich --tailor data/imports/jd.txt --locale en_US -n 1
   uv run vibe-resume enrich --persona tech_lead --locale en_US                  # single persona
   uv run vibe-resume enrich --persona tech_lead,hr,executive --locale en_US     # prep three personas in one run
   uv run vibe-resume enrich --persona all --locale en_US                        # every registered persona
   uv run vibe-resume personas-compare                                            # side-by-side diff (quality iteration)
   ```
   - `--locale` selects the prompt shape and language label (prevents e.g. Japanese role_label leaking Simplified Chinese).
   - `--tailor <JD.txt>` injects the JD's extracted keywords into the prompt so achievements surface them verbatim when the raw activity supports it (never invents matches).
   - `--persona <key>` biases bullet phrasing toward a reviewer archetype. Keys: `tech_lead`, `hr`, `executive`, `startup_founder`, `academic`. Accepts **comma-separated list** or `all` — each persona writes to its own cache `data/cache/_project_groups.<persona>.json`, so parallel variants coexist. Orthogonal to `--locale` and `--tailor`.
   - `personas-compare [--personas a,b] [-n N]` prints each group's role + bullets side-by-side across persona variants, so you can see whether the re-voicing meaningfully differentiates. Use this to iterate persona prompt quality.
   - `-n N` limits to the top-N groups; out-of-window groups keep prior enrichment rather than being overwritten.

6. **Render.**
   ```bash
   uv run vibe-resume render -f md  --locale en_US
   uv run vibe-resume render -f all --locale ja_JP         # md + docx (JIS Z 8303 履歴書) + pdf
   uv run vibe-resume render --all-locales                 # fan out every registered locale
   uv run vibe-resume render --all-locales --tailor data/imports/jd.txt
   ```

   **Locale resolution chain** (used by render and enrich):
   1. CLI `--locale`
   2. `profile.preferred_locale`
   3. `config.render.locale`
   4. `en_US` fallback

   Each render writes `data/resume_history/resume_v{NNN}_{locale}.{md|docx|pdf}` and commits to an internal git repo.

7. **Review & trend.** Score the output against the 8-point reviewer checklist:
   ```bash
   uv run vibe-resume review                              # latest render
   uv run vibe-resume review -v 9 --locale zh_TW
   uv run vibe-resume review -v 12 --jd data/imports/jd.txt   # with JD keyword echo
   uv run vibe-resume trend --locale ja_JP                # per-locale sparkline
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
| `uv run vibe-resume status` | per-source activity counts |
| `uv run vibe-resume list-versions` | resume version history (internal git log) |
| `uv run vibe-resume diff v001 v002` | diff two resume versions |
| `uv run vibe-resume completion zsh --install` | install shell completion so `--locale <tab>` expands |
| `uv run vibe-resume company list [--tier X]` | browse 70 bundled employer profiles |
| `uv run vibe-resume company show <key>` | full profile (must-haves / red flags / tips) |
| `uv run vibe-resume company audit [--only-stale]` | age table; flag profiles past 90-day threshold |
| `uv run vibe-resume company verify <key> [--apply]` | delegate fact-check to claude agent; auto-bump date on clean verdict |
| `uv run vibe-resume company mark-verified <key>` | bump `last_verified_at` after manual fact-check |
| `scripts/backup_claude_projects.sh` | macOS/Linux rsync of `~/.claude/projects` |
| `pwsh scripts/backup_claude_projects.ps1` | Windows / cross-platform backup (supports `-WhatIf`) |

## Strategic résumé: `--company <key> --level <key>`

`enrich` and `review` accept two extra axes — a named target employer
(70 bundled profiles) and a seniority bracket — stacked on top of
`--locale` / `--persona` / `--tailor`. Block injection order is
`tailor → persona → level → company`.

See [references/strategic-resume.md](references/strategic-resume.md) for
the full axis reference, catalogue-management commands, 90-day staleness
guard, and the drop-in recipe for adding a new employer profile.

## How to help the user

Common failure modes and their fixes — mixed-script locale leaks, slow
extraction, score regressions, missing extractors, rollback, and the
privacy rules around `profile.yaml` / `data/imports/` — are catalogued
in [references/troubleshooting.md](references/troubleshooting.md).
Consult it when the user reports an issue or asks how to extend the
pipeline.

## Extending the pipeline

When the user asks to add a new extractor, locale, or persona, consult
[references/extending.md](references/extending.md) for the `Activity`
schema contract, registration steps, and the "never invent activities"
rule.

## End-to-end example: "one JD, every market"

The user: "I want to apply to roles in Japan, Germany, and Taiwan using this JD".

```bash
# 1. One LLM pass per locale (English fallback on failure is automatic)
for loc in ja_JP de_DE zh_TW; do
    uv run vibe-resume enrich --tailor data/imports/jd.txt --locale "$loc" -n 3
done

# 2. Batch render those three locales
for loc in ja_JP de_DE zh_TW; do
    uv run vibe-resume render -f all --locale "$loc" --tailor data/imports/jd.txt
done

# 3. Review each; bar is B/80%
for loc in ja_JP de_DE zh_TW; do
    uv run vibe-resume review --locale "$loc"
done

# 4. Which one improved most vs last iteration?
uv run vibe-resume trend
```
