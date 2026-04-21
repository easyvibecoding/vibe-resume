# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

```bash
uv venv && uv pip install -e ".[dev]"   # one-time setup (installs `vibe-resume` entry point)

uv run vibe-resume <subcommand>         # canonical invocation (post-install)
uv run python cli.py <subcommand>       # equivalent pre-install path used in tests/docs

uv run pytest tests/                    # full suite (currently 50 tests)
uv run pytest tests/test_review.py      # single file
uv run pytest tests/test_extractors.py::test_cursor_happy_path   # single test

uv run ruff check .                     # lint
uv run ruff check --fix .               # autofix import order, trivial issues
```

No separate build step — the project is a pure-Python CLI. `pandoc` is an
optional system dep (PDF rendering only); `claude -p` is an optional binary
(enricher LLM path; falls back to rule-based summaries when absent).

## Pipeline architecture

The CLI orchestrates a six-stage pipeline. Each stage writes to `data/cache/`
or `data/resume_history/` so later stages can re-run independently:

```
extract → aggregate → enrich → render → review → trend
```

- **`extract`** (`core/runner.py::run_extractors`) — drives all extractors via
  `ThreadPoolExecutor(max_workers=4)` with a `rich.progress` display. Each
  extractor returns `list[Activity]` (schema in `core/schema.py`) which is
  serialized to `data/cache/<name>.json`. Failure of one extractor is isolated
  and does not abort the batch. `git_repos` has a 120s wall-clock deadline
  inside `_find_repos` to survive FUSE/broken-symlink stalls.

- **`aggregate`** (`core/aggregator.py`) — groups activities by project and
  writes `data/cache/_project_groups.json` + `_window_stats.json`. Project
  names are abstracted when `config.privacy.abstract_tech: true`.

- **`enrich`** (`core/enricher.py`) — feeds each group through a locale-shaped
  LLM prompt (XYZ verbs for `en_*`, noun-phrase for `zh_*`/`ja_JP`/`ko_KR`/
  `de_DE`/`fr_FR`). `--tailor <JD.txt>` injects extracted keywords so
  achievements bias toward the JD *when the raw activity supports it* (never
  inventing matches). Output: per-group `bullets`, `role_label`, `summary`
  written back into `_project_groups.json`.

- **`render`** (`render/renderer.py`) — merges `profile.yaml` + enriched
  groups into a Jinja2 template `render/templates/resume.<locale>.md.j2`,
  writes `data/resume_history/resume_v{NNN}_{locale}.{ext}`, and **commits
  to an internal git repo** at `data/resume_history/` for versioning.
  DOCX for `ja_JP` uses a specialized path (`render/japan.py`) that emits the
  JIS Z 8303 履歴書 grid form rather than going through pandoc.

- **`review`** (`core/review.py`) — scores a rendered resume against the
  8-point checklist (top-fold, numbers-per-bullet, keyword-echo,
  action-verb-first, density, locale-aware red-flags, contact-line width,
  page-count estimate). Writes `data/reviews/{version}_{locale}.{md,json}`.
  Bar is grade B / 80%.

- **`trend`** — reads `data/reviews/*.json` and renders per-locale ASCII
  sparklines of the score history.

### Locale resolution chain

Both `enrich` and `render` resolve the active locale in this order:

1. CLI `--locale`
2. `profile.yaml::preferred_locale`
3. `config.yaml::render.locale`
4. `en_US` fallback

Locales are registered in `render/i18n.py::LOCALES`. Adding one requires:
the registry entry, a new `render/templates/resume.<locale>.md.j2`, and —
if the review pitfalls (e.g. contact-line width) apply — a template tweak.

## Key contracts

- **`Activity` schema** (`core/schema.py`) — every extractor returns a list of
  these. Adding a new extractor means implementing `extract(cfg) -> list[Activity]`,
  reading its path from `cfg["extractors"][NAME]["path"]`, and **registering
  its module name in `core/runner.py::LOCAL_EXTRACTORS` / `CLOUD_EXTRACTORS` /
  `AIGC_EXTRACTORS`**. Extractors never invent activities — if their source
  is missing, return `[]` silently.

- **User files are gitignored** — both `profile.yaml` (contains real PII) and
  `config.yaml` (contains user-specific `scan.roots`) are in `.gitignore`.
  The committed templates are `profile.example.yaml` and `config.example.yaml`;
  `core/config.py::load_config` auto-bootstraps `config.yaml` from the example
  on first run. Never stage either file.

## Agent-Skill duality

This repo **is** an installable Agent Skill + Plugin in addition to being
a CLI tool.

**Canonical skill**: `skills/ai-used-resume/SKILL.md`. Body follows the
Hermes 5-section convention (When to Use / Quick Reference / Procedure /
Pitfalls / Verification) — compatible with every agentskills.io host per
Anthropic's own skill best-practice guide. Advanced content lives under
`skills/ai-used-resume/references/` (one-level-deep per spec):
`strategic-resume.md`, `troubleshooting.md`, `extending.md`.

**Host discovery paths are symlinks** to the canonical:

- `.claude/skills/ai-used-resume` → `../../skills/ai-used-resume` (Claude Code, Copilot CLI, Warp)
- `.gemini/skills/ai-used-resume` → same (Gemini CLI)
- `.agents/skills/ai-used-resume` → same (OpenAI Codex + Warp)
- `.opencode/skills/ai-used-resume` → same (OpenCode)

**Plugin-layer manifests** for marketplace distribution:

- `.claude-plugin/plugin.json` — Claude Code plugin spec
- `.codex-plugin/plugin.json` — OpenAI Codex plugin spec

Both point at the canonical skills/ directory, so plugin-installed users
get the same SKILL.md as symlink-discovery users.

Frontmatter compliance, plugin-manifest consistency, symlink integrity,
and reference-link correctness are guarded by `tests/test_skill_spec.py`
(14 assertions).

When updating workflow documentation, edit the canonical SKILL.md at
`skills/ai-used-resume/` — every symlinked host sees the change
immediately. Also update `AGENTS.md` (Cursor CLI reads it natively) and
the two `plugin.json` manifests if you bump the plugin version. The
`docs/samples/` gallery (linked from README §Multi-locale rendering) is
hand-crafted illustrative output — do **not** regenerate from the
user's real profile.

## CI & safety notes

- GitHub Actions matrix: Ubuntu × macOS × Python 3.12 / 3.13 + a
  `windows-latest` job that lints PowerShell scripts with PSScriptAnalyzer.
- `data/imports/` is gitignored **except** for `sample_jd.txt` — real job
  descriptions live there and must never be committed.
- `scripts/com.vibe-resume.backup.plist` uses `$HOME` placeholders and must
  not leak a real user directory layout.
