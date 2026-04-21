# Agent Skill — vibe-resume

This repository ships an [Agent Skill](skills/ai-used-resume/SKILL.md)
that drives the full `extract → aggregate → enrich → render → review → trend`
pipeline for an agentic coding CLI. In 2026 the `SKILL.md` format has become
an industry convention — so a single canonical file works across every host
below with zero content duplication.

## Canonical skill file

[`skills/ai-used-resume/SKILL.md`](skills/ai-used-resume/SKILL.md)

This file has the frontmatter-typed `name` and `description` that hosts use to
decide when to lazy-load the skill. The body follows the Hermes 5-section
convention (*When to Use / Quick Reference / Procedure / Pitfalls /
Verification*) — recognised by Anthropic's skill-authoring best practices
and natively understood by every host below. Advanced content is bundled
under [`skills/ai-used-resume/references/`](skills/ai-used-resume/references/)
and loaded progressively — `strategic-resume.md` (company / level axis),
`troubleshooting.md` (failure-mode playbook), and `extending.md` (Activity
schema + extractor registration) — per the
[agentskills.io](https://agentskills.io/specification) spec.

Every other host path (`.claude/skills/`, `.gemini/skills/`, `.agents/skills/`,
`.opencode/skills/`) is a relative symlink pointing at this canonical
directory. Editing the canonical updates every host in one pass, zero drift.

## Plugin-layer manifests (2026 marketplaces)

This repo also ships two plugin manifests so users can install via the
Claude Code and OpenAI Codex marketplaces:

- [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) — Claude Code plugin spec
- [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) — OpenAI Codex plugin spec

Both auto-discover the bundled skill at `skills/ai-used-resume/`.

## Host discovery matrix

| Host | Discovery path | Our setup |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | `../../skills/ai-used-resume` symlink. Plugin-layer install via `/plugin install easyvibecoding/vibe-resume` (uses `.claude-plugin/plugin.json`) |
| **Gemini CLI** (Google) | `.gemini/skills/<name>/SKILL.md` | `../../skills/ai-used-resume` symlink |
| **GitHub Copilot CLI** | reads `.claude/skills/` natively (per 2026-04 changelog) | Zero config — follows the Claude symlink |
| **Cursor CLI** | reads `AGENTS.md` + `.cursor/rules/` | This file points at canonical SKILL.md |
| **Warp** (agentic terminal) | reads `.claude/skills/` + `.agents/skills/` + `.warp/skills/` | Zero config; both symlinks resolve to canonical |
| **OpenAI Codex** (CLI, app, IDE ext) | `.agents/skills/<name>/SKILL.md` (repo) + `.codex-plugin/plugin.json` for plugin-level | `.agents/skills/ai-used-resume` symlink ✓; `.codex-plugin/plugin.json` shipped ✓ — full plugin install supported |
| **OpenClaw** (Nov 2025 → 250k ⭐ Feb 2026) | `~/.openclaw/skills/<name>/SKILL.md` (user scope only) | User-scope symlink — see below |
| **OpenCode** (CLI agent) | `.opencode/skills/<name>/` (project) + `~/.opencode/skills/` (user) | `../../skills/ai-used-resume` symlink at project scope; user-scope optional |
| **Hermes Agent** (Nous Research) | repo layout `<repo>/skills/<name>/SKILL.md` — this IS our canonical path; installed to `~/.hermes/skills/<category>/<name>/`; 5-section body is native | Canonical location. Install via `hermes skills tap add easyvibecoding/vibe-resume && hermes skills install easyvibecoding/vibe-resume/ai-used-resume` — indexed on [skills.sh](https://skills.sh/easyvibecoding/vibe-resume/ai-used-resume) |

All hosts receive byte-identical SKILL.md content because every path resolves (directly or via symlink) to `skills/ai-used-resume/`.

## For the agent reading this file

If the user is asking about generating, rendering, tailoring, reviewing, or
trending their résumé — open [`skills/ai-used-resume/SKILL.md`](skills/ai-used-resume/SKILL.md)
and follow its workflow. The CLI binary is `vibe-resume` (installed via
`uv pip install -e ".[dev]"`); the same commands also work as
`uv run python cli.py <command>`.

## For the human reading this file

See the main [README](README.md) (or [繁體中文](README.zh-TW.md) /
[简体中文](README.zh-CN.md) / [日本語](README.ja.md)) for setup and usage.

### Install system-wide

Project-scope paths only fire when the agent runs inside this clone. To make
the skill's trigger phrases available anywhere, use whichever installer matches
your agent's ecosystem:

**Tier 1 — `agentskills.io`-standard hosts** (37 confirmed as of 2026-04,
snapshot below):

```bash
npx skills add easyvibecoding/vibe-resume --skill ai-used-resume
```

<details>
<summary>Full list (37 hosts from the agentskills.io adoption carousel)</summary>

| # | Host | Type |
|---|---|---|
| 1 | Claude Code | Anthropic terminal/IDE agent |
| 2 | Claude (claude.ai) | Anthropic web |
| 3 | Cursor | AI IDE + coding agent |
| 4 | GitHub Copilot | IDE assistant |
| 5 | VS Code | Editor agent integration |
| 6 | Gemini CLI | Google terminal agent |
| 7 | OpenAI Codex | OpenAI coding agent |
| 8 | OpenHands | Open cloud agents platform |
| 9 | OpenCode | Terminal/IDE/desktop agent |
| 10 | Goose | Block, extensible agent |
| 11 | Amp | Frontier coding agent |
| 12 | Kiro | Spec-driven development |
| 13 | Factory | Multi-surface dev platform |
| 14 | Junie | JetBrains IntelliJ-native agent |
| 15 | Letta | Stateful agents w/ memory |
| 16 | Mux | Parallel coding agents |
| 17 | Emdash | Desktop parallel agents |
| 18 | Workshop | Multi-LLM app builder |
| 19 | Piebald | Desktop + web agent |
| 20 | Firebender | Android-native agent |
| 21 | Roo Code | Editor AI dev team |
| 22 | TRAE | Adaptive AI IDE (ByteDance) |
| 23 | Autohand Code CLI | Autonomous ReAct agent |
| 24 | pi | Minimal terminal harness |
| 25 | VT Code | Open-source coding agent |
| 26 | Command Code | Taste-learning agent |
| 27 | Qodo | Code-integrity platform |
| 28 | Ona | Background agent orchestrator |
| 29 | Agentman | Healthcare revenue-cycle agent |
| 30 | Databricks Genie Code | Databricks data agent |
| 31 | Snowflake Cortex Code | Snowflake data agent |
| 32 | Spring AI | Java AI framework |
| 33 | Laravel Boost | Laravel-specific skills |
| 34 | Mistral AI Vibe | Mistral terminal agent |
| 35 | Google AI Edge Gallery | On-device LLMs |
| 36 | nanobot | Multi-platform personal agent |
| 37 | fast-agent | Skills-dev framework |

</details>

Beyond this open-standard group, this repo's manual-install tier-1 table
(the "Host discovery matrix" above) covers 7 specific hosts where we've
wired up explicit discovery paths and symlinks.

**Tier 2 — OpenClaw** (own ClawHub marketplace):
```bash
openclaw skills install easyvibecoding/vibe-resume/ai-used-resume
```

**Tier 3 — Hermes Agent** (own skills.sh registry + 5-section body):
```bash
hermes skills tap add easyvibecoding/vibe-resume
hermes skills install easyvibecoding/vibe-resume/ai-used-resume --force --yes
```

See the [main README](README.md) § *Install — three ecosystem tiers* for the
full 27-agent slug table, per-host behaviour notes, and manual symlink fallback
(Windows, no-Node environments).

### Why one skill, many hosts

- **Single source of truth** — edit `skills/ai-used-resume/SKILL.md`
  and every host sees the change(`.claude/skills/` and the other agent
  directories are symlinks to it). No CI, no codegen, no duplicate reviews.
- **Lazy load** — the `description` frontmatter is what each host matches
  against the user's prompt. The body is only pulled into context when
  the skill actually fires, so vibe-resume doesn't bloat every session.
- **Distribution** — once a host marketplace (ClawHub, GitHub Copilot skill
  registry) accepts a skill entry, we can point it at this repo's canonical
  file. Again, no duplication.
