# Troubleshooting & Pitfalls

Common issues the user will hit, and the fix.

## Output / rendering

- **Mixed-script output** (e.g. Japanese `role_label` leaking 简体 characters, zh_TW leaking 简体). The noun-phrase prompt has an anti-leak rule, but it only fires when `--locale` is explicit. Always pass `--locale <target>` on `enrich`.
- **Contact line wrap in CJK locales.** If `review` flags `contact_line_width`, split the contact row into two lines in `src/vibe_resume/render/templates/resume.<locale>.md.j2`. Already done for `zh_TW`; port to any new CJK locale.
- **`--all-locales` ignores `-f`.** It honours `config.render.all_locales_formats` (default `["md"]`), not the CLI `--format`. Pass `-f` explicitly per-locale if you need docx/pdf for all.

## Enrichment

- **`claude -p` is optional but billed separately as of 2026-06-15.** The
  `--mode subprocess` path spawns `claude -p`, which bills against the
  Anthropic Agent SDK monthly quota pool (Pro $20 / Max 20x $200), not
  your Claude Code subscription. The default `--mode prompt` flow keeps
  everything inside the current Claude Code session (uses subscription
  quota). If `claude` is missing on PATH, `--mode subprocess` automatically
  falls back to `--mode rule-based`.
  ([Anthropic billing change](https://codersera.com/blog/anthropic-june-2026-billing-change-claude-code/))
- **Score dropped after a change.** Run `uv run vibe-resume review --diff` (default on) for Δ vs the previous review of the same locale, then `uv run vibe-resume trend --locale <L>` for the whole history.
- **Tailoring for multiple JDs.** Keep `data/imports/jd_<company>.txt` per target. Enrich + render + review each before the interview cycle. `trend` shows whether tailoring helped.

## Extraction

- **Missing tool.** If the user says "my résumé is missing X tool", check `src/vibe_resume/extractors/{local,cloud_export,api}/`. If absent, add a new extractor following `src/vibe_resume/extractors/base.py`'s contract and register it in `src/vibe_resume/core/runner.py`. Path conventions live in `config.yaml`.
- **First-run slowness.** `git_repos` / `aider` scanning the entire `$HOME` can take 1-3 minutes. Switch `scan.mode: whitelist` in `config.yaml` and list project directories in `scan.roots`.

## Content / profile

- **New résumé section.** Edit `profile.yaml` (`custom_sections` for awards/talks/hobbies, or a bespoke top-level key). For a new template slot, also edit `src/vibe_resume/render/templates/resume.<locale>.md.j2`.
- **Rollback a draft.** `uv run vibe-resume list-versions`, then inside the internal git repo:
  ```bash
  cd data/resume_history && git checkout <sha> -- resume_v001_en_US.md
  ```

## Privacy & commits

- **`profile.yaml` must never be committed.** It's in `.gitignore` and contains the user's real PII. If the user accidentally stages it, refuse and point them to `profile.example.yaml` for the template.
- **`data/imports/` is gitignored except `sample_jd.txt`.** Real JD files live here and must NOT end up in commits.
