# Contributing to vibe-resume

Thanks for considering a contribution! `vibe-resume` is a CLI pipeline, so most
contributions fall into one of four shapes:

1. **New extractor** — add a new AI tool or data source (`extractors/**/`).
2. **New locale** — add a regional résumé template + i18n registration.
3. **Review rules** — add or tighten a reviewer-audit check (`core/review.py`).
4. **Enricher prompts** — refine the LLM prompt for a given locale / style.

## Local setup

```bash
# 1. clone
git clone https://github.com/easyvibecoding/vibe-resume.git
cd vibe-resume

# 2. install (uv recommended; pip also works)
uv sync --all-extras
# or: pip install -e ".[dev,pdf]"

# 3. run the suite
uv run pytest -q
```

Python 3.12+ is required. Optional dependencies:

- `pdf` — WeasyPrint for PDF rendering (XeLaTeX + pandoc also supported out-of-box)
- `dev` — pytest + ruff

## Adding a new extractor

1. Create `extractors/<kind>/<tool>.py` with an `extract(cfg) -> list[Activity]` function (`kind` ∈ `local` / `cloud_export` / `api`).
2. Register the module name in `core/runner.py` under the matching list.
3. Add a YAML block to `config.example.yaml` so users can toggle it.
4. If the source needs redaction, extend `core/privacy.py`.

## Adding a new locale

1. Copy `render/templates/resume.en_US.md.j2` → `resume.<locale>.md.j2` and
   adapt headings / personal-info layout per `docs/resume_locales.md`.
2. Register the locale in `render/i18n.py::LOCALES` with `style`, `photo`,
   `personal_fields`, `headings`, `date_format`, and `filename_style`.
3. If the locale needs a language-label in the enrich prompt, extend
   `core/enricher.py::_LANG_LABEL`.
4. Add at least one unit test to `tests/test_i18n.py` covering `format_date`
   and `localized` for the new locale.

## Style

- `ruff check .` must pass (config in `pyproject.toml`).
- Keep commit messages imperative and focused; reference the locale/tool
  area in the subject (e.g. `feat(ja_JP): …`).
- Prefer a **small, well-tested PR** over a big bundle.

## Tests

```bash
uv run pytest -q                    # all tests
uv run pytest tests/test_review.py  # just the review suite
```

## Reporting a security issue

See [SECURITY.md](SECURITY.md) — don't open a public issue for vulnerabilities.

## Licence

By contributing, you agree your changes will be released under the project's
[MIT licence](LICENSE).
