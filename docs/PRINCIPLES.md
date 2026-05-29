# Principles

## P1 — The review score is a proxy, never the objective (#51, north star)

The review scorecard is a **proxy** for "does this résumé truthfully and effectively
represent a strong engineer" — not the objective itself. Every feature that touches
`enrich` / `review` / `render` / any score-driven loop MUST treat the score as
**advisory** and MUST NOT trade away truthfulness or genuine human-in-the-loop for
points.

### Non-negotiables (Goodhart guardrails)

1. **No fabrication, ever.** Numbers, frameworks, metrics, skills, MCP servers,
   methodologies must be grounded in real extracted activity. If a metric doesn't
   exist, the bullet stays qualitative — a lower `numbers-per-bullet` score is the
   *correct* outcome, not an invented number.
2. **Human-gate phrasing must reflect reality.** Surfacing "經人工把關 / human-verified"
   is allowed only when the activity actually shows the user reviewed/verified. Never
   boilerplate-insert it to pass the AI-proficiency check.
3. **Keyword surfacing requires evidence.** Only surface a JD keyword genuinely present
   in the user's signals. Never echo a JD keyword the activity doesn't support.
4. **Condensing must not distort.** Length/page reduction drops the *least
   representative* content; it must not drop inconvenient truths, over-claim what
   remains, or pad.
5. **Auto-iteration stops honestly.** A score-driven loop must stop and report when it
   cannot reach the bar *truthfully*, rather than inflating. The loop optimizes
   *framing of true facts*, never the facts.
6. **Auditability.** Every automated rewrite keeps a trace (what changed, from which
   real signal) so a human can verify nothing was invented.

### How this is enforced

- Each enhancement that touches the score carries an **"Alignment guardrail"** section
  in its spec, consistent with P1, and at least one test asserting the guardrail
  (e.g. "no number appears that isn't in the source activity").
- `tests/test_alignment_guardrails.py` collects the cross-cutting invariants.

## P2 — Disclosure over opacity: let the agent see and self-mine the real signals

vibe-resume is an Agent Skill as much as a CLI. The consuming agent (and the human)
must be able to **see what the tool sees** — the raw, real signals behind every
enrich/review/iterate decision — and **self-mine** them, rather than trusting an opaque
heuristic.

Concretely: the **evidence-disclosure layer** (`core/evidence.py`, surfaced by
`vibe-resume evidence`) discloses, per project group, the *real* signals available —
candidate metrics actually present in the activity, terms genuinely backed by the data,
where a human gate actually appears, and provenance for each. Features that surface
metrics (#53), reconcile keywords (#54), frame human gates (#56), or auto-iterate (#57)
**read from this disclosure** so every change is traceable to a disclosed real signal
(satisfying P1.6). The agent digs out what it needs to see; nothing is invented behind
its back.
