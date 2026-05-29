# Research / market-refresh pass (#46)

**Date:** 2026-05-29  ·  **Target version:** v0.16.0  ·  **Issue:** #46

## Goal

An opt-in `vibe-resume research` pass that refreshes the AI-proficiency rubric
(#47) against the current AI-hiring market — fan-out web research + adversarial
verification → a **cited, dated** `data/cache/market_rubric.yaml` that enrich +
review already consume (the #47 loader prefers this override). **Never injects
numbers into bullets;** it informs framing/keywords/anti-patterns only.

## Architecture

Mirror the proven enrich **emit → session-processes → ingest** flow. No host
`deep-research` skill is available locally, so the research itself runs in the
user's Claude Code session (which has web search); the CLI brackets it.

```
vibe-resume research            → writes data/research/research.prompt.md
  (session does fan-out web research + adversarial verify, writes research.result.yaml)
vibe-resume research --ingest   → validates result, installs data/cache/market_rubric.yaml
                                  (clears load_rubric() lru_cache)
```

`data/cache/market_rubric.yaml` is exactly the #47 override path, so once
ingested, enrich's `AI_PROFICIENCY_BLOCK` and review's AI checks pick it up with
zero further wiring.

### `core/research.py`

- `emit_research_prompt(out_dir, *, today) -> Path` — writes
  `research.prompt.md` containing:
  - **Fan-out angles** (the issue's list): recruiter evaluation criteria,
    senior-vs-junior AI signals, ATS keyword sets for AI/agentic roles, credible
    impact-metric ranges, current yellow-flag anti-patterns.
  - **Adversarial-verify instruction**: verify each claim against ≥2 sources;
    *kill* ungrounded hype (e.g. "AI improves productivity 80%") that lacks a
    credible citation; prefer primary sources (vendor engineering blogs,
    DORA-style reports, ATS vendors).
  - **Required output schema** = the #47 `market_rubric.yaml` shape, with two
    hard rules: `refreshed_at: <today>` and a non-empty `sources:` list where
    every entry has a `title` + `url`. Metric ranges are for sanity-checking,
    **never** to be written into résumé bullets.
  - Instruction to write `research.result.yaml` next to the prompt.
- `ingest_research(result_path) -> tuple[dict, list[str]]` — strict validation:
  1. parse YAML → must be a mapping, else reject.
  2. **`sources` must be a non-empty list** (each with a `url`), else reject —
     this is the adversarial-verify gate: no un-sourced rubric is installed.
  3. normalize through the #47 `rubric._coerce` shape; drop any
     `yellow_flag_patterns` whose regex fails to compile (warn, don't abort).
  4. on success: write `data/cache/market_rubric.yaml`, call
     `rubric.load_rubric.cache_clear()`, return `(installed_dict, warnings)`.
  Rejection raises `ResearchValidationError` (CLI prints it; old cache, if any,
  is untouched).
- `staleness_note(rubric) -> str | None` — returns a one-line
  "rubric N days stale — run `vibe-resume research`" when
  `rubric.is_stale()` (180-day threshold from #47), else None.

### CLI — `research` command

```
vibe-resume research            # emit prompt (opt-in; prints next-step hint)
vibe-resume research --ingest   # validate + install result
vibe-resume research --status   # show cache date + staleness (optional, thin)
```

Opt-in by nature (it's a manual command + the session does the network/LLM
work), matching the `github` extractor's opt-in stance — no always-on network.

### Staleness surfacing (enrich + review)

The issue asks enrich + review to warn when the rubric is stale:

- **enrich** — `_do_emit` prints a yellow `staleness_note(load_rubric())` line
  when non-None (the generation side sees it before emitting prompts).
- **review** — `_check_ai_proficiency` appends the staleness note to its
  `notes` when the active rubric is stale (the scoring side surfaces it in the
  markdown report). No score impact — informational only.

## `config.example.yaml`

Add a `research:` block (documentation/opt-in marker, default disabled-ish):

```yaml
research:
  enabled: false        # opt-in: `vibe-resume research` works regardless, but
                        # this documents that it does network + LLM work in your
                        # Claude Code session and writes data/cache/market_rubric.yaml
  stale_after_days: 180 # surfaced by enrich/review when the cached rubric ages past this
```

`stale_after_days` is read by `staleness_note` (falls back to the 180 default in
`rubric._STALE_DAYS` when absent), so a user can tighten the cadence.

## Error handling

- Missing `research.result.yaml` on `--ingest` → clear error naming the emit
  step; exit non-zero; no cache change.
- Result with empty/absent `sources` → `ResearchValidationError`; old cache kept.
- Malformed YAML → reject; old cache kept.
- A bad regex in `yellow_flag_patterns` → dropped with a warning, rest installed.

## Testing

- `tests/test_research.py` — emit writes a prompt containing the fan-out angles +
  the "every claim needs a source / kill un-sourced hype" instruction + the
  required schema; ingest **rejects** a result with no `sources`; ingest of a
  valid cited result writes `data/cache/market_rubric.yaml` and the bytes parse
  back through `load_rubric()` (override wins); a bad-regex yellow-flag is
  dropped with a warning, not fatal; `staleness_note` returns a string for a
  stale rubric and None for a fresh one.
- `tests/test_review.py` — `_check_ai_proficiency` surfaces the staleness note
  when the active rubric is stale (monkeypatch a stale `refreshed_at`).

## Non-fabrication contract (preserved)

The emitted prompt forbids writing metric *values* into bullets — ranges are for
sanity-checking and flagging only. Ingest installs framing/keywords/anti-patterns
+ cited sources; it never touches a résumé's numbers.

## Out of scope

- Auto-running the research without a session (no headless web crawler ships
  here). `--mode subprocess` (`claude -p`) is deliberately **not** built — YAGNI;
  the emit→ingest path covers the use case and stays host-portable.
