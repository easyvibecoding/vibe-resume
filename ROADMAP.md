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

- **Codex extractor** (`extractors/local/codex.py`) — reads `~/.codex/sessions/**/rollout-*.jsonl` AND `~/.codex/archived_sessions/*.jsonl`; emits one `Activity` per session with `cwd`, `git.branch`, `cli_version`, user-prompt count, function-call count, file paths. Session-UUID dedup across the two trees. Registered as `Source.CODEX`. 5 unit tests. Live sanity on the author's machine: 65 sessions (50 active + 15 archived).
- **Gemini CLI extractor** (`extractors/local/gemini_cli.py`) — reads `~/.gemini/tmp/<project_hash>/chats/session-*.json` (rich) AND `~/.gemini/tmp/<project_hash>/logs.json` (fallback). Session-ID dedup across the two shapes; skips `bin/` helper dir and malformed JSON silently. Registered as `Source.GEMINI_CLI`. 3 unit tests. Live sanity: 61 sessions (9 chats + 52 logs-only) across 19 project-hash dirs.
- **Copilot CLI extractor** (`extractors/local/copilot_cli.py`) — reads `~/.copilot/session-state/<uuid>/events.jsonl`. Event stream carries `session.start` (sessionId, cwd, copilotVersion, producer), `user.message`, `assistant.message` with `toolRequests` (tool-call count + file-path extraction), `session.shutdown`. Registered as `Source.COPILOT_CLI`. 3 unit tests. This is a separate extractor from `copilot_vscode` (parses the Copilot Chat VS Code extension's per-workspace sessions); same parent product, different storage layout.

## 🚧 Up next (short list)

- [ ] **Description trigger refresh** — the `ai-used-resume` SKILL.md frontmatter description still enumerates "Codex" in the cloud-export sense. Now that we have native extractors, add **"Codex CLI sessions (`~/.codex/sessions/`, archived too) + Gemini CLI sessions (`~/.gemini/tmp/`)"** as explicit triggers so skill-selection picks us up for those tools' users.
- [ ] **Antigravity `.pb` conversations extractor** — Antigravity IDE shares `~/.gemini/` with Gemini CLI but stores conversations at `~/.gemini/antigravity/conversations/*.pb` (binary protobuf, 23 files on author's machine) and annotations as `.pbtxt` (text protobuf). Blocked on obtaining the `.proto` schema — options: (a) reverse-engineer from [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) source, (b) probe the binary with `protoc --decode_raw` and reconstruct message types, (c) wait for Google to publish the schema. Code tracker (`~/.gemini/antigravity/code_tracker/active/<project>/<hash>_<filename>`) is already JSON-parseable and carries real repo names like `air-chiuchau_104a4bfd...` — could be a lighter first pass that emits one Activity per touched file even before .pb is solved.
- [ ] **Remaining Copilot variants** — we cover `copilot_vscode` (VS Code extension chat sessions) and `copilot_cli` (GitHub Copilot CLI). Still to explore:
  - **Copilot Chat in JetBrains / IntelliJ** — stored under `~/Library/Caches/JetBrains/<IDE>/copilot/` or similar per-IDE path (investigate).
  - **Copilot in Xcode** (macOS only) — new in 2026; probably `~/Library/Application Support/com.apple.dt.Xcode/Copilot/` or plugin-level storage.
  - **Copilot Workspace** — web-only; no local files (out of scope unless we parse browser IndexedDB).
  - **Copilot in Zed** — confirmed `~/Library/Application Support/Zed/copilot/` holds only the LSP binary + tokenizer assets, no session data. Zed's chat is covered by `zed_ai` extractor (separate code path).
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
