---
name: ai-used-resume
description: Generate a versioned, reviewer-scored résumé from the user's AI-coding and git history — extracts from Claude Code, Cursor, Copilot, Cline, Continue, Aider, Windsurf, Zed AI, Claude Desktop, ChatGPT/Claude.ai/Gemini/Grok/Perplexity/Mistral/Poe cloud exports, ComfyUI, Midjourney, Suno, ElevenLabs, and git commits. Renders to Markdown / DOCX / PDF across 10 locales (en_US, en_EU, en_GB, zh_TW, zh_HK, zh_CN, ja_JP, ko_KR, de_DE, fr_FR) with culture-specific layouts (JIS Z 8303 履歴書 grid, Europass, Lebenslauf, bilingual HK), optional JD-tailored bullet rewriting, and an 8-point reviewer audit with score trend. Use when the user asks to "generate my résumé", "render my résumé in Japanese", "tailor my CV for this job description", "score my résumé", or "show my résumé trend".
version: 0.2.0
author: easyvibecoding
license: MIT
metadata:
  hermes:
    tags:
      - resume
      - cv
      - career
      - ai-coding-assistant
      - claude-code
      - cursor
      - copilot
      - multi-locale
      - i18n
      - europass
      - rirekisho
      - ats-friendly
    platform:
      - macos
      - linux
    requires:
      - python>=3.12
      - uv
      - pandoc        # optional — enables PDF rendering
      - claude        # optional — headless LLM enrichment; falls back to rule-based summary if missing
    homepage: https://github.com/easyvibecoding/vibe-resume
---

# ai-used-resume

## When to Use

Invoke this skill whenever the user wants to **turn their AI-tool usage history into a résumé artefact**. Common triggers:

- "Generate my résumé from my AI usage."
- "Render my CV in Japanese / German / Traditional Chinese / Europass."
- "Tailor my résumé for this JD."
- "Review / score my latest résumé."
- "Show my résumé score trend."
- "Which locales am I weakest in?"

**Do NOT** invoke when the user:
- Asks to *write* résumé content from scratch without AI-usage history (no signal source).
- Wants a generic CV template — this skill is opinionated about the AI-coding-era narrative.
- Asks for a profile on a platform that doesn't use Markdown/DOCX/PDF (e.g. LinkedIn scraping).

## Quick Reference

| Intent | Command |
|---|---|
| Fresh pipeline | `uv run vibe-resume extract && uv run vibe-resume aggregate && uv run vibe-resume enrich --locale en_US && uv run vibe-resume render -f all` |
| Render single locale | `uv run vibe-resume render -f md --locale ja_JP` |
| All 10 locales | `uv run vibe-resume render --all-locales` |
| JD-tailored run | `uv run vibe-resume enrich --tailor data/imports/jd.txt --locale en_US -n 1 && uv run vibe-resume render -f md --locale en_US --tailor data/imports/jd.txt` |
| Persona-biased enrich | `uv run vibe-resume enrich --persona tech_lead --locale en_US` (keys: `tech_lead` / `hr` / `executive` / `startup_founder` / `academic`) |
| Multi-persona enrich in one run | `uv run vibe-resume enrich --persona tech_lead,hr,executive --locale en_US` or `--persona all` — each persona writes its own `_project_groups.<persona>.json` |
| Persona render | `uv run vibe-resume render --persona tech_lead --locale en_US` reads the persona-scoped cache and emits `resume_v<NNN>_<locale>_<persona>.md` |
| Compare persona output | `uv run vibe-resume personas-compare -n 3` — side-by-side bullets per persona for the top-N groups (quality iteration loop) |
| Score latest | `uv run vibe-resume review` |
| Score with JD echo | `uv run vibe-resume review --jd data/imports/jd.txt` |
| Score with persona lens | `uv run vibe-resume review --persona hr` — appends persona-specific review tips |
| Per-locale trend | `uv run vibe-resume trend --locale zh_TW` |

| Locale quick map | |
|---|---|
| `en_US` | default, XYZ verbs, ATS flat skills |
| `en_EU` | Europass labelled personal-info, CEFR |
| `en_GB` | UK spelling, Personal statement |
| `zh_TW` | 繁中,中英技術混排 |
| `zh_HK` | **bilingual EN + 繁** headings |
| `zh_CN` | 简体,大厂 ATS-friendly |
| `ja_JP` | **DOCX = JIS Z 8303 履歴書 grid**; md = 職務経歴書 |
| `ko_KR` | 이력서 + photo expected |
| `de_DE` | Lebenslauf + Persönliche Daten, photo expected |
| `fr_FR` | Profil / Compétences / Expérience |

## Procedure

1. **Locate the repo.** The CLI binary is `vibe-resume`; check with `which vibe-resume` or `uv run vibe-resume --help`. If not installed, ask the user whether to clone https://github.com/easyvibecoding/vibe-resume and run `uv venv && uv pip install -e ".[dev]"`.

2. **Verify `profile.yaml`.**
   - If still the example (`Your Name` placeholder), ask for `name`, `email`, `target_role`, `summary`. Optional: `experience`, `education`, `languages`, `custom_sections`.
   - For locale-specific text, use `<field>_<locale>` overrides (e.g. `title_zh_TW`, `summary_ja_JP`, `bullets_de_DE`). See `profile.example.yaml` for the full list including locale-conditional personal fields (`dob`, `gender`, `nationality`, `mil_service`, `photo_path`, `marital_status`) — only rendered when the active locale's `personal_fields` includes them.

3. **Confirm `config.yaml` knobs.**
   - `scan.mode` — `full` for all `$HOME` `.git` repos, `whitelist` to restrict to `scan.roots` (use if first run is slow).
   - `privacy.blocklist` — project names to exclude from extractor output.
   - `privacy.abstract_tech` — `true` to hide concrete tech names.
   - `render.locale` — team default.
   - `render.all_locales_formats` — formats per locale for `--all-locales` (default `["md"]`).

4. **Run extractors → aggregate → enrich.**
   ```bash
   uv run vibe-resume extract
   uv run vibe-resume status              # sanity-check per-source counts
   uv run vibe-resume aggregate           # → data/cache/_project_groups.json
   uv run vibe-resume enrich --locale <L> # XYZ (en_*) or noun-phrase (zh/ja/ko/de/fr)
   ```
   - Add `--tailor data/imports/jd.txt` to bias achievements toward a job description's keywords (never invents matches the raw activity doesn't support).
   - Add `-n N` to limit to the top-N project groups; out-of-window groups retain prior enrichment rather than being overwritten.

5. **Render.**
   ```bash
   uv run vibe-resume render -f md  --locale en_US
   uv run vibe-resume render -f all --locale ja_JP     # DOCX = JIS 履歴書 grid
   uv run vibe-resume render --all-locales             # fan out over 10 locales
   uv run vibe-resume render --all-locales --tailor data/imports/jd.txt
   ```

   Locale resolution chain (same chain applies to `enrich`):
   1. CLI `--locale`
   2. `profile.preferred_locale`
   3. `config.render.locale`
   4. `en_US` fallback

6. **Review & trend.**
   ```bash
   uv run vibe-resume review --jd data/imports/jd.txt   # 8-point scorecard, graded A–F
   uv run vibe-resume trend --locale ja_JP              # ASCII sparkline across all prior runs
   ```

   Bar is grade **B / 80%** before sending a draft to a real reviewer.

## Pitfalls

- **Japanese `role_label` leaking Simplified Chinese.** The noun-phrase prompt has an anti-leak rule, but it only fires when `--locale ja_JP` is passed. Always be explicit about locale on `enrich`.
- **`git_repos` / `aider` extractors scanning the entire `$HOME` take 1–3 min on first run.** If the user is waiting and asks why, switch `scan.mode` to `whitelist` in `config.yaml` and list their project directories in `scan.roots`.
- **`data/imports/` is gitignored except for `sample_jd.txt`.** The user's real JD files live here and must NOT end up in commits.
- **`claude -p` is optional.** If the user has no `claude` binary, the enricher falls back to rule-based summaries — functional but weaker. Tell the user.
- **`--all-locales` honours `config.render.all_locales_formats`, not `--format`.** If they passed `-f docx`, that overrides. If they omitted `-f`, the config list drives output (default `["md"]`).
- **Contact line wrap in CJK locales.** If `review` flags `contact_line_width`, the fix is usually splitting the contact row into two lines (already done in the zh_TW template; port if a new locale is added).
- **`profile.yaml` should never be committed** — it's in `.gitignore` and contains the user's real PII. If the user accidentally stages it, refuse and tell them.

## Verification

After a full run, confirm:

```bash
# 1. Render produced the expected files
ls data/resume_history/ | tail -n 10

# 2. Last review was ≥ B grade
uv run vibe-resume review --locale <L> | tail -n 5

# 3. Trend trending up
uv run vibe-resume trend --locale <L>
```

For a JD-tailored run, spot-check that the output bullets surface the JD's key nouns:

```bash
grep -iE "$(awk '/[A-Z][A-Za-z]{3,}/{print $1}' data/imports/jd.txt | head -5 | paste -sd '|' -)" data/resume_history/resume_v*_<L>.md
```

For multi-locale batch runs, make sure there's no cross-script leak:

```bash
# ja_JP render must not contain Traditional-only Chinese (e.g. 設計, 處理, 實作)
grep -cE "設計|處理|實作|業務" data/resume_history/resume_v*_ja_JP.md    # expect 0 or very low
# zh_CN must not contain Traditional-only characters (e.g. 設, 實, 業)
grep -cE "設|實|業" data/resume_history/resume_v*_zh_CN.md              # expect 0
```

## End-to-end example — "one JD, every market"

```bash
# LLM pass per locale
for loc in en_US ja_JP de_DE zh_TW; do
  uv run vibe-resume enrich --tailor data/imports/jd.txt --locale "$loc" -n 3
done

# Batch render
for loc in en_US ja_JP de_DE zh_TW; do
  uv run vibe-resume render -f all --locale "$loc" --tailor data/imports/jd.txt
done

# Review each and show the trend
for loc in en_US ja_JP de_DE zh_TW; do
  uv run vibe-resume review --locale "$loc"
done
uv run vibe-resume trend
```

## Strategic résumé: `--company <key> --level <key>`

70 bundled company profiles (`core/profiles/*.yaml`) + 6 career-level
archetypes let you tailor `enrich` and `review` against a named target
employer on top of locale/persona/JD. Each profile carries
`last_verified_at` metadata so stale research surfaces loudly.

- `uv run vibe-resume company list [--tier X]` — catalogue grouped by
  tier (frontier_ai / ai_unicorn / regional_ai / tw_local / us_tier2 /
  eu / jp / kr).
- `uv run vibe-resume company show <key>` — full profile (must-haves,
  red flags, keyword anchors, enrich_bias, review_tips, verified date).
- `uv run vibe-resume company audit [--only-stale]` — age table across
  all profiles; default staleness threshold is 90 days (quarterly refresh
  cadence matched to current AI-hiring market churn).
- `uv run vibe-resume company verify <key> [--apply]` — delegates a
  fact-check to `claude -p`; saves the markdown report under
  `data/verification_reports/`; auto-bumps the verified date when the
  agent returns `VERDICT: clean`.
- `uv run vibe-resume company mark-verified <key>` — bump
  `last_verified_at` in place (one-line YAML edit, preserves formatting).

Apply via `--company <key>` on `enrich` or `review`; apply stacks with
`--level <key>` (`new_grad`/`junior`/`mid`/`senior`/`staff_plus`/
`research_scientist`). Enrich injects the company's `enrich_bias` into
the prompt (block order: tailor → persona → level → company). Review
adds a 0-10 "Company keyword coverage" score that counts how many
`keyword_anchors` actually surface in the résumé.

Every `--company` apply auto-prints a warning and the refresh
instruction when the profile is older than 90 days — never silently
tailors against stale research.

## Useful sibling commands

- `uv run vibe-resume status` — per-source activity counts
- `uv run vibe-resume list-versions` — résumé version history from internal git
- `uv run vibe-resume diff v001 v002` — diff two versions
- `uv run vibe-resume completion zsh --install` — shell completion so `--locale <tab>` expands
- `scripts/backup_claude_projects.sh` (macOS/Linux) / `scripts/backup_claude_projects.ps1` (Windows) — back up `~/.claude/projects` before Claude Code's 30-day cleanup
