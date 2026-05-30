---
name: ai-used-resume
description: Generate a versioned, reviewer-scored résumé from the user's AI-coding and git history — extracts from Claude Code, Cursor, Copilot, Cline, Continue, Aider, Windsurf, Zed AI, Claude Desktop, ChatGPT/Claude.ai/Gemini/Grok/Perplexity/Mistral/Poe cloud exports, ComfyUI, Midjourney, Suno, ElevenLabs, and git commits. Renders to Markdown / DOCX / PDF across 10 locales (en_US, en_EU, en_GB, zh_TW, zh_HK, zh_CN, ja_JP, ko_KR, de_DE, fr_FR) with culture-specific layouts (JIS Z 8303 履歴書 grid, Europass, Lebenslauf, bilingual HK), optional JD-tailored bullet rewriting, and an 8-point reviewer audit with score trend. Use when the user asks to "generate my résumé", "render my résumé in Japanese", "tailor my CV for this job description", "score my résumé", or "show my résumé trend".
license: MIT
compatibility: Requires Python 3.12+ and uv. Optional pandoc (PDF rendering) and claude CLI (LLM enrichment; falls back to rule-based). Works on macOS and Linux.
metadata:
  version: "0.25.0"
  author: easyvibecoding
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
| Fresh pipeline | `uv run vibe-resume extract && uv run vibe-resume aggregate && uv run vibe-resume enrich --locale en_US` then process prompts in session, then `enrich --ingest --locale en_US && render -f all --locale en_US` |
| Render single locale | `uv run vibe-resume render -f md --locale ja_JP` |
| All 10 locales | `uv run vibe-resume render --all-locales` |
| JD-tailored run | `uv run vibe-resume enrich --tailor data/imports/jd.txt --locale en_US -n 1 && uv run vibe-resume render -f md --locale en_US --tailor data/imports/jd.txt` |
| Persona-biased enrich | `uv run vibe-resume enrich --persona tech_lead --locale en_US` (keys: `tech_lead` / `hr` / `executive` / `startup_founder` / `academic`) |
| Multi-persona enrich in one run | `uv run vibe-resume enrich --persona tech_lead,hr,executive --locale en_US` or `--persona all` — each persona writes its own `_project_groups.<persona>.json` |
| Level-tuned enrich | `uv run vibe-resume enrich --level senior --locale en_US` (keys: `new_grad` / `junior` / `mid` / `senior` / `staff_plus` / `research_scientist`) |
| Persona render | `uv run vibe-resume render --persona tech_lead --locale en_US` reads the persona-scoped cache and emits `resume_v<NNN>_<locale>_<persona>.md` |
| Compare persona output | `uv run vibe-resume personas-compare --locale en_US -n 3` — side-by-side bullets per persona for the top-N groups (quality iteration loop). `--locale` required since 0.4.0. |
| Score latest | `uv run vibe-resume review` |
| Score with JD echo | `uv run vibe-resume review --jd data/imports/jd.txt` |
| Score with persona lens | `uv run vibe-resume review --persona hr` — appends persona-specific review tips |
| **Disclose real signals (self-mine)** | `uv run vibe-resume evidence --json` — per group: candidate metrics, backed terms, human-gate evidence, provenance. `--jd <file>` adds present-but-omitted vs genuinely-absent keywords. **Surface only what's disclosed — never invent.** |
| **Ground in the code** | `uv run vibe-resume scan` → process each `*.scan.prompt.md` with a cheap-model subagent (one per project, parallel) → `uv run vibe-resume scan --ingest`. Grounds bullets in what the repo actually does. Opt-in; never uploads code, drops secrets. |
| **Fit a page budget** | `uv run vibe-resume render --max-pages 2 --locale en_US` — tighten bullet density, not just `--top-n` |
| **Standard variant set** | `uv run vibe-resume render --variants --locale en_US` — ATS (page-budgeted) + detailed, same cache |
| **Truth-preserving auto-iterate** | `uv run vibe-resume iterate --locale en_US` — lift the grade via truthful levers, stop honestly at the ceiling, print human-applied suggestions (dry-run; `--write` to snapshot) |
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

4. **Run extractors → aggregate.**

   ```bash
   uv run vibe-resume extract
   uv run vibe-resume status              # sanity-check per-source counts
   uv run vibe-resume aggregate           # → data/cache/_project_groups.json
   ```

4a. **(Default, uses subscription quota)** Emit + session-driven enrich.

   ```bash
   uv run vibe-resume enrich --locale <L>
   # → writes data/enrich_jobs/<persona-or-default>/<L>/manifest.json
   #   + one *.prompt.md per project group
   ```

   In the current Claude Code session:

   1. Read `data/enrich_jobs/<persona>/<L>/manifest.json`
   2. For each `status: pending` entry, read its `*.prompt.md`
   3. Produce strict YAML matching the schema the prompt requires
   4. Write to the entry's `output_path` (`NNN_<name>.yaml`)

   When all entries are done:

   ```bash
   uv run vibe-resume enrich --ingest --locale <L>
   # → merges *.yaml into _project_groups.<persona>.<L>.json
   ```

   Add `--level <key>` to bias bullet ambition for the seniority bracket
   (e.g. `enrich --level senior --locale en_US`).

   Multi-locale runs are independent (per-locale subdir + per-locale cache):

   ```bash
   uv run vibe-resume enrich --locale en_US
   uv run vibe-resume enrich --locale zh_TW      # does NOT overwrite en_US
   # process both locales' yaml in session…
   uv run vibe-resume enrich --ingest --locale en_US
   uv run vibe-resume enrich --ingest --locale zh_TW
   uv run vibe-resume render --locale en_US      # reads _project_groups.default.en_US.json
   uv run vibe-resume render --locale zh_TW      # reads _project_groups.default.zh_TW.json
   ```

   Pass `--tailor <JD.txt>` to bias bullets toward JD keywords (up to 12 extracted via
   tech-priority dict + capitalised fallback — see
   [references/tailor-keyword-extraction.md](references/tailor-keyword-extraction.md)
   for the strategy and the 12-keyword cap rationale).

   Stacks with `--persona`/`--company` per `references/strategic-resume.md` §Axis matrix.

   See `tests/fixtures/enrich_jobs_sample/` for a reference of what the
   manifest + prompt + yaml triple looks like.

4b. **(Fallback for CI / non-interactive)** Spawn `claude -p` subprocess.

   ```bash
   uv run vibe-resume enrich --mode subprocess --locale <L>
   ```

   This bills against the Anthropic Agent SDK monthly quota pool (Pro $20 /
   Max 20x $200, separate from the Claude Code subscription quota — change
   effective 2026-06-15). The CLI prints a red warning at startup.

   `--mode rule-based` skips LLM entirely and uses heuristic summaries
   (works without any `claude` binary).

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

7. **Self-mine the real signals, then iterate truthfully.** Don't guess what to
   strengthen — disclose it:
   ```bash
   uv run vibe-resume evidence --jd data/imports/jd.txt   # what's REALLY there
   uv run vibe-resume iterate --locale en_US              # truth-preserving lift, stops honestly
   ```
   `evidence` discloses, per group, the candidate metrics, backed terms,
   human-gate evidence, and provenance the tool can actually see — so you (the
   agent) surface only disclosed signals and never invent. `iterate` tightens the
   page budget to lift the grade and reports the honest ceiling + human-applied
   suggestions. **The score is a proxy: never trade truthfulness or
   human-in-the-loop for points** — see [docs/PRINCIPLES.md](../../docs/PRINCIPLES.md).

## Pitfalls

The full catalogue of failure modes and their fixes — mixed-script
locale leaks, `--all-locales` format quirk, first-run extraction
slowness, CJK contact-line wrapping, the `claude -p` optional fallback,
and the privacy rules around `profile.yaml` / `data/imports/` — lives
in [references/troubleshooting.md](references/troubleshooting.md).

- `personas-compare` requires `--locale` (the enriched cache split per-locale in 0.4.0); see CHANGELOG.

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

`enrich` and `review` accept two extra axes — a named target employer
(70 bundled profiles in `src/vibe_resume/core/profiles/*.yaml`) and a seniority bracket
(6 career-level archetypes) — stacked on top of `--locale` /
`--persona` / `--tailor`. Block injection order is
`tailor → persona → level → company`. Every apply auto-checks
`last_verified_at` and warns loudly if older than 90 days.

See [references/strategic-resume.md](references/strategic-resume.md) for
the full axis reference, `company list`/`show`/`audit`/`verify`/
`mark-verified` commands, and the drop-in recipe for adding a new
employer profile.

## Extending the pipeline

When the user asks to add a new extractor, locale, or persona, consult
[references/extending.md](references/extending.md) for the `Activity`
schema contract, registration steps, and the "never invent activities"
rule.

## Useful sibling commands

- `uv run vibe-resume status` — per-source activity counts
- `uv run vibe-resume list-versions` — résumé version history from internal git
- `uv run vibe-resume diff v001 v002` — diff two versions
- `uv run vibe-resume completion zsh --install` — shell completion so `--locale <tab>` expands
- `uv run vibe-resume doctor` — diagnose CLI/plugin version drift, profile/config presence, optional-dep availability
- `scripts/backup_claude_projects.sh` (macOS/Linux) / `scripts/backup_claude_projects.ps1` (Windows) — back up `~/.claude/projects` before Claude Code's 30-day cleanup
