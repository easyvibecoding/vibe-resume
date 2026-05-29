# Changelog

All notable changes to `vibe-resume`. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.15.0] — 2026-05-29

### Added

- **AI-proficiency rubric** (#47) — a bundled, cited, dated `market_rubric.yaml`
  (winning-bullet formula, senior differentiators, anti-patterns, agentic
  keyword set, regex yellow-flags, and metric hints) now drives both generation
  and scoring, so output stops plateauing at "uses AI" framing.
  - **enrich** — a gated `AI_PROFICIENCY_BLOCK` injects the formula
    (*directing verb + named tool + scale + measurable delta + human quality
    gate*), senior differentiators, and junior-tell anti-patterns into the LLM
    prompt — but only when the group carries agentic signals (#43/#44/#45/#48),
    the agentic persona is active, or the emphasis mentions AI. Non-fabrication
    rule preserved.
  - **review** — two new scorecard checks: a positive **AI proficiency** check
    (rewards AI bullets that pair a tool with a human quality gate) and a
    negative **AI framing red flags** check (junior volume-bragging, stale-stack
    headline, unverified-judge claim, bare tool name-drop). Both self-skip
    (`max=0`) when the résumé has no AI content, so non-AI résumés keep their
    denominator and scores stay comparable across versions.
  - **metric guidance, not fabrication** — a number-less AI bullet gets a
    *pointer* to a real metric to measure (review round-trips, first-pass QA %,
    token-cost %, eval task-completion) — never an injected value.
- The rubric loader prefers a `data/cache/market_rubric.yaml` override when
  present, wiring it forward for the #46 research/market-refresh pass with zero
  rework.

## [0.14.0] — 2026-05-29

### Added

- **Installed-toolkit extractor** (`installed_env`, opt-in, #45) — inventories
  the configured agentic toolkit: Claude Code plugins
  (`~/.claude/plugins/installed_plugins.json`), standalone Agent Skills
  (`~/.claude/skills/<name>/`), and configured MCP servers (`mcpServers` in
  `~/.claude.json` / settings / Claude Desktop config). Emits one synthetic
  "Agentic Toolkit" group (exempt from the noise filter) that the enricher
  frames as installed/curated — distinct from authored and used (#43).
  **Privacy-critical: only names + coarse transport are captured — never MCP
  `env`/`args`/`url` values — and names run through `redact_patterns`.**

## [0.13.0] — 2026-05-29

### Added

- **Multi-agent orchestration signal** (`AgenticSignals.orchestration`, #48) —
  detects subagents, parallel fan-out, supervisor/worker, fan-out→verify
  pipelines, workflow scripts, and Agent SDK usage as distinct pattern tags
  (from activity text + `skills_used`), instead of folding them into a generic
  `agent-tooling %`. The enricher surfaces the topology — flagging a
  verification/judge stage as a senior signal. Completes the competency-signal
  set (tools #43 · methodology #44 · process #48).

## [0.12.0] — 2026-05-29

### Added

- **SDD / TDD methodology signal** (`AgenticSignals.sdd` / `.tdd`, #44) —
  detects Spec-Driven Development (OpenSpec / Spec-Kit / `specs/<feature>/`
  trees / spec-kit artifacts) and Test-Driven Development (test-driven /
  red-green / failing-test-first), distinct from mere test presence. The
  enricher surfaces these as methodology bullets.

### Fixed

- **Bare `spec` no longer mis-books spec-driven work as testing** (#44). The
  classifier TESTING regex dropped the bare `\bspec\b` token (kept `.spec.` /
  `_spec` / `tests`), so `spec.md` / `specs/` / OpenSpec stop inflating the
  `testing %` and instead feed the new SDD signal.

## [0.11.0] — 2026-05-29

### Added

- **Agent Skills + MCP competency signal** (`AgenticSignals` on each project
  group, #43) — distinguishes **authoring** from **usage**: skills authored
  (from `SKILL.md` / `skills/<name>/` / plugin manifests, with a published
  flag), skills used (from session `Base directory for this skill:` markers),
  MCP servers integrated (from `mcp__<server>__` tool calls), and a
  conservative MCP-authoring flag. The enricher now appends a factual agentic-
  signals hint so bullets can foreground this Tier-1 agentic competency instead
  of collapsing it into a generic `agent-tooling %`. First of the competency-
  signal epic; shared `AgenticSignals` surface extended by later releases.

## [0.10.2] — 2026-05-29

### Fixed

- **`curate --apply` no longer drops same-named groups (data loss)** (#41).
  `apply_curation` keyed lookups by group name, so applying a `needs_decision`
  merge of a same-named twin sent both groups to the merge-source bucket and
  neither to survivors — silently deleting the kept project. It now pairs
  groups with entries positionally and resolves merge targets to a specific
  surviving group object (preferring the canonical-keyed anchor), so exactly
  one group survives carrying both groups' activities.
- **`load_groups` curated-cache lookup is now anchored to `GROUPS_PATH`** (#42).
  The curated path is derived via `GROUPS_PATH.with_name(...)` at call time
  instead of a standalone constant, so monkeypatching `GROUPS_PATH` redirects
  it too and the suite stays hermetic on machines with a real curated cache.

## [0.10.1] — 2026-05-29

### Fixed

- **Canonical-key merge no longer labels the merged project with a
  version/cache folder** (#39). Representative-path selection prefers a
  meaningful basename (not `0.2.0` / a plugin-cache path), then a work-tree
  toplevel, then the most-seen path; falls back to the repo basename from the
  git remote when every candidate leaf is meaningless. Since merging inflates
  the session count, the affected project is often the highest-ranked one.
- **`curate` `needs_decision` now fires for same-name/no-remote duplicates**
  (#40). The classifier self-excluded by name, which also dropped a same-named
  twin from the candidate set; it now self-excludes by identity and prefers a
  canonical-keyed sibling as the merge anchor, so a no-remote copy folds into
  the proven repo group instead of both being silently kept.

## [0.10.0] — 2026-05-29

### Added

- **`emphasis` lever** — `vibe-resume emphasis "<intent>"` writes an editable
  `_emphasis.yaml` (intent / keywords / bias_instruction / spotlight / demote)
  that re-shapes output to a chosen focus (#38). `enrich` injects it as the
  highest-priority bias block; `render` boosts `spotlight` groups into the
  detailed top-N and sinks `demote` groups to one-liners. Depth is implicit:
  re-run `render` for a light re-rank (no LLM) or `enrich` for a deep
  bias-rewrite. Hand-edited keywords/spotlight/demote carry forward when the
  intent changes; `--no-emphasis` / `emphasis --clear` disable it. New
  `emphasis:` config block. Completes #38 (the curate gate shipped in 0.9.0).

## [0.9.0] — 2026-05-29

### Added

- **`curate` gate** — a file-based human-in-the-loop checkpoint between
  `aggregate` and `enrich` (#38). `vibe-resume curate` writes an editable
  `_curation.yaml` classifying every project group into `auto_merge` /
  `auto_drop` / `needs_decision` / `keep` with evidence; `curate --apply`
  executes keep/merge_into/drop into a non-destructive
  `_project_groups.curated.json` that `enrich`/`render` prefer. Human
  decisions carry forward across re-runs (keyed by canonical identity);
  headless runs apply only the high-confidence auto tiers. New `curate:`
  config block (`enabled`, `noise_globs`).
- Merge **provenance** on `ProjectGroup` (`canonical_key` / `merged_from` /
  `merge_evidence`): the #37 cross-path auto-merge is now traceable in
  `_project_groups.json` instead of silently rewriting paths.

## [0.8.0] — 2026-05-29

### Changed

- **Same logical repo worked from multiple paths now collapses into one
  project group** (#37). Extractors capture each path's normalized git
  `origin` remote + work-tree toplevel (`git_remote` / `git_toplevel` in
  `Activity.extra`); the aggregator derives an identity-proven canonical
  key (remote → toplevel) and rewrites duplicate groups onto one
  representative path. Fixes double-counted projects from clones, renamed
  dirs, and sub-package working directories. Merges only on proven identity
  — unrelated same-named repos (different remote) stay separate.

### Added

- `extractors/base.py::git_identity(path, cache)` helper + `_normalize_remote`
  — shared, memoized git-remote/toplevel resolver (reused by the upcoming
  #38 curate gate).

## [0.7.0] — 2026-05-29

### Added

- **GitHub PR/issue extractor** (`extractors/local/github.py`, #34): pulls the
  author's PRs/issues + own review-thread comments via `gh` CLI (no token
  handling). Detects owned vs external (open-source) contributions; external
  merged PRs are exempt from the noise filter and framed as "contributed to".
  New `github:` config block (disabled by default).
- `sessions:` config block (`sample_prompts`, `per_prompt_chars`,
  `capture_tool_args`, `keep_assistant`) shared by conversation extractors.
- `enrich.input_activities` / `enrich.input_char_budget` config to widen the
  LLM input window (was hard-coded 12 activities / 200 chars).

### Changed

- git extractor now captures commit **bodies** (`%b`) and touched **file
  paths**, not just subjects (#35).
- claude_code / codex extractors spread-sample prompts across the session
  timeline (deduped) instead of keeping only the first ~8, and can keep a
  sample of tool-call arguments (#35).
- claude.ai export retains assistant responses (#35).

### Fixed

- `PrivacyFilter` now redacts string elements inside `list` values in
  `extra` (review comments / tool args), closing a redaction gap.

## [0.6.3] — 2026-05-28

### Fixed

- **#33: duplicate-named project groups collided on `enrich --ingest`.**
  Ingest matched each manifest entry's YAML back to a raw group **by name**,
  so two same-named groups (e.g. a git-only + a codex-only variant of one
  project) resolved to the same object — one group's enriched
  `summary`/`achievements` was silently overwritten (ended up `[]`). Ingest
  now matches by the manifest entry's **index** (`id`), which `emit_jobs`
  assigns over the raw group list — a stable, collision-free key. Added
  name-mismatch + index-out-of-range warnings to surface the "aggregate
  re-run since emit" divergent-set case instead of silently misattaching.
  `emit_jobs` status carry-forward is now keyed by `output_path` (unique)
  rather than name.

### Added / changed (render polish — #36)

- **Configurable detailed-project count.** `render --top-n N` /
  `config.render.detailed_projects` replaces the hardcoded `top_n = 6` in
  every locale template (was a hand-edit to produce a detailed résumé).
- **Composite project ranking.** Ordering now scores
  `sessions + achievements×5 + breadth×2` (descending) instead of favouring
  `capability_breadth`, so a focused high-session project is no longer
  buried under broad-but-shallow work.
- **ID-only CLI group names humanized.** Groups surfacing as `gemini:<hex>`
  now derive a readable name (path basename, or `<source> session <short>`)
  instead of leaking the session id as the project title.
- **Empty education/cert `year` no longer renders `()` / `（）`** — paren
  output is guarded across all locale templates (ASCII + full-width).

## [0.6.2] — 2026-05-28

### Fixed

- **#30 [P0 regression]: stale `templates_dir` crashed `render` after the
  0.6.0 src/ move.** `config.example.yaml` still shipped
  `render.templates_dir: "./render/templates"`, a path that no longer exists
  (templates moved into `src/vibe_resume/render/templates/`). Because
  `load_config` bootstraps `config.yaml` from the example, new users hit
  `TemplateNotFound` on their first `render`. Fix: removed the stale knob from
  the example, and `_render_md` now verifies a configured `templates_dir`
  actually contains templates — falling back to the bundled package templates
  with a warning instead of crashing. `render.templates_dir` is now an
  optional override; templates ship inside the package.

- **#31: `run --formats md,docx,pdf` exploded each format into its own
  version.** Phase B iterated formats as a matrix axis, so a 2-locale run
  produced 6 versions (each carrying only one format). `render_draft` now
  accepts a comma-list of formats and emits them all against ONE version;
  `run` Phase B makes a single render call per (locale, persona) cell.
  `render -f all` / `-f md` string forms still work.

- **#32: `trend` crashed (`TypeError: None < str`) on mixed persona history.**
  Default grouping is `(locale, persona)` since #15; `sorted()` couldn't
  order `None` (persona-less early runs) against `"agentic"` etc. Sort key is
  now None-safe (`persona or ""`); persona-less rows display as `(default)`.

## [0.6.1] — 2026-05-28

### Fixed (test infrastructure)

- **#27 regression guard never actually executed (#29).** The two
  console-script guards added in 0.5.1 invoked `uv run python -m vibe_resume`
  with `cwd=tmp_path`. `uv` walks up from the cwd for a `pyproject.toml`,
  finds none in a pytest temp dir, and falls back to an ad-hoc interpreter
  with no `vibe_resume` installed → `No module named vibe_resume` before any
  `ROOT`-resolution code runs. The guard proved nothing and was red/flaky
  depending on inherited shell env. Switched to `sys.executable -m
  vibe_resume`: the pytest interpreter has `vibe_resume`, `python -m`
  resolves it from `sys.path`, and `cwd=tmp_path` still exercises the
  CWD-based `ROOT` logic — which is the whole point. Confirmed the guard now
  *fails* if `user_root()` is reverted to install-dir resolution, so the #27
  regression finally has a guard with teeth.

  Product behaviour unchanged — this is a test-only fix; 0.6.0's shipped code
  was already correct.

## [0.6.0] — 2026-05-28

### Changed (packaging — #18 root cause)

- **Moved to a `src/vibe_resume/` single-package layout.** 0.5.x shipped
  `core` / `render` / `extractors` / `cli` as four **top-level** packages in
  the wheel — generic names that collide with other packages in any shared
  venv. The 0.5.0 `force-include cli.py` hack (#18) only made `uv tool
  install`'s *isolated* venv tolerate the pollution; it didn't fix the
  structure. Now everything lives under one `vibe_resume` top-level package,
  so a shared-venv `pip install vibe-resume` no longer squats on those names.
  This also makes the #27-class bug (top-level `cli.py` + `Path(__file__)`)
  structurally impossible.

  **Pure refactor — no behaviour change.** All 595 tests pass unchanged.

  **What this means for invocation:**
  - `uv run vibe-resume <cmd>` — **unchanged** (entry point still works)
  - `python -m vibe_resume <cmd>` — **new** module form
  - `python cli.py <cmd>` — **removed** (cli.py is no longer top-level);
    use one of the two forms above
  - Entry point is now `vibe_resume.cli:cli`; the `force-include` packaging
    hack is gone.

  Bundled templates + the 70 company-profile YAMLs moved with the package and
  still resolve package-relative; `core/paths.py::user_root()` (the 0.5.1 #27
  fix) still keeps user data (`data/`, `profile.yaml`, `config.yaml`) anchored
  to the working directory.

## [0.5.1] — 2026-05-28

### Fixed (P0 regression)

- **`ROOT` resolved to the install dir, not the user's working tree (#27).**
  0.5.0's wheel packaging (#18) put the package in `site-packages`, so the
  `vibe-resume` console script computed `ROOT = Path(__file__).parent` →
  `site-packages`, breaking every `ROOT / "data/..."` path. `doctor` and
  `review-diff` failed out of the box; `review`/`trend`/`run` were affected
  whenever invoked via the installed script from a normal CWD.

  **Root-cause fix (not a patch):** `ROOT` conflated two path domains —
  *user data* (`data/`, `profile.yaml`, `config.yaml`, which belong in the
  CWD like git) and *package resources* (bundled templates, company-profile
  YAML, the version string, which ship inside the install). New
  `core/paths.py::user_root()` is the single CWD-based source of truth
  (`VIBE_RESUME_ROOT` still overrides), replacing 7 duplicated
  `Path(__file__)` expressions. Bundled templates now resolve
  package-relative; `doctor` reads the version via `importlib.metadata`.
  A console-script-equivalent smoke test (runs the CLI from a foreign CWD)
  guards against recurrence — the one configuration 0.5.0's CI never
  exercised.

## [0.5.0] — 2026-05-28

Issue-driven release closing 25 issues filed against 0.4.0 (one declined).
No breaking changes — all additive or bug fixes.

### Fixed (P0)

- **review: persona+locale resolution (#2).** `review --persona X --locale Y`
  without `--file/--version` now globs `resume_v*_<locale>[_<persona>].md`
  and scores the highest matching version instead of silently scoring the
  lexically-latest file (which previously overwrote N−1 results in a batch).
- **review: DOB false positive (#3).** The "full DOB in header" red flag
  required only a bare ISO date in the first 14 lines, so summary /
  target-role / experience-start dates triggered a phantom −2 on every
  en_US/en_GB render. Now requires an explicit DOB / Date of birth / Born /
  生年月日 / 出生 label adjacent to the date. (The en_US template never
  rendered `profile.dob` — the bug was entirely in the reviewer's scanner.)
- **render: filename locale suffix (#4).** en_US renders dropped the locale
  suffix (`resume_v006_tech_lead.md`) while other locales kept it, breaking
  `resume_v*_en_US_*.md` globs. Every render now uses
  `resume_v<NNN>_<locale>[_<persona>].md` uniformly.

### Added

- **`vibe-resume run` orchestrator (#10).** One command for multi-persona ×
  multi-locale pipelines. Phase A: extract + aggregate (if cache stale) +
  enrich emit across the matrix, then stops for session processing. Phase B
  (`--continue`): ingest --all + render matrix + review matrix + trend.
  No auto-dispatch — preserves the session-quota model.
- **`vibe-resume jd-check` (#23).** Reports JD-keyword coverage across
  enriched bullets without a full render+review round. `--threshold` filters
  to under-covered keywords.
- **`vibe-resume review-diff <vA> <vB>` (#26).** Per-check scorecard delta
  between two résumé versions.
- **`vibe-resume doctor` (#19).** Diagnoses CLI/plugin version drift,
  profile/config presence, optional-dep (pandoc/claude) availability.
- **Agentic Engineer persona (#22).** `--persona agentic` — 2026 AI-agent
  narrative (agent loops, MCP, RAG triad, eval harness) with a Head-of-AI
  reviewer lens and keyword-echo-weighted scoring.
- **`enrich --tailor-keywords / --tailor-keywords-cap / --tailor-keywords-strict` (#7).**
  Manual keyword overrides; override terms always lead the merged set.
- **`enrich --ingest --all` (#9).** Walks every (persona, locale) under
  `data/enrich_jobs/` and ingests each; comma-separated persona ingest too.
- **`enrich --status` + `--ingest --all-ready` (#12).** Progress table across
  job dirs; batch-ingest only the complete ones.
- **`enrich --clean` (#20).** Clears stale `*.yaml` on re-emit; a warning
  fires when old yaml survives a re-emit without `--clean`.
- **`render --all-locales --persona X,Y,Z` matrix (#11).** Persona-list
  expansion across all locales.
- **`status --enriched / --pending / --all` (#25).** Cache-state views per
  (persona, locale) and pending job progress.
- **Profile-derived redaction (#24).** `derive_profile_redactors` auto-builds
  name/email patterns from `profile.yaml` (incl. locale name variants) and
  scrubs bullets at ingest, regardless of which invocation path ran.
- **Manifest JD provenance (#8).** Emit records the JD's sha256 + mtime +
  extracted keywords; ingest warns when the JD file changed since emit.
- **Persona-specific review weights (#16).** `review --persona` now reweights
  the 8-point scorecard (e.g. tech_lead weights metrics 1.5×, page-count
  0.7×) and normalises back to the same scale, not just appends a lens note.
- **Per-locale page-count targets + gradual scoring (#14).** ja_JP=1.0,
  de_DE/fr_FR=2.5, others=2.0; 4-band scoring (10/8/5/2) replaces the
  10→5 cliff.
- **Trend grouped by (locale, persona) (#15).** Default grouping splits
  apples-vs-oranges persona runs; `--group-by` + `--persona`/`--locale`
  filters.
- **render warns when `profile.summary` empty (#13)** — surfaces the −4
  top-fold penalty before it lands.
- **`uv tool install` support (#18).** Wheel now force-includes `cli.py` so
  `uv tool install git+…` puts `vibe-resume` on PATH. (No `src/` restructure —
  tracked separately if desired.)

### Docs

- SKILL.md documents the `--level` axis in the main Procedure + Quick
  Reference (#6); `personas-compare` quick-ref notes the `--locale`
  requirement since 0.4.0 (#5).
- New `references/tailor-keyword-extraction.md` explains the two-pass
  extractor + 12-keyword cap rationale (#21).

### Closed without code

- **#1** (list in awesome-codex-plugins) — declined; discovery is via
  skills.sh + Claude Code / Codex marketplaces.
- **#17** (plugin gitCommitSha drift) — upstream Claude Code behaviour, not
  a vibe-resume bug; workaround documented; the work-tree drift we *can*
  detect ships as `doctor` (#19).

## [0.4.0] — 2026-05-28

### Breaking changes

- **`enrich` default mode changed.** Was: spawn `claude -p` per group
  (billed against Anthropic Agent SDK quota pool as of 2026-06-15).
  Now: emit `*.prompt.md` files to `data/enrich_jobs/<persona>/<locale>/`
  for the current Claude Code session to process (uses subscription
  quota). Process the prompts in your session, then run
  `vibe-resume enrich --ingest --locale <L>` to merge the YAML back.
  CI / non-interactive: opt back into the old path with
  `--mode subprocess` (the CLI prints a red warning explaining the
  billing implication). Background:
  https://codersera.com/blog/anthropic-june-2026-billing-change-claude-code/

- **Enriched cache is now per-locale.** The cache file
  `_project_groups.<persona>.json` became
  `_project_groups.<persona-or-default>.<locale>.json`. This eliminates
  the previous hazard where `enrich --locale zh_TW` then
  `enrich --locale en_US` would overwrite each other.

  **Migration:**
  ```bash
  rm data/cache/_project_groups.*.json   # delete 0.3.x enriched caches
  uv run vibe-resume enrich --locale <L>  # re-run for each locale you need
  uv run vibe-resume enrich --ingest --locale <L>
  ```

- **`company verify` mirrored the same three-mode pattern.** Default
  emits prompt + manifest to `data/verification_jobs/<key>_<date>/`;
  session writes `report.md`; `verify --ingest <key>` finalises it.
  `--mode subprocess` keeps the old `claude -p` behaviour.

- **`personas-compare` now requires `--locale`** (cache is per-locale).

### Added

- `core/enrich_jobs.py` — `EnrichJobManifest` + `emit_jobs` + `ingest_jobs`
- `data/enrich_jobs/` and `data/verification_jobs/` working-directory
  layout (both gitignored)
- `tests/fixtures/enrich_jobs_sample/` — reference manifest + prompt + yaml
  so new contributors can see the schema shape (the live working dir is
  gitignored)
- New test suites: `test_enrich_jobs.py`, `test_per_locale_cache.py`,
  `test_cli_enrich_modes.py`, `test_company_verify_jobs.py`

### Verified

- No sensitive data ever entered git history (audit covered `profile.yaml`,
  `data/cache/*`, `data/resume_history/*`, `data/reviews/*`, secret
  patterns, credential file extensions). Historical `config.yaml` content
  was example-grade with no PII.

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
- **Shell completions** — `cli.py completion {bash,zsh,fish}` prints a
  completion snippet (or `--install` appends it to the right rc file
  with a sentinel-bracketed block so a re-run is idempotent). Makes
  `vibe-resume render --locale <tab>` expand across the 10 locales.
- **`zh_HK` locale** — Hong Kong bilingual CV. Section headings pair
  English + 繁體中文 ("Personal Profile 個人簡介" / "Work Experience
  工作經驗") so one document works for Cantonese- and English-speaking
  reviewers in one pass. Photo optional; HKID intentionally never
  emitted; CEFR-style language-proficiency section.
- **Windows backup** — `scripts/backup_claude_projects.ps1`
  (PowerShell 7, robocopy `/MIR /XO` mirror + dated snapshot) +
  `scripts/vibe-resume-backup.xml` Task Scheduler import template.
  The PS1 is smoke-testable via `pwsh -WhatIf` on macOS/Linux,
  statically checked by `PSScriptAnalyzer`, and exercised by a
  `windows-latest` matrix job in CI so a Windows box is not needed
  to maintain it.
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

- **More locales**: `en_SG` (NRIC-aware). *(`en_EU` and `zh_HK` done above.)*
- **`cli.py render --tailor` + review `--jd`** integrated into a single "target" object (one JD passed once, used everywhere).
- **PDF cover page**: optional one-page hero summary before the main resume (`render.cover_page: true`); useful for de_DE Lebenslauf + JP 履歴書 bundles.
- **Extractor hardening**: real-sample validation for Grok / Perplexity / Mistral / Poe cloud exports — schemas are currently lenient-parsed.
- **JP 履歴書 legacy cells**: optional 通勤時間 / 扶養家族 / 配偶者 cells (some traditional employers still expect these).
- **Prompt coverage**: verify ko_KR / zh_CN LLM output end-to-end (same way we verified zh_TW/ja_JP/de_DE/fr_FR in 0.1).

## [0.3.0] — 2026-04-22

Three new native CLI-session extractors + Codex plugin marketplace
distribution. Published fresh tarball so `npx skills add …` and
`skills.sh` registries pick up the new extractors and corrected install
instructions.

### Added

- **Codex CLI extractor** (`extractors/local/codex.py`) — reads
  `~/.codex/sessions/**/rollout-*.jsonl` **and**
  `~/.codex/archived_sessions/*.jsonl`. Session-UUID dedup across the
  two trees. Emits one `Activity` per session with `cwd`, `git.branch`,
  `cli_version`, user-prompt count, function-call count, file paths.
  Registered as `Source.CODEX`. 5 unit tests.
- **Gemini CLI extractor** (`extractors/local/gemini_cli.py`) — reads
  `~/.gemini/tmp/<project_hash>/chats/session-*.json` (rich) **and**
  `~/.gemini/tmp/<project_hash>/logs.json` (fallback). Session-ID
  dedup across the two shapes; skips `bin/` helper dir and malformed
  JSON silently. Registered as `Source.GEMINI_CLI`. 3 unit tests.
- **Copilot CLI extractor** (`extractors/local/copilot_cli.py`) — reads
  `~/.copilot/session-state/<uuid>/events.jsonl`. Parses
  `session.start` (sessionId, cwd, copilotVersion, producer),
  `user.message`, `assistant.message` with `toolRequests` (tool-call
  count + file-path extraction), `session.shutdown`. Registered as
  `Source.COPILOT_CLI`. Separate from `copilot_vscode`. 3 unit tests.
- **Claude Code plugin marketplace** —
  `.claude-plugin/marketplace.json` lets users run
  `/plugin marketplace add easyvibecoding/vibe-resume` and install
  via the standard two-step flow.
- **OpenAI Codex plugin marketplace** —
  `.codex-plugin/marketplace.json` mirrors the Claude Code pattern
  so `codex plugin marketplace add easyvibecoding/vibe-resume` works
  on codex-cli ≥ 0.121.0.
- **Codex plugin `interface` object** in `.codex-plugin/plugin.json`
  (displayName, shortDescription, longDescription, capabilities,
  URLs, defaultPrompt × 3, brandColor) so the marketplace listing
  renders a full card, not a placeholder.
- **`scripts/validate_plugin_e2e.sh`** — JSON parse → shared manifest
  invariants → Codex publish-readiness → marketplace installability
  → `claude plugin validate` in one pass.
- `test_codex_plugin_manifest_publish_readiness` and
  `test_marketplace_manifests_installable` guard both marketplace
  manifests and the Codex interface schema.

### Changed

- READMEs (en / zh-TW / zh-CN / ja) Tier 0 section: replaced the
  invalid `/plugin install <owner>/<repo>` shorthand with the correct
  two-step flow, and added the codex-cli ≥ 0.121 version floor with
  a Tier 1 fallback pointer for older installs.
- `core/runner.py::LOCAL_EXTRACTORS` grew to 14 entries
  (`codex`, `gemini_cli`, `copilot_cli` added).
- `config.example.yaml` gained `codex` (with `archived_path`),
  `gemini_cli`, and `copilot_cli` stanzas.

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
