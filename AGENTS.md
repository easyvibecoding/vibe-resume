# Agent Skill — vibe-resume

This repository ships an [Agent Skill](.claude/skills/ai-used-resume/SKILL.md)
that drives the full `extract → aggregate → enrich → render → review → trend`
pipeline for an agentic coding CLI. In 2026 the `SKILL.md` format has become
an industry convention — so a single canonical file works across every host
below with zero content duplication.

## Canonical skill file

[`.claude/skills/ai-used-resume/SKILL.md`](.claude/skills/ai-used-resume/SKILL.md)

This file has the frontmatter-typed `name` and `description` that hosts use to
decide when to lazy-load the skill. The body walks the LLM through every step
of the résumé pipeline, the 10-locale cheat sheet, and an end-to-end
"one JD, every market" example. Advanced content is bundled under
[`.claude/skills/ai-used-resume/references/`](.claude/skills/ai-used-resume/references/)
and loaded progressively — currently `strategic-resume.md` (company /
level axis) and `troubleshooting.md` (failure-mode playbook) — per the
[agentskills.io](https://agentskills.io/specification) progressive-disclosure pattern.

## Host discovery matrix

| Host | Discovery path | Our setup |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | Canonical location — auto-loaded |
| **Gemini CLI** (Google) | `.gemini/skills/<name>/SKILL.md` | Symlink → canonical |
| **GitHub Copilot CLI** | reads `.claude/skills/` natively (per 2026-04 changelog) | Zero config |
| **Cursor CLI** | reads `AGENTS.md` + `.cursor/rules/` | This file points at SKILL.md |
| **Warp** (agentic terminal) | reads `.claude/skills/` + `.agents/skills/` + `.warp/skills/` | Zero config; extra `.agents/skills/` symlink added defensively |
| **OpenClaw** (Nov 2025 → 250k ⭐ Feb 2026) | `~/.openclaw/skills/<name>/SKILL.md` (user scope only) | User-scope symlink — see below |
| **OpenCode** (CLI agent) | `.opencode/skills/<name>/` (project) + `~/.opencode/skills/` (user) | Project-scope symlink included; user-scope optional |
| **Hermes Agent** (Nous Research) | repo layout `<repo>/skills/<name>/SKILL.md`; installed to `~/.hermes/skills/<category>/<name>/` (body = *When to Use / Quick Reference / Procedure / Pitfalls / Verification*) | Native skill at [`skills/ai-used-resume/SKILL.md`](skills/ai-used-resume/SKILL.md); `hermes skills tap add easyvibecoding/vibe-resume && hermes skills install easyvibecoding/vibe-resume/ai-used-resume` — indexed on [skills.sh](https://skills.sh/easyvibecoding/vibe-resume/ai-used-resume) |

All four of the first five hosts receive the same SKILL.md content with zero drift because everything ultimately resolves to `.claude/skills/ai-used-resume/`.

## For the agent reading this file

If the user is asking about generating, rendering, tailoring, reviewing, or
trending their résumé — open [`.claude/skills/ai-used-resume/SKILL.md`](.claude/skills/ai-used-resume/SKILL.md)
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

**Tier 1 — 35+ `agentskills.io`-standard hosts** (Claude Code, Cursor,
Windsurf, Gemini CLI, GitHub Copilot, Codex, Qwen, Kimi, Roo, Kilo, Goose,
Trae, OpenCode, Amp, Antigravity, Kiro, Factory, Junie, Letta, Mux,
Emdash, Workshop, Laravel Boost, Spring AI, …):
```bash
npx skills add easyvibecoding/vibe-resume --skill ai-used-resume
```

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

- **Single source of truth** — edit `.claude/skills/ai-used-resume/SKILL.md`
  and every host sees the change. No CI, no codegen, no duplicate reviews.
- **Lazy load** — the `description` frontmatter is what each host matches
  against the user's prompt. The body is only pulled into context when
  the skill actually fires, so vibe-resume doesn't bloat every session.
- **Distribution** — once a host marketplace (ClawHub, GitHub Copilot skill
  registry) accepts a skill entry, we can point it at this repo's canonical
  file. Again, no duplication.
