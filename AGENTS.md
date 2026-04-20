# Agent Skill — vibe-resume

This repository ships an [Agent Skill](.claude/skills/ai-used-resume/SKILL.md)
that drives the full `extract → aggregate → enrich → render → review → trend`
pipeline for an agentic coding CLI. Any host that implements the 2026
"SKILL.md" convention can load it.

## Canonical skill file

[`.claude/skills/ai-used-resume/SKILL.md`](.claude/skills/ai-used-resume/SKILL.md)

This file has the frontmatter-typed `name` and `description` that hosts use to
decide when to lazy-load the skill. The body walks the LLM through every step
of the résumé pipeline, the 10-locale cheat sheet, a playbook for common user
requests, and an end-to-end "one JD, every market" example.

## Host discovery

| Host | Discovery path | Notes |
|---|---|---|
| Claude Code | [`.claude/skills/ai-used-resume/`](.claude/skills/ai-used-resume/) | Native location; auto-loaded when description matches user prompt. |
| Gemini CLI | [`.gemini/skills/ai-used-resume/`](.gemini/skills/ai-used-resume) | Symlinked to `.claude/skills/ai-used-resume/`. Single source of truth. |
| GitHub Copilot CLI | `.claude/skills/` is read natively. | No extra action needed. |
| Cursor CLI | Reads this `AGENTS.md` and applies it alongside `.cursor/rules/`. | The full skill instructions are in the linked SKILL.md — agents should fetch it when the user asks about résumé generation. |

## For the agent reading this file

If the user is asking about generating, rendering, tailoring, reviewing, or
trending their résumé — open [`.claude/skills/ai-used-resume/SKILL.md`](.claude/skills/ai-used-resume/SKILL.md)
and follow its workflow. The CLI binary is `vibe-resume` (installed via
`uv pip install -e ".[dev]"`); the same commands also work as
`uv run python cli.py <command>`.

## For the human reading this file

See the main [README](README.md) (or [繁體中文](README.zh-TW.md) /
[简体中文](README.zh-CN.md) / [日本語](README.ja.md)) for setup and usage.
To activate the skill system-wide in Claude Code, symlink the skill folder
to your user-level skills directory:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.claude/skills/ai-used-resume
# for Gemini CLI:
mkdir -p ~/.gemini/skills
ln -s "$(pwd)/.claude/skills/ai-used-resume" ~/.gemini/skills/ai-used-resume
```

Windows users: use `New-Item -ItemType SymbolicLink -Path <target> -Value <source>` in
an elevated PowerShell, or copy the folder instead of symlinking.
