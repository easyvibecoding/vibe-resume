# Extending the pipeline

Notes for agents who are asked to add a new extractor, locale, or persona. For project-level conventions (how CLI subcommands are wired, where cached data lives, etc.), also consult the root `CLAUDE.md`.

## Activity schema contract (for new extractors)

All extractors return `list[core.schema.Activity]`. Required fields per item:

- `source` (enum), `session_id`, `timestamp_start`, `timestamp_end`
- `project`, `activity_type`, `tech_stack`, `keywords`, `summary`
- `user_prompts_count`, `tool_calls_count`, `files_touched`
- `raw_ref` (file:line — essential for traceability during review)
- `extra` (free-form dict)

**Never invent activities.** If a tool's data isn't reachable on this machine, return `[]` silently — the pipeline must never hallucinate a project the user didn't actually work on.

Registration:

1. Implement the extractor under `extractors/{local,cloud_export,api}/<name>.py` following `extractors/base.py`'s contract.
2. Register the module name in `core/runner.py::LOCAL_EXTRACTORS`, `CLOUD_EXTRACTORS`, or `AIGC_EXTRACTORS` (whichever bucket fits).
3. Add its config path to `config.example.yaml::extractors.<name>.path`.
4. Add a unit test under `tests/test_extractors*.py` that exercises the happy path against a fixture.

## Locale

See root `CLAUDE.md § Locale resolution chain` for the canonical registration steps. TL;DR:

1. Add the locale to `render/i18n.py::LOCALES`.
2. Create `render/templates/resume.<locale>.md.j2`.
3. If the review pitfalls apply (e.g. CJK contact-line wrap, photo-expected culture), port the template tweak from an existing same-family locale.

## Persona

Persona prompts live under `core/personas/`. Add a key to the registry plus a prompt module; the `--persona` CLI flag auto-picks up new entries.
