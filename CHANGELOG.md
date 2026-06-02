# Changelog

All notable changes to `vibe-resume`. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.35.0] — 2026-06-02

### Fixed

- **Gate-mode `run --continue` silently rendered UN-enriched groups when G4
  wasn't armed** (#94, silent-corruption class). The enrich emit only fired when
  the pending gate was G4; arming e.g. `--gates G1,G2,G7,G8` skipped emit, ingested
  nothing, and rendered raw/curated groups (a contentless résumé) with no error.
  Now, on `--continue` with G4 not armed and no enrich manifest present, the run
  **emits the manifests and stops** with a process-then-continue message instead
  of rendering un-enriched.
- **`review` scored the `_detailed` variant against the fixed locale page budget
  → misleading C / "Page 2/10"** (#95). #88 made the detailed variant uncapped at
  render, but `review` still judged it against the ATS/locale target (≤2.0). Now a
  `_detailed` file is scored against a detailed-appropriate budget — the configured
  `config.render.variants` detailed `max_pages` if set, else 2.5× the locale target
  — and the budget used is disclosed in the header. `--max-pages` still overrides.
  Applies per-file, so `review --variants` scores each variant on its own budget.

### Added

- **Remote-less local dirs are now matched against the same-named remote repo at
  `curate`** (#93, residual of #37). A working dir with no git remote
  (`canonical_key: None`) whose basename **uniquely** matches the repo basename of
  a remote-keyed group (e.g. local `vibecoding` ↔ a repo `…/vibecoding`) is
  surfaced as a `needs_decision` `merge_into` suggestion — never a silent
  auto-merge (basename collisions are possible; 0 or >1 matches → left as-is, and
  `auto_drop` precedence is preserved).

## [0.34.1] — 2026-06-02

### Fixed

- **`review --file <relative path>` crashed with `ValueError`** (#92, regression
  from the #86 `Scored:` print). The new header printed `md_path.relative_to(ROOT)`,
  which raises when `--file` is a relative or out-of-repo path. Now resolves first
  and guards `relative_to`, falling back to the absolute path.
- **`review --file` mis-inferred `en_US` for a locale-tagged filename** (#92). The
  filename→locale regex `([a-zA-Z_]+)` greedily captured the persona/variant
  suffix too (`zh_TW_agentic_ats` from `resume_v012_zh_TW_agentic_ats.md`),
  yielding an invalid locale that fell back to `en_US` — so a non-English résumé
  under-scored AI-proficiency. Now captures only the `xx_YY` locale token. Affects
  every suffixed filename, not just `--file`.

## [0.34.0] — 2026-06-02

A batch of agent-operation fixes surfaced by a real interactive run (#82–#91):
silent-corruption bugs first, then disclosure/ergonomics.

### Fixed

- **Stale enrich YAML ingested by POSITION after re-aggregate → scrambled
  bullets** (#84, silent corruption). `ingest_jobs` matched the old manifest to
  the current groups by list index; after `aggregate` reordered/added/dropped
  groups, each entry's bullets landed on whatever now sat at that index (only a
  soft "name mismatch … Using raw[N]" warning). Now keyed by group **identity**
  (`name` → `canonical_key` fallback, each group consumed once); an entry that
  matches no current group is **skipped + warned loudly**, never written onto an
  unrelated group.
- **AI-proficiency human-gate detection scored 0 for every non-English locale**
  (#82). `gate_terms` matched only an exact locale key, but
  `human_gate_verbs_by_locale` is keyed by base family (`zh`/`ja`/…), so `zh_TW`
  / `ja_JP` / `de_DE` missed and a résumé that honestly paired a tool with a
  human gate was structurally pinned at 0/10. Now normalizes to the base family.
- **Detailed render silently truncated each group to 2 achievements** (#88).
  The `detailed` variant inherited the global `config.render.page_budget` and got
  floored — hiding woven content with no warning. Variants no longer inherit the
  global budget (only their own `max_pages` caps them), and any per-group
  truncation now prints a warning. New `render --bullets-per-group N` hard cap.
- **`curate --apply` silently ignored the edited `action`** (#87). A human edit
  setting `action: drop` with a non-standard `tier` (e.g. `manual_drop`) failed
  `tier` Literal validation, so the whole record fell back to the auto-only
  classification. `tier` is now a free `str` (`action` is authoritative).
- **`review` scored a stale non-suffixed version and never said which file**
  (#86, #63). The persona+locale default glob excluded `_ats`/`_detailed`
  variants and picked the highest non-suffixed file (often stale). Now includes
  variant suffixes, selects by **version number** (not lexical order), and
  **always prints the resolved target path**.
- **`run --continue` replayed the full `extract` (~4min) on every resume** (#83).
  A `G1=reextract` decision re-fired each `--continue`. Once the extract cache is
  fresh (the reextract already ran this session), it now honors `--max-age-days`
  and skips the redundant extract (still re-aggregates).
- **Gate recompute bypassed `curate --apply` cleanup** (#85). The G2/recompute
  `aggregate` regenerated raw groups and left the curated cache stale, silently
  dropping the human's curation. Now re-applies `_curation.yaml` after any
  recompute aggregate so curation survives `--continue`.

### Added

- **`enrich --candidates` evidence-aware first pass** (#89). Each group's enrich
  prompt now carries an `EVIDENCE DISCLOSURE` block — the human-gate phrasing and
  `safe_to_surface` metrics the evidence layer mines from the activity record —
  so a faithful first-pass bullet can pair tool + gate and surface real numbers
  without the manual evidence→re-edit loop. Anti-fabrication contract intact.
- **`curate --drop/--merge/--keep` verbs** (#87) — set actions without hand-editing
  YAML; unknown names are reported, not silently ignored.
- **`review --json` and `review --variants`** (#91) — structured scorecard (with
  resolved target path) on stdout, and one-call scoring of every rendered variant
  keyed by variant, for agent consumption.
- **`gates state [--json]`** (#90) — machine-readable run state: armed gates,
  fully-wired vs emit-only, the pending gate, each recorded decision, and per-gate
  recompute suffix, so an agent drives the gate machine deterministically instead
  of parsing console prose. (The `full_review` G3 stall noted in #90 was already
  fixed in 0.32.3.)

## [0.33.1] — 2026-05-31

### Documentation

- **v0.33.0 exploration commands + Interactive Gate Mode were undocumented in
  the canonical `SKILL.md` / `AGENTS.md`** (#81) — invisible to skill-discovery
  hosts that never run `--help`. Added Quick Reference rows for `explore`,
  `jd-check --explain`, `enrich --candidates` + `bullets-compare`,
  `personas-compare --with-scores`, `run --branch/--branches/--adopt`, plus
  `curate`/`emphasis`/`review-diff`; a new **Interactive Gate Mode** procedure
  subsection (presets `autopilot`/`checkpoints`/`full_review`, the G1–G8 model,
  the `run --interactive` → decide gate file → `run --continue` loop); and a
  Pitfalls note on the truthful-lever guarantees. Mirrored into `AGENTS.md`.
  A new `tests/test_skill_spec.py` drift guard asserts every top-level CLI
  command (and the v0.33.0 sub-flags) appears in `SKILL.md`, so a future command
  fails CI until documented.

## [0.33.0] — 2026-05-31

### Added — exploration & disclosure backlog

The unifying design principle (per the project goal): give the agent **disclosure
capability to self-mine what it needs to see**, and turn single-shot choices into
visible explorations. None of these rewrite bullets or fabricate — they surface
real signals and let the human pick.

- **`jd-check --explain`** (#80). For each MISSING JD keyword, classify it
  `groundable` (real supporting snippets exist in the activity — shown with source
  refs) vs `absent` ("honest gap — leave it"). Reuses the evidence-disclosure layer;
  advisory only, never auto-inserts. New `core/jd_explain.py`.
- **`explore` command** (#76). Sweeps a `top_n × page_budget` grid, renders+reviews
  each cell, and surfaces the **Pareto front** (configs not dominated on score↑ /
  pages↓) so the layout sweet-spot is found deliberately instead of by hand. Pure
  layout/selection — same truthful-lever guarantee as `iterate`. New `core/explore.py`.
- **`personas-compare --with-scores`** (#78). Joins the per-group bullet diff with a
  per-persona review-score table for the same locale + JD, and highlights the persona
  that maximizes JD fit — turning persona choice from an up-front guess into a
  data-driven comparison. New `core/persona_compare.py`.
- **`run --branch <Gn> --decision <json>` + `--branches` + `--adopt`** (#77). Forks
  the gate ledger to a named branch (original kept intact), applies the alternative
  decision, recomputes only that gate's invalidation suffix, and auto review-diffs the
  branch vs the original — making the gate flow a tree instead of a line. New
  `core/run_branch.py` (pure, deterministic branch ids; no clock/RNG).
- **`enrich --candidates <angles>` + `bullets-compare`** (#75). Generates N
  angle-biased candidate bullet-sets per group (`impact_first` / `breadth_first` /
  `depth_first` — each a prompt PREFIX; the anti-fabrication rules are untouched) and
  shows them side by side so the user picks the best framing per group. New
  `core/candidates.py`; the angle threads through `enricher._build_prompt` → `emit_jobs`.
- **G5 per-metric selection** (#79 part 2). The G5 metrics gate is no longer
  all-or-nothing: the decision records `pick: [{group, value}]` to weave a SUBSET, and
  the gate file scaffolds an empty `pick`. `g5_selected_metrics` always intersects the
  pick with `safe_to_surface` values, so a pick can never smuggle an unsafe/unlisted
  value past the P1 guard (closes #79; part 1 shipped in 0.32.4).

## [0.32.4] — 2026-05-31

### Fixed

- **G5 evidence classifier surfaced secret-key fragments and other noise as
  real metrics** (#79, part 1 — classifier hardening). The metric classifier
  now marks `safe_to_surface: false` for five additional noise contexts so they
  can never be woven into a résumé:
  - **secret/key fragments** — `487B` lifted from `CWA-BF1B60DA-2A68-487B-…`
    (also `sk-`, `ghp_`, `gho_`, `github_pat_`, `AIza…`, `x-access-token`,
    `bearer`, and dash-delimited hex/UUID groups). This is a genuine
    privacy/secret-leak fix, not just noise reduction.
  - **hash digests** — `256 h` from `SHA-256` (`md5`, `sha1`, `digest`,
    `checksum`, `hash`).
  - **ANSI / stack-trace markers** — `0m`/`4m` from colour codes, `line 42`.
  - **path / UUID fragments** — `4d`/`8d` from `~/.claude/image-cache/<uuid>`.
  - **enricher prompt-template self-reference** — `40%` lifted from the
    enricher's own template text (`寫「…壓縮約 40%」`, `e.g. …`, `範例:…`).

  Genuine plainly-stated metrics (`壓縮資料前置處理約 40%`, `handled 2k req/s`)
  are unaffected. Part 2 of #79 (per-metric pick-list selection at G5) remains
  open. New rules ordered ahead of the existing kind rules; 6 regression tests
  added.

## [0.32.3] — 2026-05-31

### Fixed

- **`run --preset full_review` skipped the enrich emit and rendered from raw
  output while reporting success** (#74, silent failure). `full_review` is the
  only preset that arms `G3` (overwrite), and `G3` sits *before* the `G4` enrich
  emit but had no pause handler in the `run` state machine. After `G1`+`G2` were
  decided, `first_pending_gate` returned `G3`, the `pending is G4` emit branch
  never fired, ingest found no jobs, and render fell back to raw aggregator output
  (no bullets) — then the run printed "gated run complete". Fixed by giving `G3`
  an emit+pause branch (symmetric with `G5`/`G6`/`G7`) so `full_review` records
  the overwrite decision and advances to the `G4` emit instead of swallowing it.
  Added regression tests driving `full_review` G1→G2→continue (pauses at `G3`,
  emits nothing, never claims completion) and G3-decided→continue (emits enrich,
  pauses at `G4`). `GUARD_PHASE` now maps `G3 → "overwrite"`.

## [0.32.2] — 2026-05-31

### Fixed

- **`claude_code_archive` extractor crash → silent data loss** (#73). It reused
  `claude_code._process_session` but still called it with the old 2-arg signature
  after that function grew to 6 args (`sample_n`/`per_chars`/`capture_args`/
  `git_cache`). Per-extractor failure isolation masked the `TypeError` as silent
  data loss — newly-archived sessions were never re-ingested and `status` kept the
  stale count. Fixed by mirroring `claude_code.extract`'s session-config read +
  per-run git cache and passing the full signature. Added archive-extractor tests
  (happy-path + missing-path) so future signature drift fails at CI, not at a
  user's `extract`.

## [0.32.1] — 2026-05-30

### Fixed

- **Self-documenting gate-file decisions** (#72). The emitted `*.gate.json` showed
  `"decision": null` with no shape hint, and the obvious fill (`"decision": "reuse"`)
  was silently coerced to `None` and mislabeled *"no decision filled in"* — stalling
  the documented happy path. Now the gate-file scaffolds `"decision": {"choice": null}`
  plus a `_hint`; a **bare string is accepted** and normalized to `{"choice": "reuse"}`;
  and `read_gate_decision` distinguishes a genuinely-empty decision from a wrong-shape
  one (`decision must be an object like {"choice": ...}; got [...]`). The engine was
  already correct — only the affordance is fixed.

## [0.32.0] — 2026-05-30

### Added

- **Interactive Gate Mode — wired into `run`** (#71, Phase 2 of #70). The tested
  gate core is now a usable flow:
  - `run --interactive` / `--preset <autopilot|checkpoints|full_review>` /
    `--gates G1,G2,...` arm a gate set (default `checkpoints` = G1/G2/G8),
    persisted to `data/run_ledger.json`.
  - A **ledger-driven multi-stop pause**: before a stage an armed-undecided gate
    guards, `run` emits a `*.gate.json` (decision context from the #62–#69
    disclosure) and **stops**; `run --continue` reads the decision, records it,
    and advances to the next gate. Fully-wired apply: G1 (reuse vs re-extract),
    G2 (top-N → enrich limit, drop-noise), G8 (terminal acceptance); G3–G7
    emit+record (MVP).
  - `run --resume-from Gn` → `resume_plan` → re-runs **only** the affected stage
    suffix (e.g. G5 → `render → review`), then prints an automatic review-diff.
  - **Backward compatible**: with no gate flags (or `--preset autopilot`), `run`
    and `run --continue` behave exactly as before — no ledger, no pauses. The G5
    fabrication guard (`assert_g5_safe`) stays active on the run path, with the
    gate context filtered to `safe_to_surface` metrics only.

## [0.31.0] — 2026-05-30

### Added

- **Interactive Gate Mode — core** (#70). The decision model behind making the
  pipeline's silent choices confirmable + replayable (built on the #62–#69
  disclosure work). `core/gates.py` provides: the 8 gates (G1 freshness … G8
  acceptance) with presets (`autopilot` / `checkpoints` / `full_review`); a
  gate→stage **invalidation graph** sliced from one `CANONICAL_ORDER` so a
  recompute set is always a well-ordered suffix (e.g. changing G5 metrics
  recomputes only `render → review`, keeping enrich); a clock-free **`GateLedger`**
  (timestamp passed in) with `resume_plan` for replay-from-gate; and gate-file
  emit/read mirroring the enrich manifest pattern. **P1 fabrication guard:**
  emitting the G5 metrics gate calls `assert_g5_safe`, so a gate can *never* list a
  non-`safe_to_surface` (invented/noise) metric — enforced in the core and in a
  cross-cutting `tests/test_alignment_guardrails.py`. CLI: `vibe-resume gates show`
  (gates + presets + blast-radius matrix) and `gates plan --changed Gn` (recompute
  stages / `resume_plan`). Full per-gate pause-and-continue wiring into `run` is
  the next phase.

## [0.30.1] — 2026-05-30

### Fixed

- **Range-expressed real metrics no longer suppressed** (#69, regression from #67).
  The blanket `X-Y%` → `ui_threshold` rule hid genuine range metrics like
  "減少前置處理時間 30-40%" / "cut by 30-40%". Now only explicit band/threshold cues
  (color words, 邊框/門檻, comparison operators `<`/`>`/`≥`) classify as
  `ui_threshold`; a bare `X-Y%` range with an improvement verb or commit provenance
  is a `real_metric`, and an ambiguous bare range is surfaced **with caution**
  (low confidence) rather than hidden — a concealed true metric is costlier than a
  low-confidence true positive the agent can vet.

## [0.30.0] — 2026-05-30

### Added

- **`review --max-pages` page-budget tolerance** (#68). The page-count check
  scored against a fixed per-locale target with no override, permanently capping
  an intentionally-detailed résumé at 2/10 and making the *detailed* variant
  grade lower than the *condensed* one even when it carried strictly more truthful
  signal. `review --max-pages <float>` (mirroring `render --max-pages`) now scores
  page-count against the budget the user actually chose, falling back to
  `config.render.page_budget` so review and render agree on "too long" by default.

## [0.29.0] — 2026-05-30

### Changed

- **`iterate` now consumes #62's metric classification** (#67). It dedups
  suggestions by `(group, normalized value)` and collapses the non-`safe_to_surface`
  candidates into a single `(N low-confidence/noise tokens hidden — run evidence
  --json)` line instead of listing noise the agent has to hand-filter. The
  classifier is also tightened: a 4-digit-year value — even with a stray glued
  unit like `2026 h` — is a `date_fragment`; threshold/range syntax (`75-89%`,
  `<90%`) is `ui_threshold`; `#<n>` / issue / PR refs are `id_number`. Fewer noise
  tokens reach the driving agent as "safe to surface."

## [0.28.1] — 2026-05-30

### Fixed

- **`render` now exits non-zero when a requested format is dropped** (#66,
  follow-up to #64). The PDF-skip warning existed but the command still returned
  exit 0, so CI/Makefiles/agents gating on the exit code treated a missing PDF as
  success. `render_draft` now reports dropped formats and the `render` command
  fails when any requested format wasn't produced; `--allow-partial` opts back
  into best-effort exit 0, and a structured `formats: md ✓ · pdf ✗` tail line lets
  callers parse per-format status.

## [0.28.0] — 2026-05-30

### Fixed

- **`project_metrics` was a silent no-op everywhere; per-locale template
  capabilities now disclosed** (#65). The `g.metrics` / Impact block lived only in
  the fallback `resume.md.j2`, but every locale (including en_US) has a specific
  template that's selected instead — so hand-supplied `project_metrics` rendered
  on no locale. Fixes:
  - The Impact block is added to `resume.en_US.md.j2`, restoring the documented
    hand-supply path on the en_US family.
  - `render/template_caps.py` + `doctor` disclose a **capability matrix** (which
    locales render a metrics/Impact line).
  - `render` **warns on a no-op config** — when `project_metrics` is set but the
    active locale's template won't render it, telling you to weave numbers into the
    bullets instead. No more undiscoverable capability cliff between locales.

## [0.27.0] — 2026-05-30

### Added

- **Stage-state + failure disclosure** (#64):
  - **`status` per-stage freshness** — shows extract / aggregate / enrich / render
    ages + a verdict ("enrich is newer than aggregate — reuse it" vs "re-run
    enrich"), so the costliest re-run decision no longer needs `ls -lt`.
  - **`doctor` PDF-engine preflight** — checks pandoc + xelatex and, when xelatex
    is installed but off PATH, discloses the exact fix (`PATH="/Library/TeX/texbin:$PATH"`).
  - **`render` no longer fails PDF silently** — a dropped PDF now surfaces the
    xelatex fix hint and an explicit `✗ PDF NOT produced` line instead of a buried
    warning behind an exit-0 success.

## [0.26.0] — 2026-05-30

### Added

- **`review` disclosure** (#63):
  - **Newer-variant warning** — when `review` auto-selects by persona/locale, a
    variant suffix (e.g. `_detailed`) could make the glob miss the file you just
    rendered and silently score an older one. It now warns when a higher-versioned
    same-locale render exists, naming it and pointing to `--file`.
  - **`review --by-bullet`** — per-failing-bullet diagnostics (which check each
    in-scope bullet missed: `no-metric` / `not-verb-first` / `ai-no-human-gate`),
    pointing at `evidence` for truthful fixes. Turns a dead-end aggregate score
    into an actionable gap list.

## [0.25.0] — 2026-05-30

### Added

- **Context-based metric classification + grounded iterate suggestions** (#62, P0).
  `iterate` previously surfaced bare metric tokens, forcing an agent to blindly
  insert them (a fabrication risk) or run extra `evidence` calls to ground each.
  `evidence.classify_metric` now uses each candidate's surrounding context to
  separate a `real_metric` from noise (`ui_threshold` confidence-band %, `css_value`,
  `model_spec` like "1M context", `url_fragment`) and grades a confidence tier
  (commit-confirmed > mentioned). `unsurfaced_metrics` returns only
  `safe_to_surface` candidates, and `iterate` inlines the value + context snippet
  + provenance + `kind`/`confidence` per suggestion — turning the in-code
  "never fabricate" guardrail into a signal the driving agent can see and act on.

## [0.24.1] — 2026-05-30

### Fixed

- **Corrected the #60 quota-pool framing + added real 429 mitigation** (#61).
  #60 defaulted subagent fan-outs to Sonnet on the claim that Sonnet's pool
  "protects the orchestrator budget" — but the 429s observed on wide fan-outs
  were **per-minute rate limits tripped by uncapped concurrency**, which hit
  regardless of tier or remaining weekly quota. (Sonnet *does* have a separate
  **weekly** pool with more headroom, so the Sonnet default stays — the framing,
  not the default, was the bug.) Fixes:
  - `enricher._call_claude` now **retries on 429 with exponential backoff honoring
    `retry-after`** — the actual fix for the failure mode.
  - `core/agents.py` (docstring + `FANOUT_CONCURRENCY = 5`), `config.agents`, and
    the `scan` next-step hint are corrected: tier choice selects *which weekly
    pool* you draw from; **capping concurrency + backoff** — not tier choice — is
    what prevents 429s. Process fan-outs in small batches.
  - Purely operational; truthfulness/human-in-the-loop untouched (#51).

## [0.24.0] — 2026-05-30

### Added

- **Configurable subagent model tier across fan-outs** (#60) — tool-spawned
  subagent fan-outs (codebase scan #59, subprocess enrich) now pick their model
  tier by **quota-pool isolation + sufficiency**, not a hardcoded cheapest.
  `core/agents.py::resolve_subagent_model` resolves: `--subagent-model` flag >
  per-command `config.<cmd>.subagent_model` > `config.agents.subagent_model` >
  default **sonnet** (so an Opus orchestrator's budget isn't exhausted by a large
  fan-out; Sonnet→Sonnet stays; Haiku only when explicitly chosen). Honored by
  `enrich --mode subprocess` (`claude -p --model`) and surfaced in `scan`'s
  next-step hint. Purely operational — truthfulness/human-in-the-loop untouched (#51).

## [0.23.0] — 2026-05-30

### Added

- **`vibe-resume scan` — opt-in codebase scan per project** (#59). Activity says
  *what the user did*; the code says *what the project is*. For each group with a
  resolvable local `path`, the CLI gathers a **bounded, redacted** slice (README,
  manifests, top-level tree — skips vendored/build dirs, caps files+bytes, drops
  secret-bearing lines, runs profile redactors, honors `privacy.blocklist`) and
  emits a per-project prompt for a **cheaper-model subagent** (one per project,
  parallel) to summarize; `scan --ingest` persists structured grounding
  (`{purpose, concrete_features, confirmed_tech, entrypoints}`) that enrich
  injects (`CODEBASE_GROUNDING_BLOCK`). Describes **only what the code shows**
  ("couldn't determine" is valid), never uploads code, never invents (P1).

## [0.22.1] — 2026-05-30

### Fixed

- **Metric-candidate noise in `evidence` / `iterate`** (#58) — the bare-integer
  branch of the metric detector surfaced calendar dates, IP octets, ports,
  PR/issue numbers, and long ID/phone-like digit runs as "candidate metrics".
  The disclosure layer now keeps only impact-shaped quantities (%, multiplier,
  magnitude k/M/B, time units, currency, CJK units) and drops bare integers —
  a precision refinement that speeds the human-confirm step and removes the
  privacy-adjacent long-digit runs. Not a score lever; no auto-surfacing (#51
  unchanged).

## [0.22.0] — 2026-05-30

### Added

- **`vibe-resume iterate` — truth-preserving score-driven auto-iterate** (#57,
  capstone of the truthfulness epic; opt-in, dry-run by default). Tightens the
  page budget — the only deterministic, truth-preserving lever — to lift the
  review grade, then **stops at the bar (grade B) or honestly reports the ceiling**
  ("page-count" / "genuine content gap") rather than distorting to pass. It
  **never rewrites a bullet, invents a metric, or inserts a human gate** to chase
  points. The edits that need rewriting — surface present-but-omitted keywords
  (#54), strengthen real human-gate framing (#56), add real unsurfaced metrics
  (#53) — are emitted as **human-applied-only suggestions sourced from the
  disclosed evidence**, each traceable to a real signal (P1.5 + P1.6).

## [0.21.0] — 2026-05-30

### Added

- **`render --variants` multi-variant render** (#55) — one command emits the
  standard variant set per locale: an **ATS** variant (page-budgeted, ~2 pages,
  for broad applications) and a **detailed** variant (richer, for
  interviews/portfolio), with `_ats` / `_detailed` filename suffixes. All
  variants derive from the **same truthful enriched cache** — they differ only
  in selection/length/framing, never in claims (P1.4); a shorter variant never
  states anything the detailed one wouldn't. Config-overridable via
  `config.render.variants`.

## [0.20.0] — 2026-05-30

### Changed

- **Agentic persona bakes in the human-gate pairing** (#56) — the `agentic`
  persona's enrich directive now leads/closes an AI bullet with the real
  human-verification step (locale-appropriate phrasing) by default, lifting the
  AI-proficiency signal (#47) without a manual prompt — **but only when the
  activity actually shows the candidate reviewed/verified/audited the output.**
  Never boilerplate-inserted to pass the checker; if there's no real gate, the
  bullet doesn't claim one and a lower score is the honest outcome (P1.2).

## [0.19.0] — 2026-05-30

### Added

- **Evidence gap reconciliation** on the disclosure layer, surfaced by
  `vibe-resume evidence` (`--jd` / `--json`):
  - **Present-but-omitted JD keywords** (#54) — `keyword_gap` splits a JD's
    keywords into *backed-by-signals-but-not-in-bullets* (a recall gap to
    surface) vs *genuinely absent* (an honest gap to leave). Never stuffs a
    keyword the activity doesn't support (P1.3).
  - **Unsurfaced real metrics** (#53) — `unsurfaced_metrics` lists numbers
    literally present in the activity but not yet in the bullets, as
    human-confirm suggestions. Never invents or estimates a metric; a bullet
    with no real number stays qualitative (P1.1).

## [0.18.0] — 2026-05-30

### Added

- **`render --max-pages` page budget** (#52) — hit a page target by tightening
  *bullet density* (achievements per group, highest-signal first), not only by
  dropping whole projects via `--top-n`; the two compose. Also
  `config.render.page_budget`. The greedy fitter never goes below 2 bullets/group
  and **never pads or over-claims** — if the floor is reached it keeps the honest
  content and lets the page-count check surface the residual (P1.4 guardrail).
  `estimate_pages` is now a shared helper in `core/review.py`.

## [0.17.0] — 2026-05-30

### Added

- **Score-is-a-proxy principle + evidence-disclosure layer** (#51) — the north
  star for the truthfulness epic. `docs/PRINCIPLES.md` states P1 (the review
  score is advisory; 6 Goodhart guardrails — no fabrication, real human gates,
  evidence-backed keywords, non-distorting condensing, honest auto-iterate stop,
  auditability) and P2 (disclosure over opacity).
- **`core/evidence.py` + `vibe-resume evidence`** — discloses, per project group,
  the *real* signals behind every enrich/review/iterate decision: candidate
  metrics literally present (never invented), terms genuinely backed by the data,
  where a human gate actually appears (locale-aware), and provenance. Lets an
  agent self-mine what it needs to see and makes every later surfacing traceable
  to a disclosed signal. `--json` for agent consumption, `--group` to filter.
  The shared locale-aware `gate_terms` now lives in `core/rubric.py`.

## [0.16.1] — 2026-05-30

### Fixed

- **AI-proficiency review check was English-only** (#50) — `human_gate_verbs`
  matched the "AI bullet paired with a human quality gate" signal only in
  English, so a correctly-framed non-English résumé (zh/ja/ko/de/fr) scored
  **AI proficiency 0/10** and was falsely flagged as a bare tool name-drop, even
  when every AI bullet explicitly paired a tool with human verification. The
  rubric now carries `human_gate_verbs_by_locale`; `review` unions the English
  base list with the active locale's phrasing (e.g. 人工把關 / 複核 / 審查 for
  `zh_*`, レビュー / 検証 for `ja_JP`, geprüft / verifiziert for `de_DE`) so the
  headline senior-vs-junior signal is scored fairly across all 10 shipped locales.

## [0.16.0] — 2026-05-29

### Added

- **Research / market-refresh pass** (`vibe-resume research`, #46) — an opt-in
  step that keeps the AI-proficiency rubric (#47) current with the AI-hiring
  market without ever fabricating numbers. It mirrors the proven enrich
  emit → session-processes → ingest flow:
  - `vibe-resume research` writes a cited-research prompt (`data/research/
    research.prompt.md`) that fans out across recruiter criteria, senior-vs-junior
    signals, ATS keyword sets, credible metric *ranges*, and current yellow-flag
    anti-patterns — and **adversarially verifies** each claim, killing ungrounded
    hype that lacks a citation.
  - `vibe-resume research --ingest` strictly validates the session's result and
    installs `data/cache/market_rubric.yaml` (the #47 loader override). **A rubric
    with no `sources` is rejected** — no un-sourced framing is ever installed; a
    bad-regex yellow-flag is dropped with a warning rather than aborting.
  - `vibe-resume research --status` shows the active rubric date + staleness.
- **Staleness surfacing** — `enrich` (emit) prints a refresh hint and `review`
  appends one to the AI-proficiency check once the active rubric ages past the
  180-day threshold. Informational only — no score impact.
- **Hard constraint preserved** — the research prompt forbids writing metric
  *values* into bullets; ranges are for sanity-checking / flagging only.

## [0.15.0] — 2026-05-29

### Added

- **AI-proficiency rubric** (#47) — a bundled, cited, dated `market_rubric.yaml`
  (winning-bullet formula, senior differentiators, anti-patterns, agentic
  keyword set, regex yellow-flags, and metric hints) now drives both generation
  and scoring, so output stops plateauing at "uses AI" framing.
  - **enrich** — a gated `AI_PROFICIENCY_BLOCK` injects the formula
    (*directing verb + named tool + scale + measurable delta + human quality
    gate*), senior differentiators, and junior-tell anti-patterns into the LLM
    prompt — but only when the group carries agentic signals (#43/#44/#45/#48),
    the agentic persona is active, or the emphasis mentions AI. Non-fabrication
    rule preserved.
  - **review** — two new scorecard checks: a positive **AI proficiency** check
    (rewards AI bullets that pair a tool with a human quality gate) and a
    negative **AI framing red flags** check (junior volume-bragging, stale-stack
    headline, unverified-judge claim, bare tool name-drop). Both self-skip
    (`max=0`) when the résumé has no AI content, so non-AI résumés keep their
    denominator and scores stay comparable across versions.
  - **metric guidance, not fabrication** — a number-less AI bullet gets a
    *pointer* to a real metric to measure (review round-trips, first-pass QA %,
    token-cost %, eval task-completion) — never an injected value.
- The rubric loader prefers a `data/cache/market_rubric.yaml` override when
  present, wiring it forward for the #46 research/market-refresh pass with zero
  rework.

## [0.14.0] — 2026-05-29

### Added

- **Installed-toolkit extractor** (`installed_env`, opt-in, #45) — inventories
  the configured agentic toolkit: Claude Code plugins
  (`~/.claude/plugins/installed_plugins.json`), standalone Agent Skills
  (`~/.claude/skills/<name>/`), and configured MCP servers (`mcpServers` in
  `~/.claude.json` / settings / Claude Desktop config). Emits one synthetic
  "Agentic Toolkit" group (exempt from the noise filter) that the enricher
  frames as installed/curated — distinct from authored and used (#43).
  **Privacy-critical: only names + coarse transport are captured — never MCP
  `env`/`args`/`url` values — and names run through `redact_patterns`.**

## [0.13.0] — 2026-05-29

### Added

- **Multi-agent orchestration signal** (`AgenticSignals.orchestration`, #48) —
  detects subagents, parallel fan-out, supervisor/worker, fan-out→verify
  pipelines, workflow scripts, and Agent SDK usage as distinct pattern tags
  (from activity text + `skills_used`), instead of folding them into a generic
  `agent-tooling %`. The enricher surfaces the topology — flagging a
  verification/judge stage as a senior signal. Completes the competency-signal
  set (tools #43 · methodology #44 · process #48).

## [0.12.0] — 2026-05-29

### Added

- **SDD / TDD methodology signal** (`AgenticSignals.sdd` / `.tdd`, #44) —
  detects Spec-Driven Development (OpenSpec / Spec-Kit / `specs/<feature>/`
  trees / spec-kit artifacts) and Test-Driven Development (test-driven /
  red-green / failing-test-first), distinct from mere test presence. The
  enricher surfaces these as methodology bullets.

### Fixed

- **Bare `spec` no longer mis-books spec-driven work as testing** (#44). The
  classifier TESTING regex dropped the bare `\bspec\b` token (kept `.spec.` /
  `_spec` / `tests`), so `spec.md` / `specs/` / OpenSpec stop inflating the
  `testing %` and instead feed the new SDD signal.

## [0.11.0] — 2026-05-29

### Added

- **Agent Skills + MCP competency signal** (`AgenticSignals` on each project
  group, #43) — distinguishes **authoring** from **usage**: skills authored
  (from `SKILL.md` / `skills/<name>/` / plugin manifests, with a published
  flag), skills used (from session `Base directory for this skill:` markers),
  MCP servers integrated (from `mcp__<server>__` tool calls), and a
  conservative MCP-authoring flag. The enricher now appends a factual agentic-
  signals hint so bullets can foreground this Tier-1 agentic competency instead
  of collapsing it into a generic `agent-tooling %`. First of the competency-
  signal epic; shared `AgenticSignals` surface extended by later releases.

## [0.10.2] — 2026-05-29

### Fixed

- **`curate --apply` no longer drops same-named groups (data loss)** (#41).
  `apply_curation` keyed lookups by group name, so applying a `needs_decision`
  merge of a same-named twin sent both groups to the merge-source bucket and
  neither to survivors — silently deleting the kept project. It now pairs
  groups with entries positionally and resolves merge targets to a specific
  surviving group object (preferring the canonical-keyed anchor), so exactly
  one group survives carrying both groups' activities.
- **`load_groups` curated-cache lookup is now anchored to `GROUPS_PATH`** (#42).
  The curated path is derived via `GROUPS_PATH.with_name(...)` at call time
  instead of a standalone constant, so monkeypatching `GROUPS_PATH` redirects
  it too and the suite stays hermetic on machines with a real curated cache.

## [0.10.1] — 2026-05-29

### Fixed

- **Canonical-key merge no longer labels the merged project with a
  version/cache folder** (#39). Representative-path selection prefers a
  meaningful basename (not `0.2.0` / a plugin-cache path), then a work-tree
  toplevel, then the most-seen path; falls back to the repo basename from the
  git remote when every candidate leaf is meaningless. Since merging inflates
  the session count, the affected project is often the highest-ranked one.
- **`curate` `needs_decision` now fires for same-name/no-remote duplicates**
  (#40). The classifier self-excluded by name, which also dropped a same-named
  twin from the candidate set; it now self-excludes by identity and prefers a
  canonical-keyed sibling as the merge anchor, so a no-remote copy folds into
  the proven repo group instead of both being silently kept.

## [0.10.0] — 2026-05-29

### Added

- **`emphasis` lever** — `vibe-resume emphasis "<intent>"` writes an editable
  `_emphasis.yaml` (intent / keywords / bias_instruction / spotlight / demote)
  that re-shapes output to a chosen focus (#38). `enrich` injects it as the
  highest-priority bias block; `render` boosts `spotlight` groups into the
  detailed top-N and sinks `demote` groups to one-liners. Depth is implicit:
  re-run `render` for a light re-rank (no LLM) or `enrich` for a deep
  bias-rewrite. Hand-edited keywords/spotlight/demote carry forward when the
  intent changes; `--no-emphasis` / `emphasis --clear` disable it. New
  `emphasis:` config block. Completes #38 (the curate gate shipped in 0.9.0).

## [0.9.0] — 2026-05-29

### Added

- **`curate` gate** — a file-based human-in-the-loop checkpoint between
  `aggregate` and `enrich` (#38). `vibe-resume curate` writes an editable
  `_curation.yaml` classifying every project group into `auto_merge` /
  `auto_drop` / `needs_decision` / `keep` with evidence; `curate --apply`
  executes keep/merge_into/drop into a non-destructive
  `_project_groups.curated.json` that `enrich`/`render` prefer. Human
  decisions carry forward across re-runs (keyed by canonical identity);
  headless runs apply only the high-confidence auto tiers. New `curate:`
  config block (`enabled`, `noise_globs`).
- Merge **provenance** on `ProjectGroup` (`canonical_key` / `merged_from` /
  `merge_evidence`): the #37 cross-path auto-merge is now traceable in
  `_project_groups.json` instead of silently rewriting paths.

## [0.8.0] — 2026-05-29

### Changed

- **Same logical repo worked from multiple paths now collapses into one
  project group** (#37). Extractors capture each path's normalized git
  `origin` remote + work-tree toplevel (`git_remote` / `git_toplevel` in
  `Activity.extra`); the aggregator derives an identity-proven canonical
  key (remote → toplevel) and rewrites duplicate groups onto one
  representative path. Fixes double-counted projects from clones, renamed
  dirs, and sub-package working directories. Merges only on proven identity
  — unrelated same-named repos (different remote) stay separate.

### Added

- `extractors/base.py::git_identity(path, cache)` helper + `_normalize_remote`
  — shared, memoized git-remote/toplevel resolver (reused by the upcoming
  #38 curate gate).

## [0.7.0] — 2026-05-29

### Added

- **GitHub PR/issue extractor** (`extractors/local/github.py`, #34): pulls the
  author's PRs/issues + own review-thread comments via `gh` CLI (no token
  handling). Detects owned vs external (open-source) contributions; external
  merged PRs are exempt from the noise filter and framed as "contributed to".
  New `github:` config block (disabled by default).
- `sessions:` config block (`sample_prompts`, `per_prompt_chars`,
  `capture_tool_args`, `keep_assistant`) shared by conversation extractors.
- `enrich.input_activities` / `enrich.input_char_budget` config to widen the
  LLM input window (was hard-coded 12 activities / 200 chars).

### Changed

- git extractor now captures commit **bodies** (`%b`) and touched **file
  paths**, not just subjects (#35).
- claude_code / codex extractors spread-sample prompts across the session
  timeline (deduped) instead of keeping only the first ~8, and can keep a
  sample of tool-call arguments (#35).
- claude.ai export retains assistant responses (#35).

### Fixed

- `PrivacyFilter` now redacts string elements inside `list` values in
  `extra` (review comments / tool args), closing a redaction gap.

## [0.6.3] — 2026-05-28

### Fixed

- **#33: duplicate-named project groups collided on `enrich --ingest`.**
  Ingest matched each manifest entry's YAML back to a raw group **by name**,
  so two same-named groups (e.g. a git-only + a codex-only variant of one
  project) resolved to the same object — one group's enriched
  `summary`/`achievements` was silently overwritten (ended up `[]`). Ingest
  now matches by the manifest entry's **index** (`id`), which `emit_jobs`
  assigns over the raw group list — a stable, collision-free key. Added
  name-mismatch + index-out-of-range warnings to surface the "aggregate
  re-run since emit" divergent-set case instead of silently misattaching.
  `emit_jobs` status carry-forward is now keyed by `output_path` (unique)
  rather than name.

### Added / changed (render polish — #36)

- **Configurable detailed-project count.** `render --top-n N` /
  `config.render.detailed_projects` replaces the hardcoded `top_n = 6` in
  every locale template (was a hand-edit to produce a detailed résumé).
- **Composite project ranking.** Ordering now scores
  `sessions + achievements×5 + breadth×2` (descending) instead of favouring
  `capability_breadth`, so a focused high-session project is no longer
  buried under broad-but-shallow work.
- **ID-only CLI group names humanized.** Groups surfacing as `gemini:<hex>`
  now derive a readable name (path basename, or `<source> session <short>`)
  instead of leaking the session id as the project title.
- **Empty education/cert `year` no longer renders `()` / `（）`** — paren
  output is guarded across all locale templates (ASCII + full-width).

## [0.6.2] — 2026-05-28

### Fixed

- **#30 [P0 regression]: stale `templates_dir` crashed `render` after the
  0.6.0 src/ move.** `config.example.yaml` still shipped
  `render.templates_dir: "./render/templates"`, a path that no longer exists
  (templates moved into `src/vibe_resume/render/templates/`). Because
  `load_config` bootstraps `config.yaml` from the example, new users hit
  `TemplateNotFound` on their first `render`. Fix: removed the stale knob from
  the example, and `_render_md` now verifies a configured `templates_dir`
  actually contains templates — falling back to the bundled package templates
  with a warning instead of crashing. `render.templates_dir` is now an
  optional override; templates ship inside the package.

- **#31: `run --formats md,docx,pdf` exploded each format into its own
  version.** Phase B iterated formats as a matrix axis, so a 2-locale run
  produced 6 versions (each carrying only one format). `render_draft` now
  accepts a comma-list of formats and emits them all against ONE version;
  `run` Phase B makes a single render call per (locale, persona) cell.
  `render -f all` / `-f md` string forms still work.

- **#32: `trend` crashed (`TypeError: None < str`) on mixed persona history.**
  Default grouping is `(locale, persona)` since #15; `sorted()` couldn't
  order `None` (persona-less early runs) against `"agentic"` etc. Sort key is
  now None-safe (`persona or ""`); persona-less rows display as `(default)`.

## [0.6.1] — 2026-05-28

### Fixed (test infrastructure)

- **#27 regression guard never actually executed (#29).** The two
  console-script guards added in 0.5.1 invoked `uv run python -m vibe_resume`
  with `cwd=tmp_path`. `uv` walks up from the cwd for a `pyproject.toml`,
  finds none in a pytest temp dir, and falls back to an ad-hoc interpreter
  with no `vibe_resume` installed → `No module named vibe_resume` before any
  `ROOT`-resolution code runs. The guard proved nothing and was red/flaky
  depending on inherited shell env. Switched to `sys.executable -m
  vibe_resume`: the pytest interpreter has `vibe_resume`, `python -m`
  resolves it from `sys.path`, and `cwd=tmp_path` still exercises the
  CWD-based `ROOT` logic — which is the whole point. Confirmed the guard now
  *fails* if `user_root()` is reverted to install-dir resolution, so the #27
  regression finally has a guard with teeth.

  Product behaviour unchanged — this is a test-only fix; 0.6.0's shipped code
  was already correct.

## [0.6.0] — 2026-05-28

### Changed (packaging — #18 root cause)

- **Moved to a `src/vibe_resume/` single-package layout.** 0.5.x shipped
  `core` / `render` / `extractors` / `cli` as four **top-level** packages in
  the wheel — generic names that collide with other packages in any shared
  venv. The 0.5.0 `force-include cli.py` hack (#18) only made `uv tool
  install`'s *isolated* venv tolerate the pollution; it didn't fix the
  structure. Now everything lives under one `vibe_resume` top-level package,
  so a shared-venv `pip install vibe-resume` no longer squats on those names.
  This also makes the #27-class bug (top-level `cli.py` + `Path(__file__)`)
  structurally impossible.

  **Pure refactor — no behaviour change.** All 595 tests pass unchanged.

  **What this means for invocation:**
  - `uv run vibe-resume <cmd>` — **unchanged** (entry point still works)
  - `python -m vibe_resume <cmd>` — **new** module form
  - `python cli.py <cmd>` — **removed** (cli.py is no longer top-level);
    use one of the two forms above
  - Entry point is now `vibe_resume.cli:cli`; the `force-include` packaging
    hack is gone.

  Bundled templates + the 70 company-profile YAMLs moved with the package and
  still resolve package-relative; `core/paths.py::user_root()` (the 0.5.1 #27
  fix) still keeps user data (`data/`, `profile.yaml`, `config.yaml`) anchored
  to the working directory.

## [0.5.1] — 2026-05-28

### Fixed (P0 regression)

- **`ROOT` resolved to the install dir, not the user's working tree (#27).**
  0.5.0's wheel packaging (#18) put the package in `site-packages`, so the
  `vibe-resume` console script computed `ROOT = Path(__file__).parent` →
  `site-packages`, breaking every `ROOT / "data/..."` path. `doctor` and
  `review-diff` failed out of the box; `review`/`trend`/`run` were affected
  whenever invoked via the installed script from a normal CWD.

  **Root-cause fix (not a patch):** `ROOT` conflated two path domains —
  *user data* (`data/`, `profile.yaml`, `config.yaml`, which belong in the
  CWD like git) and *package resources* (bundled templates, company-profile
  YAML, the version string, which ship inside the install). New
  `core/paths.py::user_root()` is the single CWD-based source of truth
  (`VIBE_RESUME_ROOT` still overrides), replacing 7 duplicated
  `Path(__file__)` expressions. Bundled templates now resolve
  package-relative; `doctor` reads the version via `importlib.metadata`.
  A console-script-equivalent smoke test (runs the CLI from a foreign CWD)
  guards against recurrence — the one configuration 0.5.0's CI never
  exercised.

## [0.5.0] — 2026-05-28

Issue-driven release closing 25 issues filed against 0.4.0 (one declined).
No breaking changes — all additive or bug fixes.

### Fixed (P0)

- **review: persona+locale resolution (#2).** `review --persona X --locale Y`
  without `--file/--version` now globs `resume_v*_<locale>[_<persona>].md`
  and scores the highest matching version instead of silently scoring the
  lexically-latest file (which previously overwrote N−1 results in a batch).
- **review: DOB false positive (#3).** The "full DOB in header" red flag
  required only a bare ISO date in the first 14 lines, so summary /
  target-role / experience-start dates triggered a phantom −2 on every
  en_US/en_GB render. Now requires an explicit DOB / Date of birth / Born /
  生年月日 / 出生 label adjacent to the date. (The en_US template never
  rendered `profile.dob` — the bug was entirely in the reviewer's scanner.)
- **render: filename locale suffix (#4).** en_US renders dropped the locale
  suffix (`resume_v006_tech_lead.md`) while other locales kept it, breaking
  `resume_v*_en_US_*.md` globs. Every render now uses
  `resume_v<NNN>_<locale>[_<persona>].md` uniformly.

### Added

- **`vibe-resume run` orchestrator (#10).** One command for multi-persona ×
  multi-locale pipelines. Phase A: extract + aggregate (if cache stale) +
  enrich emit across the matrix, then stops for session processing. Phase B
  (`--continue`): ingest --all + render matrix + review matrix + trend.
  No auto-dispatch — preserves the session-quota model.
- **`vibe-resume jd-check` (#23).** Reports JD-keyword coverage across
  enriched bullets without a full render+review round. `--threshold` filters
  to under-covered keywords.
- **`vibe-resume review-diff <vA> <vB>` (#26).** Per-check scorecard delta
  between two résumé versions.
- **`vibe-resume doctor` (#19).** Diagnoses CLI/plugin version drift,
  profile/config presence, optional-dep (pandoc/claude) availability.
- **Agentic Engineer persona (#22).** `--persona agentic` — 2026 AI-agent
  narrative (agent loops, MCP, RAG triad, eval harness) with a Head-of-AI
  reviewer lens and keyword-echo-weighted scoring.
- **`enrich --tailor-keywords / --tailor-keywords-cap / --tailor-keywords-strict` (#7).**
  Manual keyword overrides; override terms always lead the merged set.
- **`enrich --ingest --all` (#9).** Walks every (persona, locale) under
  `data/enrich_jobs/` and ingests each; comma-separated persona ingest too.
- **`enrich --status` + `--ingest --all-ready` (#12).** Progress table across
  job dirs; batch-ingest only the complete ones.
- **`enrich --clean` (#20).** Clears stale `*.yaml` on re-emit; a warning
  fires when old yaml survives a re-emit without `--clean`.
- **`render --all-locales --persona X,Y,Z` matrix (#11).** Persona-list
  expansion across all locales.
- **`status --enriched / --pending / --all` (#25).** Cache-state views per
  (persona, locale) and pending job progress.
- **Profile-derived redaction (#24).** `derive_profile_redactors` auto-builds
  name/email patterns from `profile.yaml` (incl. locale name variants) and
  scrubs bullets at ingest, regardless of which invocation path ran.
- **Manifest JD provenance (#8).** Emit records the JD's sha256 + mtime +
  extracted keywords; ingest warns when the JD file changed since emit.
- **Persona-specific review weights (#16).** `review --persona` now reweights
  the 8-point scorecard (e.g. tech_lead weights metrics 1.5×, page-count
  0.7×) and normalises back to the same scale, not just appends a lens note.
- **Per-locale page-count targets + gradual scoring (#14).** ja_JP=1.0,
  de_DE/fr_FR=2.5, others=2.0; 4-band scoring (10/8/5/2) replaces the
  10→5 cliff.
- **Trend grouped by (locale, persona) (#15).** Default grouping splits
  apples-vs-oranges persona runs; `--group-by` + `--persona`/`--locale`
  filters.
- **render warns when `profile.summary` empty (#13)** — surfaces the −4
  top-fold penalty before it lands.
- **`uv tool install` support (#18).** Wheel now force-includes `cli.py` so
  `uv tool install git+…` puts `vibe-resume` on PATH. (No `src/` restructure —
  tracked separately if desired.)

### Docs

- SKILL.md documents the `--level` axis in the main Procedure + Quick
  Reference (#6); `personas-compare` quick-ref notes the `--locale`
  requirement since 0.4.0 (#5).
- New `references/tailor-keyword-extraction.md` explains the two-pass
  extractor + 12-keyword cap rationale (#21).

### Closed without code

- **#1** (list in awesome-codex-plugins) — declined; discovery is via
  skills.sh + Claude Code / Codex marketplaces.
- **#17** (plugin gitCommitSha drift) — upstream Claude Code behaviour, not
  a vibe-resume bug; workaround documented; the work-tree drift we *can*
  detect ships as `doctor` (#19).

## [0.4.0] — 2026-05-28

### Breaking changes

- **`enrich` default mode changed.** Was: spawn `claude -p` per group
  (billed against Anthropic Agent SDK quota pool as of 2026-06-15).
  Now: emit `*.prompt.md` files to `data/enrich_jobs/<persona>/<locale>/`
  for the current Claude Code session to process (uses subscription
  quota). Process the prompts in your session, then run
  `vibe-resume enrich --ingest --locale <L>` to merge the YAML back.
  CI / non-interactive: opt back into the old path with
  `--mode subprocess` (the CLI prints a red warning explaining the
  billing implication). Background:
  https://codersera.com/blog/anthropic-june-2026-billing-change-claude-code/

- **Enriched cache is now per-locale.** The cache file
  `_project_groups.<persona>.json` became
  `_project_groups.<persona-or-default>.<locale>.json`. This eliminates
  the previous hazard where `enrich --locale zh_TW` then
  `enrich --locale en_US` would overwrite each other.

  **Migration:**
  ```bash
  rm data/cache/_project_groups.*.json   # delete 0.3.x enriched caches
  uv run vibe-resume enrich --locale <L>  # re-run for each locale you need
  uv run vibe-resume enrich --ingest --locale <L>
  ```

- **`company verify` mirrored the same three-mode pattern.** Default
  emits prompt + manifest to `data/verification_jobs/<key>_<date>/`;
  session writes `report.md`; `verify --ingest <key>` finalises it.
  `--mode subprocess` keeps the old `claude -p` behaviour.

- **`personas-compare` now requires `--locale`** (cache is per-locale).

### Added

- `core/enrich_jobs.py` — `EnrichJobManifest` + `emit_jobs` + `ingest_jobs`
- `data/enrich_jobs/` and `data/verification_jobs/` working-directory
  layout (both gitignored)
- `tests/fixtures/enrich_jobs_sample/` — reference manifest + prompt + yaml
  so new contributors can see the schema shape (the live working dir is
  gitignored)
- New test suites: `test_enrich_jobs.py`, `test_per_locale_cache.py`,
  `test_cli_enrich_modes.py`, `test_company_verify_jobs.py`

### Verified

- No sensitive data ever entered git history (audit covered `profile.yaml`,
  `data/cache/*`, `data/resume_history/*`, `data/reviews/*`, secret
  patterns, credential file extensions). Historical `config.yaml` content
  was example-grade with no PII.

## [Unreleased]

### Added (on `main`, not yet tagged)
- **`cli.py trend`** — per-locale review score history with ASCII
  sparkline, mean %, and grade of latest run.
- **`cli.py render --all-locales`** batch mode + `config.render.all_locales_formats`
  to control which formats fan out per locale (default `["md"]`).
- **Locale resolution chain** on renderer: CLI `--locale` >
  `profile.preferred_locale` > `config.render.locale` > `en_US`.
- **JD tokenizer hardening** (`core.review.parse_jd_keywords`): prefers
  known tech names (`_JD_TECH_PRIORITY`), skips structural noise
  (`_JD_STOPWORDS`); keyword echo went 10/12 → 12/12 on the sample JD.
- 18 additional unit tests (41 total now) — parse_jd_keywords /
  find_previous_review / ReviewReport.grade boundaries / _pick_template /
  _build_prompt across en_US, zh_TW, zh_CN, ja_JP, de_DE.
- **`en_EU` locale** — Europass-styled English CV. Labelled Personal
  information list (not a centered strip), Occupation/Employer fields
  under each experience block (matches Europass XML schema labels),
  CEFR languages section, GDPR-minimal personal data.
- **Shell completions** — `cli.py completion {bash,zsh,fish}` prints a
  completion snippet (or `--install` appends it to the right rc file
  with a sentinel-bracketed block so a re-run is idempotent). Makes
  `vibe-resume render --locale <tab>` expand across the 10 locales.
- **`zh_HK` locale** — Hong Kong bilingual CV. Section headings pair
  English + 繁體中文 ("Personal Profile 個人簡介" / "Work Experience
  工作經驗") so one document works for Cantonese- and English-speaking
  reviewers in one pass. Photo optional; HKID intentionally never
  emitted; CEFR-style language-proficiency section.
- **Windows backup** — `scripts/backup_claude_projects.ps1`
  (PowerShell 7, robocopy `/MIR /XO` mirror + dated snapshot) +
  `scripts/vibe-resume-backup.xml` Task Scheduler import template.
  The PS1 is smoke-testable via `pwsh -WhatIf` on macOS/Linux,
  statically checked by `PSScriptAnalyzer`, and exercised by a
  `windows-latest` matrix job in CI so a Windows box is not needed
  to maintain it.
- **`cli.py enrich --tailor JD.txt`** — injects `parse_jd_keywords`
  output into the enrich prompt as a "Tailor hint" block so
  achievements surface JD keywords verbatim when the raw activity
  supports them (explicit "never invent a match" rule). Verified on
  `rag-search-platform`: non-tailor run produced metric-rich but
  keyword-neutral bullets; tailor run surfaced FastAPI / pgvector /
  Next.js / TypeScript / Docker / AWS verbatim and added `RAG` to
  `tech_stack`.
- README: `trend` / `render --all-locales` / locale resolution chain /
  `enrich --tailor` sections.

### Verified (on top of the 0.1 list)
- `cli.py enrich --locale ko_KR -n 1` → native Korean output
  (풀스택 엔지니어, 설계·배포, 구현, 단축), tech nouns stay English
  (FastAPI / pgvector / Next.js / Docker / AWS / Claude Code).
- `cli.py enrich --locale zh_CN -n 1` → all Simplified Chinese
  (全栈工程师, 设计, 构建, 部署, 重构, 修复), zero Traditional-only
  character leak.

### Verified
- Enrichment prompt dispatch produces **native output** in every
  noun-phrase locale we ran end-to-end with `claude -p`:
  - zh_TW: 「設計並部署基於 FastAPI 與 pgvector 的 RAG 搜尋平台…」
  - ja_JP: 「FastAPIとpgvectorを核にRAG検索基盤を設計し…」 *(headline 「フルスタック + DevOps」, no 简体 leakage)*
  - de_DE: 「Full-Stack-Engineer für RAG-Suchplattform mit FastAPI…」
  - fr_FR: 「Ingénieur full-stack sur plateforme RAG Python/FastAPI…」
  - Tech nouns (FastAPI, PostgreSQL, Next.js) stay English per the
    prompt rule; metric numbers from source data flow through unchanged.

### Planned for v0.2

- **More locales**: `en_SG` (NRIC-aware). *(`en_EU` and `zh_HK` done above.)*
- **`cli.py render --tailor` + review `--jd`** integrated into a single "target" object (one JD passed once, used everywhere).
- **PDF cover page**: optional one-page hero summary before the main resume (`render.cover_page: true`); useful for de_DE Lebenslauf + JP 履歴書 bundles.
- **Extractor hardening**: real-sample validation for Grok / Perplexity / Mistral / Poe cloud exports — schemas are currently lenient-parsed.
- **JP 履歴書 legacy cells**: optional 通勤時間 / 扶養家族 / 配偶者 cells (some traditional employers still expect these).
- **Prompt coverage**: verify ko_KR / zh_CN LLM output end-to-end (same way we verified zh_TW/ja_JP/de_DE/fr_FR in 0.1).

## [0.3.0] — 2026-04-22

Three new native CLI-session extractors + Codex plugin marketplace
distribution. Published fresh tarball so `npx skills add …` and
`skills.sh` registries pick up the new extractors and corrected install
instructions.

### Added

- **Codex CLI extractor** (`extractors/local/codex.py`) — reads
  `~/.codex/sessions/**/rollout-*.jsonl` **and**
  `~/.codex/archived_sessions/*.jsonl`. Session-UUID dedup across the
  two trees. Emits one `Activity` per session with `cwd`, `git.branch`,
  `cli_version`, user-prompt count, function-call count, file paths.
  Registered as `Source.CODEX`. 5 unit tests.
- **Gemini CLI extractor** (`extractors/local/gemini_cli.py`) — reads
  `~/.gemini/tmp/<project_hash>/chats/session-*.json` (rich) **and**
  `~/.gemini/tmp/<project_hash>/logs.json` (fallback). Session-ID
  dedup across the two shapes; skips `bin/` helper dir and malformed
  JSON silently. Registered as `Source.GEMINI_CLI`. 3 unit tests.
- **Copilot CLI extractor** (`extractors/local/copilot_cli.py`) — reads
  `~/.copilot/session-state/<uuid>/events.jsonl`. Parses
  `session.start` (sessionId, cwd, copilotVersion, producer),
  `user.message`, `assistant.message` with `toolRequests` (tool-call
  count + file-path extraction), `session.shutdown`. Registered as
  `Source.COPILOT_CLI`. Separate from `copilot_vscode`. 3 unit tests.
- **Claude Code plugin marketplace** —
  `.claude-plugin/marketplace.json` lets users run
  `/plugin marketplace add easyvibecoding/vibe-resume` and install
  via the standard two-step flow.
- **OpenAI Codex plugin marketplace** —
  `.codex-plugin/marketplace.json` mirrors the Claude Code pattern
  so `codex plugin marketplace add easyvibecoding/vibe-resume` works
  on codex-cli ≥ 0.121.0.
- **Codex plugin `interface` object** in `.codex-plugin/plugin.json`
  (displayName, shortDescription, longDescription, capabilities,
  URLs, defaultPrompt × 3, brandColor) so the marketplace listing
  renders a full card, not a placeholder.
- **`scripts/validate_plugin_e2e.sh`** — JSON parse → shared manifest
  invariants → Codex publish-readiness → marketplace installability
  → `claude plugin validate` in one pass.
- `test_codex_plugin_manifest_publish_readiness` and
  `test_marketplace_manifests_installable` guard both marketplace
  manifests and the Codex interface schema.

### Changed

- READMEs (en / zh-TW / zh-CN / ja) Tier 0 section: replaced the
  invalid `/plugin install <owner>/<repo>` shorthand with the correct
  two-step flow, and added the codex-cli ≥ 0.121 version floor with
  a Tier 1 fallback pointer for older installs.
- `core/runner.py::LOCAL_EXTRACTORS` grew to 14 entries
  (`codex`, `gemini_cli`, `copilot_cli` added).
- `config.example.yaml` gained `codex` (with `archived_path`),
  `gemini_cli`, and `copilot_cli` stanzas.

## [0.1.0] — 2026-04-20

First public-ready cut: end-to-end pipeline from AI-tool extractors through
LLM enrichment to multi-locale rendering, plus an automated reviewer audit.

### Added

- **Local extractors** (11): Claude Code · Claude Code Archive · Cursor ·
  Cline · Continue.dev · Aider · Windsurf / Cascade · Copilot (VS Code) ·
  Zed · Claude Desktop (config + extensions) · `git` commits filtered by
  author email.
- **Cloud export importers** (7): ChatGPT · Claude.ai · Gemini Takeout ·
  Grok · Perplexity · Mistral · Poe (drop ZIPs into `data/imports/<tool>/`).
- **AIGC extractors** (6): ComfyUI / A1111 PNG metadata · Midjourney IPTC ·
  ElevenLabs · Suno · Runway · HeyGen.
- **Aggregation pipeline**: 18-category bilingual task classifier,
  capability-breadth ranking, 30-day rolling window stats, project grouping
  with significance ranking.
- **LLM enrichment** (`core/enricher.py`): headless `claude -p` invocation
  with two prompt shapes —
  - `style="xyz"` (en_US / en_GB) — Google XYZ action-verb bullets
  - `style="noun_phrase"` (zh / ja / de / fr / ko) — fact-first noun-phrase
    bullets with explicit anti-leak rules so a Japanese `role_label` cannot
    drift to `全栈` instead of `フルスタック`.
  `--limit N` now preserves out-of-window groups instead of overwriting
  them with a fallback summary.
- **Multi-locale rendering** with 9 templates:
  | Locale | Template | Notable specifics |
  |---|---|---|
  | `en_US` | `resume.en_US.md.j2` | ATS-friendly flat skills line, XYZ verbs |
  | `en_GB` | `resume.en_GB.md.j2` | UK spellings, `Personal statement` heading, CEFR languages |
  | `zh_TW` | `resume.zh_TW.md.j2` | 繁中 noun-phrase, 兩行 contact, `localized()` field fallback |
  | `zh_CN` | `resume.zh_CN.md.j2` | 简体, 大厂友善 default (no photo / 政治面貌) |
  | `ja_JP` | `resume.ja_JP.md.j2` (職務経歴書) + `render/japan.py` (履歴書 DOCX grid, JIS Z 8303) |
  | `ko_KR` | `resume.ko_KR.md.j2` | 이력서 sections; 자기소개서 left as separate doc |
  | `de_DE` | `resume.de_DE.md.j2` | `Persönliche Daten` block; renders `dob` / `nationality` when set |
  | `fr_FR` | `resume.fr_FR.md.j2` | Profil / Compétences / Expérience / Centres d'intérêt |
  | (default) | `resume.md.j2` | locale-agnostic fallback when no `.<locale>.j2` exists |
- **i18n machinery** (`render/i18n.py`):
  - `LOCALES` dict captures per-locale style / photo rule / personal-field list / heading labels / date format / filename style.
  - `format_date(value, locale)` Jinja filter — handles ISO inputs, "Present"-style tokens (normalized per language), and CJK literal patterns like `%Y年%m月`.
  - `localized(obj, key, locale)` Jinja filter — reads `<key>_<locale>` when set, falls back to canonical key (powered by `UserProfile.model_config = ConfigDict(extra="allow")`).
- **Profile schema** (`core/schema.py`): formal optional fields for
  `dob` / `gender` / `nationality` / `marital_status` / `mil_service` /
  `photo_path`. Locale templates only emit them when the active locale's
  `personal_fields` list includes them and the value is set.
- **DOCX rendering**:
  - Photo-expected locales (`de_DE`, `ko_KR`) use an invisible 1×2 layout
    table so the photo sits in the true top-right next to the
    name/title/contacts block.
  - `ja_JP` is dispatched to `render/japan.py` which emits a JIS-style
    履歴書 with photo cell, ふりがな row, 学歴・職歴 grid, 免許・資格,
    志望動機 sections.
- **PDF rendering**: pandoc + XeLaTeX with CJK font, falls back to plain
  pandoc if XeLaTeX is missing.
- **Reviewer audit** (`core/review.py`, `cli.py review`): 8-point scorecard
  (top fold · numbers per bullet · keyword echo (JD) · action-verb first ·
  density · red flags · contact-line width · page-count estimate). Outputs
  human + JSON scorecards, with `--diff` to show Δ vs the previous review
  of the same locale and line-number examples for non-conforming bullets.
- **Versioning** (`core/versioning.py`): every render commits a snapshot
  to an internal git repo at `data/resume_history/`, with
  `cli.py list-versions` and `cli.py diff` for navigation.
- **Privacy filter** (`core/privacy.py`): regex redaction of API keys /
  emails / passwords; project blocklist; optional tech-name abstraction.
- **Claude Code agent skill**: `.claude/skills/ai-used-resume/SKILL.md`
  ships an in-Claude entry point.
- **Backup script**: `scripts/backup_claude_projects.sh` rsync-backs
  `~/.claude/projects` so the 30-day cleanup window doesn't erase history.
- **Docs**: `docs/resume_locales.md` (per-region research, decision matrix,
  reviewer-view checklist) and `docs/review_v007.md` (worked example
  scorecard from the first end-to-end run).

### Known limits

- Full `$HOME` git scan takes 1–3 min on first run; switch to
  `scan.mode: whitelist` for faster iteration.
- `claude_desktop` extractor only sees MCP config + extensions; chat
  contents are encrypted in Local Storage.
- Grok / Perplexity / Mistral cloud exports are lenient-parsed (no
  official schema); drop a real sample into `data/imports/<tool>/` if a
  field doesn't map.
- `ja_JP` 履歴書 grid covers core JIS cells but skips legacy
  通勤時間 / 扶養家族 / 印鑑欄.
