---
name: ai-used-resume
description: Extract AI tool usage history (Claude Code, Cursor, Copilot, ChatGPT/Claude.ai/Gemini exports, ComfyUI, git commits, ElevenLabs, etc.) from the user's macOS and synthesize a versioned resume in Markdown/DOCX/PDF. Triggers when the user asks to "generate my resume from AI usage", "list my AI work history", or "render my resume".
---

# AI-Used Resume

You are operating inside the `AI-used-resume` project (path depends on where the user cloned it; use the current working directory). This skill walks the user through extracting their AI tool traces and producing a polished, versioned resume.

## Standard workflow

1. **Check `profile.yaml`**. If it's still the example text, ask the user to fill in name, email, target_role, and optional sections (experience, education, custom_sections). Don't proceed until the name is real.

2. **Review `config.yaml`**. Confirm with the user:
   - `scan.mode` — `full` scans `$HOME` for every `.git`, `whitelist` uses `scan.roots` only.
   - `privacy.blocklist` — any project names to exclude.
   - `privacy.abstract_tech` — set `true` if the user wants concrete tech hidden.
   - Which cloud exports they've dropped into `data/imports/` (ChatGPT, Claude.ai, Gemini Takeout, Grok, Perplexity, Mistral, Poe).

3. **Run extractors**:
   ```bash
   uv run python cli.py extract
   ```
   This populates `data/cache/*.json` (one file per source). Check `uv run python cli.py status` for counts.

4. **Aggregate**:
   ```bash
   uv run python cli.py aggregate
   ```
   Groups activities by project, infers tech stack. Output: `data/cache/_project_groups.json`.

5. **Enrich** (optional but recommended): writes summary + achievements per project.
   ```bash
   uv run python cli.py enrich
   ```
   Under the hood this calls `claude -p` for each project group. If that's slow or rate-limited, disable by setting `enrich.mode: "fallback"` in `config.yaml`.

6. **Render**:
   ```bash
   uv run python cli.py render -f md    # or docx, pdf, all
   ```
   Each render creates `data/resume_history/resume_v{N}.{md,docx,pdf}` and commits to an internal git repo.

7. **Tailor for a job** (optional): place the JD in `data/imports/jd.txt` and run:
   ```bash
   uv run python cli.py render -f md --tailor data/imports/jd.txt
   ```

## Useful commands

- `uv run python cli.py status` — show per-source activity counts
- `uv run python cli.py list-versions` — list resume versions from the git log
- `uv run python cli.py diff v001 v002` — diff two versions

## How to help the user

- If they say "my resume is missing X tool", check whether that extractor exists under `extractors/local/`, `extractors/cloud_export/`, or `extractors/api/`. If not, add one following the `base.py` contract (`extract(cfg) -> list[Activity]`). Path conventions live in `config.yaml`.
- If they want a new section on the resume, edit `profile.yaml` (add to `custom_sections`) and optionally update `render/templates/resume.md.j2`.
- If they want to rollback a draft: `uv run python cli.py list-versions` then `cd data/resume_history && git checkout <sha> -- resume_v001.md`.
- If extraction is slow, the bottleneck is usually `git_repos` or `aider` scanning `$HOME`. Switch `scan.mode` to `whitelist`.

## Schema contract

All extractors return a list of `core.schema.Activity`:
- `source` (enum), `session_id`, `timestamp_start`, `timestamp_end`
- `project`, `activity_type`, `tech_stack`, `keywords`, `summary`
- `user_prompts_count`, `tool_calls_count`, `files_touched`
- `raw_ref` (file:line for traceability), `extra`

Never invent activities. If a tool's data isn't reachable, return `[]` silently.
