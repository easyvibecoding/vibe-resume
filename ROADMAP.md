# Roadmap

Living doc. PRs welcome against any unchecked item.

## ✅ Landed

### v0.2.0 — 2026-04-21

- **Unified canonical skill** at `skills/ai-used-resume/` + 4 one-hop symlinks (`.claude/skills/`, `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/`)
- **Progressive-disclosure references** (`strategic-resume.md`, `troubleshooting.md`, `extending.md`)
- **Plugin-layer marketplace support**: `.claude-plugin/plugin.json` + `.codex-plugin/plugin.json`
- **`VIBE_RESUME_ROOT` env var** across 6 modules — clean sandboxed e2e testing
- **Test coverage**: `test_skill_spec.py` (14 spec assertions) + `test_cli_e2e.py` (9 CLI smoke tests); 472 → 495 tests
- Enricher wrapped untrusted activity in tagged boundary against prompt-injection
- 4 READMEs synced (en / zh-TW / zh-CN / ja) with 4-tier install section and 37-host adoption list

### Post-0.2.0

- **Codex extractor** (`extractors/local/codex.py`) — reads `~/.codex/sessions/**/rollout-*.jsonl`; emits one `Activity` per session with `cwd`, `git.branch`, `cli_version`, user-prompt count, function-call count, file paths. Registered as `Source.CODEX`. 3 unit tests (happy path, missing path, malformed lines).

## 🚧 Up next (short list)

- [ ] **Description trigger refresh** — the `ai-used-resume` SKILL.md frontmatter description still enumerates "Codex" in the cloud-export sense (ChatGPT/Codex cloud cut). Explicitly add **"Codex CLI sessions at `~/.codex/sessions/`"** as a trigger so skill-selection picks us up for Codex-user prompts.
- [ ] **iter-1 skill eval follow-through** — benchmark found 2 baseline failures worth defending against regressions in the main SKILL.md body:
  - Add explicit "canonical subcommand list; do not invent others" line to Procedure
  - Add `review --jd <path>` reminder in Quick Reference (baseline forgot the flag)
- [ ] **`skills-ref validate` in CI** — currently we validate frontmatter with our own `test_skill_spec.py` (14 checks). The upstream `skills-ref validate` CLI from agentskills.io catches a superset; evaluate adding it as a CI job (Go binary; small extra runtime).
- [ ] **Cleanup `data/resume_history/.git`** — internal git accumulated test-only commits during e2e development. One-time `git reset --hard` back to a clean baseline, then rely on VIBE_RESUME_ROOT-isolated tests going forward (no more pollution).

## 💭 Brainstorm — Chronicle family & session-memory crossover (2026-04)

The Chronicle ecosystem sits adjacent to vibe-resume: **same data source (AI coding sessions), different output shape (persistent memory vs résumé artefact)**. We consume the same JSONL transcripts; they synthesise context for future sessions; we synthesise evidence for hiring.

Interesting integrations if the fit is right:

- [ ] **OpenAI Chronicle Markdown files as a source** — Chronicle (OpenAI's, launched 2026-04-20) distills screen captures into per-day Markdown memory under `~/.codex/chronicle/` (path TBC; opt-in, Pro-only, macOS). If we can parse these, we gain cross-tool context the JSONL files miss (e.g., time spent reading Figma, reviewing PRs in browser). New extractor: `extractors/local/chronicle_openai.py`.
- [ ] **Community `chronicle` (ChandlerHardy/chronicle) compatibility** — Dev session recorder with multi-AI + git integration. Author deprecated it in favour of the `episodic-memory` skill (agentskills.io); watch for their migration path and consider reading the resulting memory format. (Project archived; extractor not urgent.)
- [ ] **`claude-mem` plugin interop** — auto-captured Claude Code session memory + context injection. If the on-disk format is stable, a `claude_mem` extractor could be a light wrapper around our existing `claude_code` extractor with memory-aware summaries.
- [ ] **Reverse direction: emit memory files FROM vibe-resume** — We have rich per-project achievement summaries post-`enrich`. A small adapter could write them to Chronicle-compatible Markdown files so Codex/Claude Code sessions *start* knowing your project highlights. Would close the loop: session history → enrich → memory → informs future sessions.
- [ ] **Episodic-memory skill contract** — Once the agentskills.io episodic-memory skill stabilises, evaluate publishing alongside `ai-used-resume` as a sibling skill that consumes the same `data/cache/_project_groups.json` but outputs agent-memory shape instead of résumé markdown.

### Design questions to answer before implementing

1. **Privacy boundary**: Chronicle captures screenshots of arbitrary content (financial apps, secrets). If we extract FROM Chronicle files, do we need a stricter `privacy.blocklist` that operates on Chronicle's output categories (app name, domain) rather than just project names?
2. **Deduplication**: Chronicle summarises sessions that ALSO appear in `~/.codex/sessions/**/rollout-*.jsonl`. Extracting both would double-count. Need a "prefer most specific source" rule — probably Chronicle summary wins when both exist (it's already condensed), else fall back to raw transcript.
3. **Platform scope**: Chronicle is macOS-only (OpenAI's) or cross-platform (community versions). `config.yaml::extractors.chronicle_openai.enabled` defaults to `false` on non-macOS to avoid noise.

## Sources / references

- [OpenAI Chronicle announcement (Help Net Security, 2026-04-21)](https://www.helpnetsecurity.com/2026/04/21/openai-chronicle-codex-screen-context-memories/)
- [OpenAI Codex CLI session format](https://developers.openai.com/codex/cli/features)
- [ChandlerHardy/chronicle (GitHub, archived)](https://github.com/ChandlerHardy/chronicle)
- [claude-mem plugin](https://aitoolly.com/ai-news/article/2026-04-15-claude-mem-a-new-claude-code-plugin-for-automated-session-memory-and-context-injection)
- [agentskills.io](https://agentskills.io/specification)
