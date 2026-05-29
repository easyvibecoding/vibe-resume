# AI-proficiency rubric — enrich + review + agentic persona (#47)

**Date:** 2026-05-29  ·  **Target version:** v0.15.0  ·  **Issue:** #47

## Goal

Bake the industry-researched "good AI usage on a résumé" rubric into the two
generation/scoring surfaces so output stops plateauing at "uses AI" framing:

1. **enrich** — a new AI-proficiency directive injected into the LLM prompt
   when the activity carries agentic signals (or an agentic persona/emphasis
   is active), encoding the winning-bullet formula + senior differentiators +
   anti-patterns.
2. **review** — two new scorecard checks (one positive, one negative) that
   reward tool-paired-with-human-gate framing and flag junior framing,
   stale-stack headlines, and unverified-judge claims. Gated on AI content so
   non-AI résumés are unaffected and historical scores stay comparable.
3. **metric guidance, not fabrication** — when an AI bullet carries no number,
   the reviewer *hints which real metric to go measure* (review round-trips,
   first-pass QA %, token-cost %, cycle time, eval task-completion). A pointer,
   never an injected value.

## Architecture

A single bundled, cited, dated **`market_rubric.yaml`** is the source of truth
for both surfaces. #47 ships the bundled baseline; the sibling #46 later makes
it refreshable by overwriting a user-cache copy — **same schema, zero rework.**

```
core/market_rubric.yaml         # bundled baseline (cited + dated)
core/rubric.py::load_rubric()   # lru_cached loader; user-cache copy wins if present
        │
        ├── enricher._build_prompt()  → AI_PROFICIENCY_BLOCK (both emit + subprocess paths)
        └── review.review()           → _check_ai_proficiency / _check_ai_red_flags
```

Bundled-YAML-as-package-data already works for `core/profiles/*.yaml`
(`packages = ["src/vibe_resume"]`), so no `pyproject` packaging change is
needed.

### Loader precedence (forward-compatible with #46)

`load_rubric(cfg=None)` resolves in this order:

1. `data/cache/market_rubric.yaml` under the user root **if it exists**
   (this is what #46's `research` pass will write) — and only if it parses.
2. the bundled `core/market_rubric.yaml`.

`load_rubric` is `functools.lru_cache`-wrapped (no args in the hot path) so
`_build_prompt` and each review check can call it freely. A `refreshed_at`
older than 180 days surfaces a one-line staleness note in the review report
(mirrors the company-profile `last_verified_at` pattern) — informational only,
no score impact.

## `market_rubric.yaml` schema

```yaml
version: 1
refreshed_at: "2026-05-29"          # ISO date; staleness measured from here
source_note: >
  Bundled baseline distilled from 2025-2026 AI-hiring research.
  Refresh via `vibe-resume research` (#46) to overwrite with a dated, cited pull.
sources:                            # cited, auditable — never rots silently
  - title: "Compound Engineering (Every)"
    url: "https://every.to/source-code/the-compound-engineer"
  - title: "Anthropic — Context engineering for agents"
    url: "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents"
  - title: "Anthropic — Building effective agents / evals"
    url: "https://www.anthropic.com/engineering/building-effective-agents"
  - title: "DORA 2025 — State of AI-assisted Software Development"
    url: "https://dora.dev/research/2025/"
  - title: "2026 ATS / AI résumé keyword guidance"
    url: "https://www.jobscan.co/blog/ats-resume/"
bullet_formula: "directing verb + named tool + context/scale + measurable delta + human quality gate"
agentic_keywords:                   # surfaces senior framing in enrich; AI-content gate in review
  - MCP
  - subagent
  - Agent Skills
  - context engineering
  - eval harness
  - LLM-as-judge
  - compound engineering
  - model routing
  - spec-driven
  - test-driven
  - orchestration
  - prompt caching
ai_tool_names:                      # bare tool mentions — used by AI-content gate + name-drop check
  - Claude Code
  - Claude
  - Copilot
  - Cursor
  - GPT
  - ChatGPT
  - LLM
  - "AI agent"
human_gate_verbs:                   # prove the human judgment layer (positive signal)
  - reviewed
  - verified
  - validated
  - architected
  - audited
  - vetted
  - gated
  - benchmarked
senior_differentiators:             # injected into enrich prompt
  - "scoped MCP / supervisor-subagent topology"
  - "authored Agent Skills for team quality & consistency"
  - "subagents for context isolation"
  - "token-cost mechanism (model routing, caching, context pruning)"
  - "compound engineering (Plan -> Work -> Review -> Compound loop)"
  - "owns the eval harness / LLM-as-judge"
anti_patterns:                      # injected into enrich prompt as 'avoid'
  - "'AI wrote it, I shipped it' with no verification"
  - "a 2024-only stack (LangChain + Pinecone + ChatGPT API) as the headline"
  - "raw-volume bragging ('3x more PRs')"
  - "assuming impact instead of measuring it"
  - "unverified LLM-as-judge claims"
yellow_flag_patterns:               # regex-driven review red-flag detections
  - kind: stale_stack
    pattern: "(?i)\\b(langchain|pinecone)\\b"
    why: "2024-only stack (LangChain/Pinecone) as a headline now reads as a yellow flag"
  - kind: junior_volume
    pattern: "(?i)\\b\\d+\\s*x\\s+(?:more|faster|as many)\\b.*\\b(prs?|commits?|lines|tickets?)\\b"
    why: "raw-volume bragging reads junior — pair the volume with an outcome metric"
  - kind: unverified_judge
    pattern: "(?i)\\bai[- ]?(?:reviewed|validated|judged|verified|approved)\\b"
    why: "an 'AI reviewed/validated' claim with no eval/verification evidence is unverified"
metric_hints:                       # which REAL metric to go measure — never a value
  review: ["review round-trips saved", "first-pass QA %"]
  cost: ["token-cost % reduction", "model-routing savings"]
  cycle: ["cycle time", "lead time for changes"]
  eval: ["eval task-completion %", "regression catch rate"]
```

A typed `MarketRubric` (frozen dataclass) wraps the parsed mapping with safe
defaults so a malformed/partial YAML degrades to empty lists rather than
crashing enrich/review. `YellowFlag` is a small `(kind, pattern, why)` record;
patterns compile lazily.

## Enricher touch point — `AI_PROFICIENCY_BLOCK`

A new prompt block (sibling of `AGENTIC_SIGNALS_BLOCK`), appended in
`_build_prompt` **after** `AGENTIC_SIGNALS_BLOCK` / `INSTALLED_TOOLKIT_BLOCK`
and before the emphasis block. Fires when **any** of:

- `g.agentic_signals` has at least one populated field, **or**
- the active `persona` is the agentic/AI-leadership persona (key match), **or**
- `emphasis` is present and its intent/keywords mention AI/agentic terms.

Content (templated from the rubric, so it refreshes with #46):

```
AI-PROFICIENCY FRAMING (apply only when the raw activity supports it — never invent):
- Winning bullet shape: {bullet_formula}.
- Pair AI delegation with the human-only work (architecture / security review /
  verification) — high usage + high verification reads senior; blind enthusiasm does not.
- When the data supports it, surface senior differentiators: {senior_differentiators}.
- Avoid these junior tells: {anti_patterns}.
- Frame AI tools as directed multipliers, not skills. Keep every claim grounded
  in the activity above; never fabricate a metric, tool, or decision.
```

Both enrich paths (`emit_jobs` and `_enrich_with_subprocess`) call
`_build_prompt`, so threading the block through `_build_prompt` covers both.
The rubric is loaded inside `_build_prompt` via the cached `load_rubric()` — no
signature change rippling through `emit_jobs`.

## Review touch point — two gated checks

A helper `_has_ai_content(md, rubric)` returns True when the résumé text
contains any `agentic_keywords` or `ai_tool_names` (case-insensitive). Both new
checks return `Score(max=0, …, ["no AI/agentic content — skipped"])` when it is
False — exactly the keyword-echo skip pattern, so non-AI résumés keep their
existing denominator and historical comparability.

### 1. `_check_ai_proficiency` (positive, max 10)

Over the AI-related bullets (a bullet mentioning a tool/agentic keyword):

- **+** ratio of AI bullets that also contain a `human_gate_verb` (tool paired
  with judgment). Linear to 10.
- **Metric guidance (notes, not score):** for AI bullets with no metric
  (`_count_metrics == 0`), append a note pointing at the most relevant
  `metric_hints` category (heuristic keyword → category map), e.g.
  *"L42 mentions AI review but no number — consider 'review round-trips saved'
  or 'first-pass QA %'."* This is a pointer to measure, never an injected value.

### 2. `_check_ai_red_flags` (negative, starts at 10, deducts)

Mirrors `_check_red_flags`:

- `junior_volume` yellow-flag match → −3, note the offending line + why.
- bare tool name-drop (an `ai_tool_names` mention in a bullet with **no** metric
  **and no** `human_gate_verb`) → −2, note "reads junior; pair with an outcome".
- `stale_stack` yellow-flag match **in the top fold / headline** → −2.
- `unverified_judge` yellow-flag match with no `human_gate_verb`/eval evidence
  in the same bullet → −2.
- floor at 0; "no AI framing red flags detected" when clean.

Both checks are appended in `review()` after the base 8 (and after the optional
company check), so the base rubric stays byte-comparable across versions when no
AI content is present.

## Data flow

```
load_rubric()  ← core/market_rubric.yaml  (or data/cache override from #46)
   │
enrich:  _build_prompt(g) → if AI-relevant: append AI_PROFICIENCY_BLOCK(rubric)
   │
review:  review(md) → if _has_ai_content: + _check_ai_proficiency, + _check_ai_red_flags
                                            (else both max=0 skipped)
report:  staleness note if rubric.refreshed_at > 180d old
```

## Error handling

- Missing/malformed bundled YAML → `MarketRubric` with empty collections;
  enrich block simply doesn't fire, review checks skip (max=0). Never crashes.
- User-cache override that fails to parse → fall back to bundled, emit a dim
  warning (consistent with manifest-unreadable handling in `enrich_jobs`).
- Unknown `metric_hints` category for a bullet → omit the hint note silently.

## Testing

- `tests/test_rubric.py` — loader precedence (bundled vs cache override),
  malformed-YAML degradation, staleness flag boundary.
- `tests/test_enricher.py` — `AI_PROFICIENCY_BLOCK` fires with agentic signals /
  agentic persona / AI emphasis; does **not** fire for a plain group; block text
  contains the formula + a senior differentiator.
- `tests/test_review.py` — `_has_ai_content` gate; positive check rewards
  tool+gate pairing; metric-hint note appears for number-less AI bullet;
  red-flags check deducts for junior-volume / bare name-drop / stale-stack /
  unverified-judge; both checks max=0 (skipped) on a non-AI résumé so the total
  denominator is unchanged.

## Out of scope (→ #46)

- The `vibe-resume research` / market-refresh command that *writes* the
  `data/cache/market_rubric.yaml` override. #47 only ships + consumes the
  bundled baseline; the loader already prefers the cache copy so #46 is purely
  additive.

## Non-fabrication contract (preserved)

Enrich block is always conditioned on "when the raw activity supports it";
review metric guidance is a *pointer to a real metric to measure*, and metric
ranges (if any) are used only to sanity-check, never written into a bullet.
