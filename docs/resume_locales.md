# Resume locales — regional conventions & template matrix

> Decision reference for `vibe-resume` multi-locale rendering. Every row here
> maps to a `render/templates/resume.<locale>.md.j2` variant and a DOCX style
> preset in `render/renderer.py`.

Sources consulted: US BLS / Harvard FAS / Oxford Careers / DIHK (Germany) /
APEC (France) / MHLW 履歴書 JIS Z 8303 / Saramin (Korea) / 前程無憂 (CN) /
104.com.tw (TW) / JobsDB (HK) / MyCareersFuture (SG). Last reviewed
2026-04-20. Hiring conventions drift slowly but not zero — re-check yearly.

---

## 0. The universal invariants (all locales)

1. **One résumé = one target role.** Tailoring beats length.
2. **Never fabricate metrics.** If the raw activity has no number, keep a
   qualitative outcome (our `enricher.py` prompt already enforces this).
3. **ATS-safe formatting where ATS exists (US / UK / SG / DE enterprise).**
   No tables, no text boxes, no headers/footers, standard section names,
   single-column only in the machine-readable copy.
4. **Filename convention**: `FirstLast_Role_Locale_YYYYMM.pdf`.
   Recruiters grep filenames, not folders.

---

## 1. United States (`en_US`) — the ATS baseline

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 1 page (≤5 yrs exp) / 2 pages max               |
| Photo                  | **Never** (EEOC discrimination risk)            |
| Personal data          | Name, city+state, email, phone, LinkedIn/GitHub only. No DOB, marital status, nationality, photo. |
| Section order          | Summary → Skills → Experience → Projects → Education → (Certs) |
| Voice                  | Past-tense action verbs, XYZ bullets, em-dash OK |
| Keyword density        | ATS parsers expect the literal phrase from the JD. Canonicalize: "PostgreSQL" not "postgres". |
| Dates                  | "Aug 2019 – Jun 2021"                           |
| Reviewer attention     | ≈6–8 seconds on top fold. Name → title → 1st bullet of most recent role. |
| Red flags              | Photo; objective statement; "references on request"; >2 pages for <10yrs. |

Template note: this is the **default** produced by today's
`resume.md.j2`, with one tweak — move `Summary` above `AI-assisted workflow
overview` so the top fold is human-readable, not stat-heavy.

---

## 2. United Kingdom & Ireland (`en_GB`)

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 2 pages standard                                |
| Photo                  | **No** (Equality Act 2010)                      |
| Personal data          | Name, city, email, phone. DOB optional but falling out of favour. |
| Section order          | Personal statement → Skills → Experience → Education → Interests |
| Voice                  | Past-tense action verbs; UK spelling (organise, optimise) |
| Dates                  | "August 2019 – June 2021" or "08/2019"          |
| Reviewer attention     | Similar 6–8s; slightly more weight on education |
| Red flags              | US spelling; 1-pager for senior role (looks thin in UK). |

Diff from `en_US`: UK spelling in templates, `Personal statement` label
instead of `Summary`, include `Interests` section if relevant.

---

## 3. Europass / EU-wide English (`en_EU`)

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 2–3 pages                                        |
| Photo                  | Optional (common in DE/FR/IT/ES, rare in NL/SE/IE) |
| Personal data          | Minimized per GDPR — name, email, phone, LinkedIn. |
| Section order          | Personal info → Work experience → Education → Skills → Languages (CEFR A1–C2) |
| Voice                  | Neutral, fact-first                             |
| Language proficiency   | Must use CEFR scale; "fluent" is not acceptable |
| Red flags              | Missing CEFR; missing "Work experience" heading verbatim. |

Template note: the `languages` field in `profile.yaml` should optionally
accept CEFR (e.g. `"English (C1)"`).

---

## 4. Germany (`de_DE`) — Lebenslauf

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 1–2 pages (Lebenslauf) + Anschreiben + Zeugnisse |
| Photo                  | De facto expected (AGG allows candidates to opt-out, but ≥80% include) |
| Personal data          | Full address, DOB, nationality, marital status still common (legally optional since 2006). |
| Section order          | Persönliche Daten → Berufserfahrung → Ausbildung → Kenntnisse → Hobbys |
| Voice                  | Noun-heavy, factual, no marketing verbs        |
| Dates                  | "08/2019 – 06/2021", reverse chronological     |
| Zeugnisse              | Scanned certificates/references typically attached as a single PDF bundle. Not optional at senior level. |
| Reviewer attention     | Reviewer reads top-to-bottom linearly; structure matters more than hooks. |
| Red flags              | Missing photo at non-tech firms; missing Zeugnisse; English-only CV for in-country role. |

Template delta: rename all headings to German, add `geburtsdatum` and
`nationalität` fields to profile schema as optional, swap XYZ bullets for
noun-phrase lines.

---

## 5. France (`fr_FR`) — CV

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 1 page (junior/mid) / 2 pages (senior)          |
| Photo                  | Common but optional; declining                  |
| Personal data          | Name, city, email, phone; DOB optional         |
| Section order          | État civil → Expérience professionnelle → Formation → Compétences → Langues → Centres d'intérêt |
| Voice                  | Past-tense, concise, elegant; avoid anglicisms where French equivalent exists |
| Dates                  | "août 2019 – juin 2021"                         |
| Red flags              | Long narrative summaries; missing `Centres d'intérêt`. |

---

## 6. Japan (`ja_JP`) — 履歴書 + 職務経歴書

This is the **structurally unique** locale — it's not a résumé with
different headings, it's **two separate documents**.

### 6a. 履歴書 (rirekisho) — JIS Z 8303 standard form
| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Format                 | Fixed-grid A4 form (JIS standard or MHLW 2021 revision). Must be table-rendered. |
| Photo                  | Required, 縦 40mm × 横 30mm, suit, plain background. |
| Personal data          | 氏名(ふりがな), 生年月日, 年齢, 性別(任意), 住所(ふりがな), 電話, email, 顔写真, 印鑑欄 (some forms). |
| Sections               | 学歴 (chronological, not reverse), 職歴, 免許・資格, 志望動機・特技, 本人希望記入欄 |
| Voice                  | 丁寧語 + です/ます or noun-form; absolutely no bullet points |
| Red flags              | Using a resume-style Word layout instead of a grid form; omitting 志望動機. |

### 6b. 職務経歴書 (shokumu keirekisho) — work history narrative
| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 2–3 pages                                        |
| Style                  | Prose-first, then per-project tables            |
| Order                  | 職務要約 (summary) → 職務経歴 (reverse chronological) → 活かせる経験・知識・スキル → 自己PR |
| Voice                  | Noun-final, understated; "~を担当しました" > "~をリードしました". Overclaiming is a negative signal. |

Template delta: Japan needs **two** templates and a DOCX renderer that
outputs a table-based layout, not a flowing markdown document. This is the
largest engineering investment of all locales.

---

## 7. Korea (`ko_KR`) — 이력서 + 자기소개서

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Format                 | Standard form (Saramin/JobKorea template) + 자기소개서 (self-intro essay, 3–5 sections × 500–1000자 each) |
| Photo                  | Required, 3×4cm, formal                         |
| Personal data          | Name (Hangul + Hanja + English), RRN last 6 masked, DOB, 주소, family (increasingly omitted), 병역 for male candidates |
| Sections               | 인적사항 → 학력 → 경력 → 자격증 → 어학능력 → 수상 |
| 자기소개서 prompts      | 지원동기, 성장과정, 성격의 장단점, 입사후 포부 (varies by employer) |
| Red flags              | English-only for domestic Korean firms; skipping 자기소개서. |

---

## 8. Mainland China (`zh_CN`) — 简历

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 1–2 pages                                        |
| Photo                  | Common, especially outside top-tier tech       |
| Personal data          | Name, DOB, 籍贯, 政治面貌 (党员/群众), 婚姻 for senior roles, photo. |
| Section order          | 个人信息 → 教育背景 → 工作经历 → 项目经验 → 专业技能 → 获奖 |
| Voice                  | Noun phrases, past-tense, quantified           |
| Big-tech subset (字节/阿里/腾讯/美团) | Much closer to US style: no photo, no 政治面貌, English résumé bilingual. |
| Red flags              | Using `zh_TW` vocabulary (软体 vs 軟體, 服务器 vs 伺服器) in mainland applications. |

---

## 9. Taiwan (`zh_TW`) — 履歷

| Dimension              | Convention                                      |
|------------------------|-------------------------------------------------|
| Length                 | 1–2 pages (tech) / 2–3 (traditional)            |
| Photo                  | Common in traditional industries; optional in tech |
| Personal data          | Name, 生日, 性別, 地址, 電話, email, 兵役狀態 (male). |
| Section order          | 個人資料 → 學歷 → 工作經驗 → 專案作品 → 技能 → 語言能力 |
| Voice                  | Noun-phrase past tense; mix of English tech terms allowed |
| Platform defaults      | 104.com.tw auto-generates a form; Yourator / CakeResume favour US-style narrative |
| Red flags              | Simplified Chinese characters; 繁體/簡體 混用. |

---

## 10. Hong Kong (`zh_HK` / `en_HK`) & Singapore (`en_SG`) — bilingual hubs

- **HK**: Bilingual EN+繁體中文, 1–2 pages, no photo for MNCs, photo common in local SMEs.
- **SG**: English primary, NRIC last 4 masked, no photo, 2 pages standard, LinkedIn URL near-mandatory.

---

## Decision matrix — which dimensions actually differ

| Dimension          | Varies across locales? | Handle in template | Handle in profile.yaml | Handle in renderer |
|--------------------|:---:|:---:|:---:|:---:|
| Section ordering   | ✅ | ✅ | — | — |
| Heading labels     | ✅ | ✅ (i18n strings file) | — | — |
| Photo              | ✅ | ✅ | `profile.photo_path` | DOCX: embed image cell |
| DOB / nationality  | ✅ | ✅ | `profile.dob`, `profile.nationality` (optional) | — |
| Tone (XYZ vs noun) | ✅ | ✅ (prompt template switch) | — | `enricher.py` locale-aware prompt |
| Grid form (JP)     | ✅ | — | — | **Custom DOCX template** |
| CEFR languages     | partial | ✅ | `profile.languages` accepts CEFR | — |
| Filename pattern   | ✅ | — | — | ✅ |

---

## Implementation plan (downstream of this doc)

1. **Template registry** — add `LOCALES = {"en_US", "en_GB", "en_EU",
   "de_DE", "fr_FR", "ja_JP", "ko_KR", "zh_CN", "zh_TW", "zh_HK", "en_SG"}`
   and drop per-locale `.j2` files. Fall back to `resume.md.j2` if missing.
2. **Profile schema additions** (Pydantic-additive, backwards compatible):
   `dob`, `nationality`, `photo_path`, `marital_status`, `mil_service`.
   None required — only rendered when the selected locale expects them.
3. **Enricher prompt variants** — two prompt styles:
   - `style="xyz"` (US/UK/SG) — action-verb + metric
   - `style="noun_phrase"` (JP/DE/CN/TW) — fact-first, understated
   Switched by the target locale.
4. **CLI flag** — `vibe-resume render --locale ja_JP --style shokumu` and
   `--locale zh_TW`. Default resolves from `profile.yaml:preferred_locale`.
5. **Japan is a separate sub-project** — grid-based DOCX rendering is not a
   Jinja template, plan a dedicated `render/japan.py` using
   `python-docx` tables.
6. **Filename template** — make configurable:
   `render.filename_template: "{last}_{first}_{role_slug}_{locale}_{yyyymm}"`.

## Reviewer-view checklist (what a hiring screener actually grades)

For any locale, run the final PDF through this 6-point check:

1. **Top fold (first 1/3 of page 1)**: name, target role, 1 concrete
   outcome. If reviewer stops here, do they know *what you ship*?
2. **Numbers per bullet**: aim ≥60% of bullets carry a metric. Zero-metric
   bullets accumulate below the fold only.
3. **Keyword echo**: the top 8 nouns of the target JD should appear
   verbatim in Skills + Experience. Run `rg -io "<keyword>" resume.md`.
4. **Action-verb first** (for XYZ locales): every experience bullet starts
   with a verb in the past tense. No "Responsible for…".
5. **Density** (for noun-phrase locales): each bullet is self-sufficient,
   no pronouns referring to the previous bullet.
6. **Red-flag scan**: no photo where the locale forbids it; no DOB where
   the locale forbids it; no typos in proper nouns (company/product).

These 6 points become `core/review.py::score(resume_md, locale) -> ReviewReport`
in a later task.
