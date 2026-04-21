# Strategic résumé — `--company <key> --level <key>`

Tailor `enrich` and `review` against a named target employer and a seniority bracket, stacked on top of `--locale`, `--persona`, and `--tailor`. 70 bundled company profiles (`core/profiles/*.yaml`) + 6 career-level archetypes are available out of the box.

## `--company <key>`

- One of 70 bundled keys — run `uv run vibe-resume company list [--tier X]` to browse.
- Tiers: `frontier_ai` / `ai_unicorn` / `regional_ai` / `tw_local` / `us_tier2` / `eu` / `jp` / `kr`.
- On `enrich`: injects the profile's `enrich_bias` into the LLM prompt, biasing bullets toward the employer's must-haves and keyword anchors (without inventing matches).
- On `review`: adds a 0-10 **Company keyword coverage** score — counts how many of the profile's `keyword_anchors` actually surface in the rendered résumé.
- **Staleness guard**: every apply auto-checks `last_verified_at`. Profiles older than 90 days trigger a loud warning with the refresh instruction. Never silently tailors against stale research.

## `--level <key>`

One of: `new_grad` / `junior` / `mid` / `senior` / `staff_plus` / `research_scientist`.

Bakes in the lead-bullet signal the reviewer expects at that bracket, so mid-level work is not promoted into unsupported staff-plus claims.

## Block injection order (deterministic)

```
tailor → persona → level → company
```

The most-specific lens lands closest to the YAML emission point and wins tie-breaks on any conflicting guidance.

## Managing the profile catalogue

| Command | Purpose |
|---|---|
| `uv run vibe-resume company list [--tier X]` | Catalogue grouped by tier |
| `uv run vibe-resume company show <key>` | Full profile (must-haves, red flags, keyword anchors, enrich_bias, review_tips, verified date) |
| `uv run vibe-resume company audit [--only-stale]` | Age table across all profiles; default staleness threshold is 90 days (quarterly refresh cadence matched to current AI-hiring market churn) |
| `uv run vibe-resume company verify <key> [--apply]` | Delegates fact-check to `claude -p`; saves markdown report under `data/verification_reports/`; auto-bumps verified date on `VERDICT: clean` |
| `uv run vibe-resume company mark-verified <key>` | Bump `last_verified_at` in place (one-line YAML edit, preserves formatting) |

## Adding a new employer

Drop-in: write `core/profiles/<key>.yaml` with the seven required fields plus `last_verified_at: "YYYY-MM-DD"`. The loader validates schema + tier + filename match at import time.

## Typical flow

```bash
# Tailor for Anthropic at senior level, using a specific JD, HR persona, en_US
uv run vibe-resume enrich \
    --tailor data/imports/jd.txt \
    --persona hr \
    --level senior \
    --company anthropic \
    --locale en_US

uv run vibe-resume render -f all --locale en_US
uv run vibe-resume review --company anthropic --level senior --locale en_US
```
