# Resume reviewer audit — v007 (en_US) & v008 (zh_TW)

Subject: `Alex Chen`, Taipei, targeting "Senior Full-stack / AI Platform Engineer".
Artifacts audited:
- `data/resume_history/resume_v007.md` (en_US ATS template)
- `data/resume_history/resume_v008_zh_TW.md` (繁中版)
Scored against the 6-point checklist at the end of `docs/resume_locales.md`.

---

## v007 · en_US ATS — score 44 / 50

| # | Check                          | Score | Evidence |
|---|--------------------------------|:-----:|----------|
| 1 | Top fold (name+role+outcome)   | 9/10  | Lines 1–11 fit in first 1/3 of page 1. Name + title + contacts + target role + 4-line summary with a concrete metric (~40% cycle-time cut). **Nit:** first summary word is "Full-stack engineer…"; leading with the outcome ("Compressed design-to-deploy by ~40% across…") would pull a skimming reviewer deeper. |
| 2 | Numbers per bullet             | 10/10 | 8/8 Experience bullets carry a metric; 15/16 Project achievements carry a metric (93%). Far above the ≥60% bar. |
| 3 | Keyword echo (ATS parse)       | 9/10  | Skills line is a flat comma-list (line 14) — ATS-ideal. Canonical spellings used: PostgreSQL, Next.js, TypeScript, pgvector, GitHub Actions. **Nit:** `Claude Code SDK` is not a standard JD phrase; consider adding "AI coding agents", "LLM agent tooling" as additional keywords when tailoring. |
| 4 | Action-verb first              | 10/10 | Every Experience bullet starts with Led / Built / Owned / Shipped / Introduced / Refactored. Every Project achievement starts with Reduced / Lifted / Shipped / Cut / Designed / Increased / Integrated / Removed / Reached. Zero "Responsible for…". |
| 5 | Density (noun-phrase locale)   |  n/a  | Not applicable to en_US. |
| 6 | Red-flag scan                  | 6/10  | No photo ✅, no DOB ✅, no "References available upon request" ✅. **Issues:** (a) dates are `2024-02 – Present` instead of the ATS-preferred `Feb 2024 – Present`; (b) `## Awards` / `## Talks` have no blank line between the trailing list item and the next heading (lines 79–80); (c) the AI-assisted overview paragraph (line 37) is a 400-char single line that will wrap awkwardly in some ATS preview panes. |

### Top-3 actionable fixes (en_US)
1. **Date formatter** — add a Jinja filter `locale_date(iso_str, locale)` that maps `2024-02` → `Feb 2024` for `en_US/en_GB`, `2024/02` for `zh_TW`, `2024年02月` for `ja_JP`. Fix in `render/i18n.py::format_date(iso, locale)` and use across templates.
2. **Blank-line discipline** — the `custom_sections` block in `resume.en_US.md.j2` still emits consecutive `##` headings without a separator. Wrap each subsection in its own `{% if %}...{% endif %}` + trailing blank line.
3. **Lead with the outcome in Summary** — either reorder the first sentence in `profile.yaml`, or have the enricher post-process `profile.summary` into a metric-leading variant when locale.style == "xyz".

---

## v008 · zh_TW — score 38 / 50

| # | Check                          | Score | Evidence |
|---|--------------------------------|:-----:|----------|
| 1 | Top fold                       | 7/10  | Contact line is one dense stream separated by `　|　`; three URLs dominate the header. Consider splitting into two lines (一行 email/phone/location，另一行 LinkedIn/GitHub). |
| 2 | Numbers per bullet             | 10/10 | Same English bullets, same metric density. |
| 3 | Keyword echo                   | 8/10  | `技能專長` now grouped by category (Frontend/Backend/Database/DevOps/Other) — good for human scanning, weaker for ATS (台灣 ATS 較少，但 104 / Yourator 仍有簡單 parser)。Supply a flat fallback list below the grouped list for future. |
| 4 | Action-verb first              |  n/a  | zh_TW locale is `style=noun_phrase`; the bullets we render are still English (inherited from profile.yaml). **Blocker:** we have no Chinese translation pipeline. |
| 5 | Density                        | 5/10  | Each project block renders: `### N. name — headline` + stats line + stack + domain + achievements. Self-sufficient — passes. But the embedded English prose mixes poorly with Chinese headings, creating an uncanny valley for a Taiwan reviewer. |
| 6 | Red-flag scan                  | 8/10  | No photo (locale allows either); headings use 繁體 throughout, no 簡體 leakage detected. **Issues:** (a) `2024-02-14` ISO dates instead of `2024/02`; (b) `## 獲獎紀錄` / `## 演講 / 分享` / `## 興趣` are back-to-back with no blank lines; (c) English bullets below 繁體 headings feels inconsistent. |

### Top-3 actionable fixes (zh_TW)
1. **Per-locale bullet translation** — extend `profile.yaml` to allow parallel language keys:
   ```yaml
   experience:
     - title: "Senior Full-stack Engineer"
       title_zh_TW: "資深全端工程師"
       bullets:
         - "Led AI-augmented delivery..."
       bullets_zh_TW:
         - "主導 AI 協作的 RAG 搜尋交付..."
   ```
   Falls back to the default key when the localized one is missing. Template reads `e.get("bullets_" + locale) or e.bullets`.
2. **Bilingual enricher prompt** — add a `--lang zh_TW` branch in `core/enricher.py`'s prompt that asks for 繁體中文 noun-phrase bullets when the target locale is Chinese.
3. **Date localization** — same `format_date` filter as en_US fix #1.

---

## Cross-cutting findings (both locales)

| Issue | Severity | Root cause | Fix location |
|-------|:--------:|------------|--------------|
| Dates render as `2024-02` (ISO prefix slice)                          | med | Templates slice `first_activity[:7]` / profile `start` as-is | `render/i18n.py::format_date` + template use |
| Consecutive `##` headings with no blank line (awards/talks/hobbies)   | low | Loop body missing trailing blank | Both templates |
| Single long AI-overview paragraph (~400 chars)                         | low | Template design choice | Break into 2 lines or a list |
| English content under 繁中 headings                                     | high (zh_TW only) | No translation pipeline    | profile.yaml localized fields + enricher |
| No page-break hint for PDF rendering                                  | low | Template is locale-agnostic Markdown | Add `\\pagebreak` or pandoc-aware comment in templates |

## Recommended next actions (ordered)

1. **Add `format_date` Jinja filter in `render/i18n.py`** — 30-min change, unblocks both locale polish items.
2. **Extend `profile.yaml` schema with `<field>_<locale>` fallback pattern** — touches `core/schema.py` + templates. Pattern: "canonical key wins when localized is empty; localized wins when present".
3. **Implement `core/review.py::score(resume_md, locale)`** — turn this manual audit into a CLI: `uv run python cli.py review --version 7`. Encode the 6-point checklist as regex + line-count heuristics; emit a scorecard JSON + markdown. This is what unlocks iterative self-evaluation.
4. **Enricher locale switch** — add `style="noun_phrase"` and `language` params to the prompt template in `core/enricher.py`; re-run enrichment against the test `_project_groups.json` to verify the zh_TW output actually looks Taiwan-native.
5. **Ship the remaining locale .j2 files** — `ja_JP` needs the biggest investment (grid-based 履歴書 is not a markdown template — see `docs/resume_locales.md` §6).
