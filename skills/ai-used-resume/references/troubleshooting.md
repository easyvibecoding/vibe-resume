# Troubleshooting & Pitfalls

Common issues the user will hit, and the fix.

## Output / rendering

- **Mixed-script output** (e.g. Japanese `role_label` leaking 简体 characters, zh_TW leaking 简体). The noun-phrase prompt has an anti-leak rule, but it only fires when `--locale` is explicit. Always pass `--locale <target>` on `enrich`.
- **Contact line wrap in CJK locales.** If `review` flags `contact_line_width`, split the contact row into two lines in `render/templates/resume.<locale>.md.j2`. Already done for `zh_TW`; port to any new CJK locale.
- **`--all-locales` ignores `-f`.** It honours `config.render.all_locales_formats` (default `["md"]`), not the CLI `--format`. Pass `-f` explicitly per-locale if you need docx/pdf for all.

## Enrichment

- **`claude -p` is optional.** No `claude` binary on PATH → enricher falls back to rule-based summaries. Functional but weaker bullets. Tell the user.
- **Score dropped after a change.** Run `uv run vibe-resume review --diff` (default on) for Δ vs the previous review of the same locale, then `uv run vibe-resume trend --locale <L>` for the whole history.
- **Tailoring for multiple JDs.** Keep `data/imports/jd_<company>.txt` per target. Enrich + render + review each before the interview cycle. `trend` shows whether tailoring helped.

## Extraction

- **Missing tool.** If the user says "my résumé is missing X tool", check `extractors/{local,cloud_export,api}/`. If absent, add a new extractor following `extractors/base.py`'s contract and register it in `core/runner.py`. Path conventions live in `config.yaml`.
- **First-run slowness.** `git_repos` / `aider` scanning the entire `$HOME` can take 1-3 minutes. Switch `scan.mode: whitelist` in `config.yaml` and list project directories in `scan.roots`.

## Content / profile

- **New résumé section.** Edit `profile.yaml` (`custom_sections` for awards/talks/hobbies, or a bespoke top-level key). For a new template slot, also edit `render/templates/resume.<locale>.md.j2`.
- **Rollback a draft.** `uv run vibe-resume list-versions`, then inside the internal git repo:
  ```bash
  cd data/resume_history && git checkout <sha> -- resume_v001_en_US.md
  ```

## Privacy & commits

- **`profile.yaml` must never be committed.** It's in `.gitignore` and contains the user's real PII. If the user accidentally stages it, refuse and point them to `profile.example.yaml` for the template.
- **`data/imports/` is gitignored except `sample_jd.txt`.** Real JD files live here and must NOT end up in commits.
