# Tailor keyword extraction

`vibe-resume enrich --tailor <JD.txt>` injects up to **12 keywords** extracted
from the job-description file into every project group's enrich prompt as a
"Tailor hint" block, so the LLM biases bullets toward terms the JD actually
emphasises (e.g. "RAG" over generic "search stack" when the project supports it).

## Source

- Path passed via `--tailor` is read as plain UTF-8 text.
- No PDF/HTML/Word parsing — convert externally first if needed.

## Strategy (two-pass)

Implemented in `core.review.parse_jd_keywords` (`limit=12` by default).

### Pass 1 — Prioritised tech/framework dictionary

A curated list (`_JD_TECH_PRIORITY` in `src/vibe_resume/core/review.py`, ~150 entries:
React, FastAPI, LangChain, pgvector, AWS, GitHub Actions, …) is scanned
for **case-sensitive exact-word matches**. Hits are ordered by first
appearance in the JD. This pass runs to exhaustion or until 12 picks.

Why case-sensitive: avoids picking up `actions` (verb) when the JD means
GitHub `Actions`; treats `react` (verb) and `React` (framework) differently.

### Pass 2 — Capitalised fallback, stopword-filtered

If Pass 1 didn't fill the 12 slots, the JD is regex-scanned for
`\b[A-Z][A-Za-z0-9+./-]{1,}\b` tokens. Each candidate is rejected if it
appears in `_JD_STOPWORDS` (~100 entries: "About", "Remote", "Senior",
"Responsibilities", "Years", …) so structural noise stays out.

## Why 12

Prompt budget. The "Tailor hint" block lists keywords inline; with N project
groups × M models × multi-locale runs, more than 12 keywords starts
crowding the LLM's attention and reduces per-bullet quality. Empirically
12 lands well; not a hard architectural limit.

## Output

- Written verbatim into each manifest at
  `data/enrich_jobs/<persona>/<locale>/manifest.json::tailor_keywords[]`
- Injected into each prompt as a "Tailor hint" block — see
  `core.enricher.TAILOR_BLOCK_TEMPLATE`
- The LLM is instructed never to invent a match that isn't supported by
  the raw activity; "if `RAG` is listed and the project is a retrieval
  pipeline, prefer 'RAG' over 'search stack'" but it must not force
  unrelated keywords into unrelated projects.

## Debugging

Inspect what was extracted from any given JD:

```python
from pathlib import Path
from core.review import parse_jd_keywords
print(parse_jd_keywords(Path("data/imports/your_jd.txt")))
```

If a tech name you care about isn't showing up:

1. Check case-sensitivity — the dictionary expects `LangGraph`, not `langgraph`
2. Check `_JD_STOPWORDS` — if your tech name overlaps a structural word,
   add it to `_JD_TECH_PRIORITY` ahead of the stopword filter
3. Add it to `_JD_TECH_PRIORITY` if not present — short PR

## Related

- `references/strategic-resume.md` for the full axis matrix (`--tailor` ×
  `--persona` × `--level` × `--company`)
