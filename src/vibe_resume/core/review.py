"""Automated reviewer-view audit for a rendered resume.

Implements the 6-point checklist documented at the end of
`docs/resume_locales.md`. Inputs: a rendered resume markdown string +
a locale key. Outputs: a `ReviewReport` with per-check scores (0-10) and
actionable notes. Also rendered as both JSON and a human-readable
markdown scorecard.

Heuristics, not ground truth: the goal is to catch the obvious misses
(bullets without metrics, forbidden photo tags, broken heading spacing)
so a user can fix them before showing the resume to a real reviewer.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vibe_resume.core.paths import user_root
from vibe_resume.core.rubric import load_rubric
from vibe_resume.render.i18n import get_locale, resolve_locale

ROOT = user_root()

# -- heuristics --------------------------------------------------------------

# Past-tense action verbs a US reviewer expects at the front of an XYZ bullet.
XYZ_VERBS: set[str] = {
    "accelerated", "architected", "authored", "automated", "built",
    "collaborated", "compressed", "consolidated", "created", "cut",
    "decoupled", "deployed", "designed", "developed", "delivered",
    "drove", "enabled", "enhanced", "established", "executed", "extended",
    "fixed", "generalized", "grew", "implemented", "improved", "increased",
    "initiated", "integrated", "introduced", "led", "lifted", "launched",
    "maintained", "managed", "mentored", "migrated", "modernized",
    "onboarded", "optimized", "orchestrated", "overhauled", "owned",
    "parallelized", "partnered", "pioneered", "prototyped", "published",
    "reached", "rebuilt", "reduced", "refactored", "released", "removed",
    "renovated", "replaced", "restored", "scaled", "secured", "shipped",
    "simplified", "slashed", "sped", "standardized", "streamlined",
    "supported", "transformed", "trimmed", "unblocked", "unified",
    "validated", "wrote",
}

# Pronouns a noun-phrase bullet should not start with (density check).
NOUN_PHRASE_PRONOUNS: set[str] = {
    "this", "that", "it", "these", "those",
    "他", "她", "它", "他們", "她們",
    "これ", "それ", "あれ",
    "이것", "그것", "저것",
    "dies", "das", "es",
    "ce", "cela", "ça",
}

# Regex for "carries a metric": %, ratios, durations, counts with K/M/B.
METRIC_RE = re.compile(
    r"(?<!\w)("
    r"\d+(?:\.\d+)?%"
    r"|\d+(?:\.\d+)?\s*(?:ms|s|min|hr|hrs|h|d|day|days|week|month|quarter|year)"
    r"|\d+(?:\.\d+)?\s*[xX]\b"
    r"|\d+(?:\.\d+)?\s*[kKmMbB](?:\+)?\b"
    r"|\d{2,}(?:,\d{3})*"  # bare integer ≥100 (e.g. "2M+", "1.2k", "9k views")
    r")"
)

# A CJK numeric-with-unit pattern, because "200 萬" or "35%" are valid.
CJK_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?(?:%|\s*萬|\s*億|\s*千|\s*倍|\s*個|\s*天|\s*小時|\s*週|\s*個月|\s*年|\s*萬人)"
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^[\s]*-\s+(.+?)\s*$", re.MULTILINE)
# Sections whose bullets are proper nouns / facts and should skip verb+metric checks
_IRRELEVANT_HEADS = {
    # English
    "awards", "talks", "hobbies", "interests", "certifications", "education",
    "languages", "technical skills", "skills", "digital skills",
    "personal information", "mother tongue and other languages",
    "education and training", "honours and awards", "conferences and publications",
    "additional information",
    # 繁中
    "獲獎紀錄", "獎項", "演講 / 分享", "演講", "興趣", "學歷", "證照", "語言",
    "技能專長", "專業技能", "技術能力", "語言能力",
    # 简中
    "获奖记录", "演讲", "兴趣", "教育背景", "证书", "专业技能", "语言能力",
    # 日本語
    "受賞歴", "登壇・発表", "趣味・特技", "学歴", "免許・資格",
    # 한국어
    "수상 내역", "발표 / 강연", "관심 분야", "학력", "자격증", "어학",
    # Deutsch
    "auszeichnungen", "vorträge", "interessen", "ausbildung", "zertifikate", "kenntnisse",
    "persönliche daten", "sprachen",
    # français
    "distinctions", "conférences", "centres d'intérêt", "formation", "certifications",
    "compétences", "langues", "état civil",
}


def _bullets_in_scope(md: str) -> list[tuple[int, str]]:
    """Return (1-indexed line, bullet text) from 'work content' sections only.

    Heading labels are compared lowercased + trimmed against `_IRRELEVANT_HEADS`.
    Everything before the first H2 is also in scope (contact/summary area).
    """
    current_head = ""
    bullets: list[tuple[int, str]] = []
    for i, ln in enumerate(md.splitlines(), start=1):
        m = re.match(r"^##\s+(.+?)\s*$", ln)
        if m:
            current_head = m.group(1).strip().lower()
            continue
        if current_head in _IRRELEVANT_HEADS:
            continue
        bm = re.match(r"^\s*-\s+(.+?)\s*$", ln)
        if bm:
            bullets.append((i, bm.group(1)))
    return bullets


def _example_lines(samples: list[tuple[int, str]], n: int = 2, trim: int = 70) -> str:
    """Format up to N (line, text) pairs as 'L42: \"text…\"; L88: \"…\"'."""
    out: list[str] = []
    for ln, txt in samples[:n]:
        snippet = txt.strip()
        if len(snippet) > trim:
            snippet = snippet[:trim].rstrip() + "…"
        out.append(f'L{ln}: "{snippet}"')
    return "; ".join(out)
# Red flags, compiled once
REFERENCES_RE = re.compile(r"references available upon request", re.IGNORECASE)
IMAGE_TAG_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
# DOB rows are universally prefixed with one of these labels — bare ISO dates
# in summary/target_role/experience-start fields must not trigger the flag.
DOB_RE = re.compile(
    r"\b(?:DOB|D\.O\.B\.|Date of birth|Born|生年月日|出生(?:日期|年月日)?)"
    r"\s*[:：]?\s*"
    r"(?:19|20)\d{2}[-/.](?:0?[1-9]|1[012])[-/.](?:0?[1-9]|[12]\d|3[01])\b",
    re.IGNORECASE,
)


# -- data types --------------------------------------------------------------

@dataclass
class Score:
    name: str
    score: int
    max: int
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewReport:
    source: str
    locale: str
    total: int
    max_total: int
    scores: list[Score]
    persona: str | None = None  # reviewer-persona key, if one was applied
    persona_tips: str | None = None  # human-readable advice from that persona
    # Strategic-résumé hooks — same shape as persona tips, but sourced from
    # the bundled CompanyProfile / LevelArchetype registries. Both are
    # purely additive to the markdown report; they do not change numeric
    # scoring. Adding scoring logic would require defining matcher rules per
    # must_haves / red_flags entry, which is left as a future iteration.
    company: str | None = None  # company key (e.g. "openai")
    company_label: str | None = None
    company_verified_at: str | None = None  # ISO date for staleness display
    company_tips: str | None = None  # full review_tips from CompanyProfile
    level: str | None = None  # level key (e.g. "senior")
    level_label: str | None = None
    level_tips: str | None = None  # full review_tips from LevelArchetype

    @property
    def grade(self) -> str:
        if self.max_total == 0:
            return "n/a"
        pct = self.total / self.max_total
        if pct >= 0.9:
            return "A"
        if pct >= 0.8:
            return "B"
        if pct >= 0.7:
            return "C"
        if pct >= 0.6:
            return "D"
        return "F"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "locale": self.locale,
            "total": self.total,
            "max_total": self.max_total,
            "grade": self.grade,
            "scores": [s.as_dict() for s in self.scores],
        }

    def as_markdown(self, previous: ReviewReport | None = None) -> str:
        delta_total = self.total - previous.total if previous else None
        delta_str = ""
        if previous:
            sign = "+" if delta_total >= 0 else ""
            delta_str = f"  ({sign}{delta_total} vs {previous.source})"
        lines = [
            f"# Resume review — {self.source}",
            "",
            f"Locale: **{self.locale}**　· Total: **{self.total}/{self.max_total}** ({self.grade}){delta_str}",
            "",
            "| Check | Score | Δ | Notes |" if previous else "| Check | Score | Notes |",
            "|-------|:-----:|:-:|-------|" if previous else "|-------|:-----:|-------|",
        ]
        prev_by_name = {s.name: s for s in previous.scores} if previous else {}
        for s in self.scores:
            notes = "; ".join(s.notes) if s.notes else "—"
            label = f"{s.score}/{s.max}" if s.max > 0 else "n/a"
            if previous:
                prev = prev_by_name.get(s.name)
                if prev and prev.max > 0 and s.max > 0:
                    diff = s.score - prev.score
                    if diff > 0:
                        delta_cell = f"**+{diff}**"
                    elif diff < 0:
                        delta_cell = f"**{diff}**"
                    else:
                        delta_cell = "·"
                else:
                    delta_cell = "·"
                lines.append(f"| {s.name} | {label} | {delta_cell} | {notes} |")
            else:
                lines.append(f"| {s.name} | {label} | {notes} |")
        if self.persona_tips:
            persona_label = self.persona or ""
            lines.append("")
            lines.append(f"### Reviewer lens — {persona_label}")
            lines.append("")
            lines.append(self.persona_tips)
        if self.level_tips:
            lines.append("")
            lines.append(f"### Career level — {self.level_label or self.level}")
            lines.append("")
            lines.append(self.level_tips)
        if self.company_tips:
            ver = (
                f" (profile last verified {self.company_verified_at})"
                if self.company_verified_at else ""
            )
            lines.append("")
            lines.append(
                f"### Target employer — {self.company_label or self.company}{ver}"
            )
            lines.append("")
            lines.append(self.company_tips)
        return "\n".join(lines) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewReport:
        return cls(
            source=data["source"],
            locale=data["locale"],
            total=data["total"],
            max_total=data["max_total"],
            scores=[Score(**s) for s in data["scores"]],
        )


# -- individual checks -------------------------------------------------------

def _count_metrics(text: str) -> int:
    return len(METRIC_RE.findall(text)) + len(CJK_METRIC_RE.findall(text))


def _check_top_fold(md: str) -> Score:
    """Name, title/target-role, and one concrete outcome in the first ~12 lines."""
    notes: list[str] = []
    head = "\n".join(md.splitlines()[:14])
    pts = 0
    # name present (H1)
    if re.search(r"^#\s+\S", head, re.MULTILINE):
        pts += 3
    else:
        notes.append("H1 name not found in top fold")
    # title or target role marker
    if re.search(r"target role|應徵職位|应聘岗位|志望職種|지원 직무|poste visé|zielposition|zielposition", head, re.IGNORECASE):
        pts += 3
    else:
        notes.append("no target-role line in top fold")
    # at least one concrete metric in head
    if _count_metrics(head) > 0:
        pts += 4
    else:
        notes.append("no measurable outcome visible in top fold — reviewer may stop scanning")
    return Score("Top fold", pts, 10, notes)


def _check_numbers_per_bullet(md: str) -> Score:
    """≥60% of bullets should carry a metric. Linear score up to that bar."""
    bullets = _bullets_in_scope(md)
    if not bullets:
        return Score("Numbers per bullet", 0, 10, ["no bullets detected"])
    missing = [(ln, txt) for ln, txt in bullets if _count_metrics(txt) == 0]
    with_metric = len(bullets) - len(missing)
    ratio = with_metric / len(bullets)
    pts = min(int(round(ratio / 0.6 * 10)), 10)
    notes = [f"{with_metric}/{len(bullets)} bullets carry a metric ({int(ratio * 100)}%)"]
    if ratio < 0.6:
        notes.append("target ≥60% — add metrics to top-of-list bullets first")
    if missing and pts < 10:
        notes.append("metric-less examples → " + _example_lines(missing))
    return Score("Numbers per bullet", pts, 10, notes)


def _check_keyword_echo(md: str, jd_keywords: list[str] | None) -> Score:
    """Echo of the JD's top nouns. Skipped (max=0) when no JD is supplied."""
    if not jd_keywords:
        return Score("Keyword echo (JD)", 0, 0, ["no JD supplied — skipped"])
    lower = md.lower()
    hit = [k for k in jd_keywords if k.lower() in lower]
    ratio = len(hit) / len(jd_keywords)
    pts = min(int(round(ratio * 10)), 10)
    miss = [k for k in jd_keywords if k.lower() not in lower][:5]
    notes = [f"{len(hit)}/{len(jd_keywords)} JD keywords present"]
    if miss:
        notes.append("missing: " + ", ".join(miss))
    return Score("Keyword echo (JD)", pts, 10, notes)


def _check_company_keyword_coverage(md: str, company: Any) -> Score:
    """Coverage of the target employer's curated keyword anchors.

    Complementary to JD keyword-echo: JD keywords are role-specific and
    extracted from the ad, while CompanyProfile.keyword_anchors are the
    stable hiring-bar vocabulary the employer's reviewers actually look
    for across roles (e.g. OpenAI expects PyTorch + distributed training +
    RLHF on most ML résumés, regardless of which team posted).

    Matching is substring + case-insensitive so CJK anchors like
    ``職務経歴書`` or ``카카오`` match naturally. Zero-keyword profiles
    (should not happen given loader validation) return max=0 to skip.
    """
    anchors = getattr(company, "keyword_anchors", None) or ()
    if not anchors:
        return Score(
            "Company keyword coverage",
            0,
            0,
            ["no company keyword_anchors — skipped"],
        )
    lower = md.lower()
    hit = [k for k in anchors if k.lower() in lower]
    ratio = len(hit) / len(anchors)
    pts = min(int(round(ratio * 10)), 10)
    miss = [k for k in anchors if k.lower() not in lower][:5]
    notes = [
        f"{len(hit)}/{len(anchors)} {company.label} keyword anchors present",
    ]
    if miss:
        notes.append("missing: " + ", ".join(miss))
    return Score("Company keyword coverage", pts, 10, notes)


def _check_action_verb(md: str, locale_meta: dict[str, Any]) -> Score:
    """XYZ-locale check: each experience bullet starts with a past-tense verb."""
    if locale_meta.get("style") != "xyz":
        return Score("Action-verb first", 0, 0, [f"n/a for style={locale_meta.get('style')}"])
    bullets = _bullets_in_scope(md)
    if not bullets:
        return Score("Action-verb first", 0, 10, ["no bullets detected"])
    bad: list[tuple[int, str]] = []
    bad_words: list[str] = []
    for ln, b in bullets:
        first = re.split(r"[\s,—\-:]", b.strip(), 1)[0].lower().strip("*_`")
        if first not in XYZ_VERBS:
            bad.append((ln, b))
            bad_words.append(first)
    ok = len(bullets) - len(bad)
    ratio = ok / len(bullets)
    pts = min(int(round(ratio * 10)), 10)
    notes = [f"{ok}/{len(bullets)} bullets start with a past-tense verb"]
    if bad:
        uniq_bad = sorted(set(bad_words))[:5]
        notes.append("non-verb openers: " + ", ".join(uniq_bad))
        notes.append("examples → " + _example_lines(bad))
    return Score("Action-verb first", pts, 10, notes)


def _check_density(md: str, locale_meta: dict[str, Any]) -> Score:
    """Noun-phrase-locale check: bullets do not open with a dangling pronoun."""
    if locale_meta.get("style") != "noun_phrase":
        return Score("Density (noun-phrase)", 0, 0, [f"n/a for style={locale_meta.get('style')}"])
    bullets = _bullets_in_scope(md)
    if not bullets:
        return Score("Density (noun-phrase)", 0, 10, ["no bullets detected"])
    dangling: list[tuple[int, str]] = []
    for ln, b in bullets:
        first = b.strip().split()[0].lower() if b.strip().split() else ""
        if first in NOUN_PHRASE_PRONOUNS:
            dangling.append((ln, b))
    ok = len(bullets) - len(dangling)
    ratio = ok / len(bullets)
    pts = min(int(round(ratio * 10)), 10)
    notes = [f"{ok}/{len(bullets)} bullets are self-sufficient (no dangling pronoun)"]
    if dangling:
        notes.append(f"{len(dangling)} bullets open with a pronoun — fold the referent in")
        notes.append("examples → " + _example_lines(dangling))
    return Score("Density (noun-phrase)", pts, 10, notes)


def _check_contact_line(md: str) -> Score:
    """The line right after the H1 should fit on one printed line at 11pt.

    Heuristic widths: ≤80 chars (great); ≤120 chars (acceptable, may wrap on
    narrow PDF); ≤160 chars (will wrap, looks crowded); >160 (broken).
    CJK characters count as ~2 chars to approximate visual width.
    """
    lines = md.splitlines()
    contact = ""
    for i, ln in enumerate(lines[:8]):
        if ln.startswith("# ") and i + 1 < len(lines):
            # find the first non-blank, non-bold-title line after H1
            for cand in lines[i + 1:i + 6]:
                stripped = cand.strip()
                if stripped and not stripped.startswith("**") and not stripped.startswith("#"):
                    contact = stripped
                    break
            break
    if not contact:
        return Score("Contact line width", 0, 10, ["no contact line found below H1"])

    # CJK width approximation: each non-ASCII printable counts double
    width = sum(2 if ord(c) > 0x2E7F else 1 for c in contact)
    if width <= 80:
        return Score("Contact line width", 10, 10, [f"{width} display-width chars (ideal)"])
    if width <= 120:
        return Score("Contact line width", 8, 10, [f"{width} display-width chars (acceptable)"])
    if width <= 160:
        return Score("Contact line width", 5, 10, [f"{width} display-width chars — will wrap on letter PDF, consider splitting into 2 lines"])
    return Score("Contact line width", 2, 10, [f"{width} display-width chars — reviewer sees broken/crowded header; split into 2 lines or drop URLs"])


def estimate_pages(md: str) -> float:
    """Approximate rendered page count from non-blank lines + wrap width.

    ~45 effective non-blank lines per US-Letter/A4 page at 11pt/1in margins; a
    wrapped line (~95 display cols, CJK counted double) adds another visual line.
    Shared by the page-count review check and the render page-budget fitter (#52)."""
    eff = 0.0
    for ln in md.splitlines():
        if not ln.strip():
            continue
        width = sum(2 if ord(c) > 0x2E7F else 1 for c in ln)
        eff += max(1.0, width / 95)
    return eff / 45.0


def _check_page_estimate(md: str, locale_meta: dict[str, Any], target_override: float | None = None) -> Score:
    """Approximate page count from non-blank line + char totals.

    Calibration: ~45 'effective' non-blank lines per US Letter / A4 page at
    11pt with 1in margins, accounting for bullets being shorter than wrapped
    paragraphs. CJK pages fit slightly fewer characters; we still use line
    count because heading + bullet density dominates.
    """
    # #68: a user who deliberately wants a detailed résumé can override the fixed
    # per-locale target (mirrors render --max-pages) so the page-count score is
    # judged against the budget they actually chose.
    target = target_override if target_override else _LOCALE_PAGE_TARGETS.get(
        locale_meta.get("_key"), DEFAULT_PAGE_TARGET)
    pages_est = estimate_pages(md)
    if pages_est <= target:
        pts = 10
    elif pages_est <= target + 0.2:
        pts = 8
    elif pages_est <= target + 0.5:
        pts = 5
    else:
        pts = 2
    notes = [f"~{pages_est:.1f} pages estimated (locale target ≤ {target})"]
    if pages_est > target:
        notes.append(f"over target by {pages_est - target:.1f} pages")
    return Score("Page count", pts, 10, notes)


def _check_red_flags(md: str, locale_meta: dict[str, Any]) -> Score:
    """Locale-aware forbidden content + format issues."""
    pts = 10
    notes: list[str] = []

    # photo rule
    photo_rule = locale_meta.get("photo", "forbidden")
    has_photo = bool(IMAGE_TAG_RE.search(md))
    if photo_rule == "forbidden" and has_photo:
        pts -= 4
        notes.append("photo embedded but locale forbids it (EEOC/equality-law risk)")
    if photo_rule == "expected" and not has_photo:
        pts -= 2
        notes.append("locale expects a photo; none found")

    # "References available upon request" is outdated everywhere
    if REFERENCES_RE.search(md):
        pts -= 2
        notes.append("drop 'References available upon request' — it's filler in 2026")

    # DOB in top fold — forbidden for en_US / en_GB
    if locale_meta.get("_key") in {"en_US", "en_GB"}:
        head = "\n".join(md.splitlines()[:14])
        if DOB_RE.search(head):
            pts -= 2
            notes.append("full DOB in header — US/UK reviewers avoid this (discrimination risk)")

    # Consecutive `## headings` with no blank line
    bad_headings = re.findall(r"^##[^\n]*\n##[^\n]*$", md, re.MULTILINE)
    if bad_headings:
        pts -= 2
        notes.append(f"{len(bad_headings)} section header pair(s) lack a blank-line separator")

    # Date format: XYZ locales prefer month-name dates; noun_phrase locales prefer numeric
    date_iso_in_body = len(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", md))
    if locale_meta.get("style") == "xyz" and date_iso_in_body > 3:
        pts -= 1
        notes.append(f"{date_iso_in_body} ISO-style dates (YYYY-MM-DD) — prefer 'Mon YYYY' in XYZ locales")

    pts = max(pts, 0)
    if not notes:
        notes.append("no red flags detected")
    return Score("Red flags", pts, 10, notes)


# -- AI-proficiency checks (#47) ---------------------------------------------

def _has_ai_content(md: str, rubric: Any) -> bool:
    low = md.lower()
    terms = list(getattr(rubric, "agentic_keywords", [])) + list(
        getattr(rubric, "ai_tool_names", [])
    )
    return any(t.lower() in low for t in terms)


def _ai_bullets(md: str, rubric: Any) -> list[tuple[int, str]]:
    terms = [
        t.lower()
        for t in list(getattr(rubric, "agentic_keywords", []))
        + list(getattr(rubric, "ai_tool_names", []))
    ]
    return [
        (ln, b)
        for ln, b in _bullets_in_scope(md)
        if any(t in b.lower() for t in terms)
    ]


def _hint_category(bullet: str, hints: dict[str, list[str]]) -> str | None:
    low = bullet.lower()
    table = {
        "review": ("review", "qa", "pr"),
        "cost": ("cost", "token", "cache"),
        "cycle": ("cycle", "ship", "deploy", "lead time"),
        "eval": ("eval", "judge", "validate", "test", "regression"),
    }
    for cat, kws in table.items():
        if cat in hints and any(k in low for k in kws):
            return cat
    return next(iter(hints), None)


def _gate_terms(rubric: Any, lang: str | None) -> list[str]:
    """Locale-aware human-gate terms (#50). Delegates to `rubric.gate_terms`,
    the shared home for this logic (also used by the evidence-disclosure layer)."""
    from vibe_resume.core.rubric import gate_terms
    return gate_terms(rubric, lang)


def _check_ai_proficiency(md: str, rubric: Any, lang: str | None = None) -> Score:
    """Positive: AI bullets that pair a tool with a human quality gate.

    Skipped (max=0) when the résumé carries no AI/agentic content, so non-AI
    résumés keep their existing denominator. Number-less AI bullets get a
    *pointer* to a real metric (never an injected value)."""
    if not _has_ai_content(md, rubric):
        return Score("AI proficiency", 0, 0, ["no AI/agentic content — skipped"])
    bullets = _ai_bullets(md, rubric)
    if not bullets:
        return Score("AI proficiency", 0, 10, ["AI terms present but not in scored bullets"])
    gates = _gate_terms(rubric, lang)
    paired = [(ln, b) for ln, b in bullets if any(g in b.lower() for g in gates)]
    ratio = len(paired) / len(bullets)
    pts = min(int(round(ratio * 10)), 10)
    notes = [f"{len(paired)}/{len(bullets)} AI bullets pair a tool with a human quality gate"]
    hints = getattr(rubric, "metric_hints", {}) or {}
    numberless = [(ln, b) for ln, b in bullets if _count_metrics(b) == 0]
    if numberless and hints:
        ln, b = numberless[0]
        cat = _hint_category(b, hints)
        if cat:
            notes.append(
                f'L{ln} AI bullet has no number — consider measuring: {", ".join(hints[cat])}'
            )
    from vibe_resume.core.research import staleness_note
    sn = staleness_note(rubric)
    if sn:
        notes.append(f"⚠ {sn}")
    return Score("AI proficiency", pts, 10, notes)


def _check_ai_red_flags(md: str, rubric: Any, lang: str | None = None) -> Score:
    """Negative: junior framing, stale-stack headline, unverified-judge, name-drop.

    Mirrors `_check_red_flags` (start at 10, deduct). Skipped (max=0) on a
    non-AI résumé."""
    if not _has_ai_content(md, rubric):
        return Score("AI framing red flags", 0, 0, ["no AI/agentic content — skipped"])
    pts = 10
    notes: list[str] = []
    head = "\n".join(md.splitlines()[:14])
    gates = _gate_terms(rubric, lang)
    for yf in getattr(rubric, "yellow_flags", ()):
        if yf.kind == "stale_stack":
            if yf.regex.search(head):
                pts -= 2
                notes.append(f"stale-stack in top fold — {yf.why}")
        elif yf.kind == "junior_volume":
            if yf.regex.search(md):
                pts -= 3
                notes.append(f"junior volume-bragging — {yf.why}")
        elif yf.kind == "unverified_judge":
            for ln, b in _bullets_in_scope(md):
                if yf.regex.search(b) and not any(g in b.lower() for g in gates):
                    pts -= 2
                    notes.append(f"L{ln} unverified-judge claim — {yf.why}")
                    break
    for ln, b in _ai_bullets(md, rubric):
        if _count_metrics(b) == 0 and not any(g in b.lower() for g in gates):
            pts -= 2
            notes.append(
                f"L{ln} bare tool name-drop (no metric, no quality gate) — reads junior"
            )
            break
    pts = max(pts, 0)
    if not notes:
        notes.append("no AI framing red flags detected")
    return Score("AI framing red flags", pts, 10, notes)


# -- disclosure helpers (#63) ------------------------------------------------

def newer_variant_hint(hist_dir: Path, chosen: Path, locale_key: str) -> str | None:
    """Warn when a higher-versioned résumé for the same locale exists but wasn't
    auto-selected — the variant suffix (e.g. `_detailed`) can make the
    persona/locale glob miss the file the user just rendered (#63)."""
    m = re.search(r"resume_v(\d+)", chosen.name)
    if not m:
        return None
    cur = int(m.group(1))
    newer = sorted(
        p.name for p in hist_dir.glob(f"resume_v*_{locale_key}*.md")
        if (mm := re.search(r"resume_v(\d+)", p.name)) and int(mm.group(1)) > cur
    )
    if newer:
        return (f"a newer {locale_key} render exists ({', '.join(newer)}) — scoring "
                f"{chosen.name}; pass --file to target the newer one")
    return None


def per_bullet_diagnostics(
    md: str, locale_meta: dict[str, Any], rubric: Any, lang: str | None = None
) -> list[dict[str, Any]]:
    """Per-failing-bullet diagnostics (#63): which check each in-scope bullet
    missed, so an aggregate score becomes an actionable gap list."""
    bullets = _bullets_in_scope(md)
    ai_lines = {ln for ln, _ in _ai_bullets(md, rubric)}
    gates = _gate_terms(rubric, lang)
    style = locale_meta.get("style")
    out: list[dict[str, Any]] = []
    for ln, b in bullets:
        missed: list[str] = []
        if _count_metrics(b) == 0:
            missed.append("no-metric")
        if style == "xyz":
            first = re.split(r"[\s,—\-:]", b.strip(), 1)[0].lower().strip("*_`")
            if first not in XYZ_VERBS:
                missed.append("not-verb-first")
        if ln in ai_lines and not any(g in b.lower() for g in gates):
            missed.append("ai-no-human-gate")
        if missed:
            out.append({"line": ln, "text": b, "missed": missed})
    return out


# -- public API --------------------------------------------------------------

def review(
    md_text: str,
    locale_key: str | None = None,
    *,
    source: str = "(in-memory)",
    jd_keywords: list[str] | None = None,
    company: Any = None,
    persona: Any = None,
    page_target: float | None = None,
) -> ReviewReport:
    canon = resolve_locale(locale_key)
    loc = get_locale(canon)
    scores: list[Score] = [
        _check_top_fold(md_text),
        _check_numbers_per_bullet(md_text),
        _check_keyword_echo(md_text, jd_keywords),
        _check_action_verb(md_text, loc),
        _check_density(md_text, loc),
        _check_red_flags(md_text, loc),
        _check_contact_line(md_text),
        _check_page_estimate(md_text, loc, page_target),
    ]
    if company is not None:
        # Company-specific coverage lands at the bottom of the scorecard so
        # it reads as a supplement rather than an override of the generic
        # rubric — the 8 base checks remain comparable across résumé versions
        # even when a candidate swaps target employers between runs.
        scores.append(_check_company_keyword_coverage(md_text, company))
    # AI-proficiency checks (#47) append after the base rubric; both self-skip
    # (max=0) when the résumé has no AI content, so non-AI résumés keep their
    # denominator and stay byte-comparable across versions.
    _rb = load_rubric()
    _lang = loc.get("language")
    scores.append(_check_ai_proficiency(md_text, _rb, _lang))
    scores.append(_check_ai_red_flags(md_text, _rb, _lang))
    scoring = [s for s in scores if s.max > 0]
    weights = getattr(persona, "review_weights", None) or {}
    raw_total = sum(s.score for s in scoring)
    raw_max = sum(s.max for s in scoring)
    if weights:
        wsum = sum(s.score * weights.get(s.name, 1.0) for s in scoring)
        wmax = sum(s.max * weights.get(s.name, 1.0) for s in scoring)
        total = round(wsum / wmax * raw_max) if wmax else 0
        max_total = raw_max
    else:
        total = raw_total
        max_total = raw_max
    return ReviewReport(
        source=source,
        locale=canon,
        total=total,
        max_total=max_total,
        scores=scores,
    )


_VERSION_RE = re.compile(r"resume_v(\d+)")


def _version_of(path: Path) -> int:
    """Parse the zero-padded version number out of a resume filename (#86).

    Used to pick the highest-VERSION file regardless of variant suffix, instead of
    relying on lexical order (which a `_detailed`/`_ats` suffix can perturb)."""
    m = _VERSION_RE.search(path.name)
    return int(m.group(1)) if m else -1


def resolve_resume_path(
    hist_dir: Path,
    *,
    version: int | None = None,
    file: Path | str | None = None,
    persona: str | None = None,
    locale: str | None = None,
) -> Path:
    """Pick the rendered résumé markdown to review.

    Resolution priority (mutually exclusive after the first match):
      1. file: explicit path
      2. version: glob resume_v<NNN>*.md
      3. persona and/or locale: glob resume_v*_<locale>[_<persona>].md, pick highest version
      4. otherwise: latest rendered résumé

    Raises `ValueError` if both version and file are set, and
    `FileNotFoundError` if nothing on disk satisfies the request.
    """
    if version is not None and file is not None:
        raise ValueError("pass either `version` or `file`, not both")
    if file is not None:
        return Path(file)
    if version is not None:
        matches = sorted(hist_dir.glob(f"resume_v{version:03d}*.md"))
        if not matches:
            raise FileNotFoundError(
                f"no resume file for v{version:03d} in {hist_dir}"
            )
        return matches[0]

    if persona or locale:
        # #63/#86: variant renders carry an `_ats` / `_detailed` suffix BETWEEN the
        # persona and `.md`, so a strict `..._{persona}.md` glob misses the freshly
        # rendered variant and falls back to the stale non-suffixed file. Allow a
        # trailing suffix (the `*` also matches empty) and pick by VERSION number,
        # not lexical order, so v011_…_detailed beats v003_… (no suffix).
        if persona and locale:
            patterns = [f"resume_v*_{locale}_{persona}*.md"]
        elif locale:
            patterns = [f"resume_v*_{locale}*.md"]
        else:  # persona only — non-suffixed or variant-suffixed
            patterns = [f"resume_v*_{persona}.md", f"resume_v*_{persona}_*.md"]
        seen: set[Path] = set()
        for pat in patterns:
            for m in hist_dir.glob(pat):
                seen.add(m)
        if not seen:
            raise FileNotFoundError(
                f"no resume file matching (persona={persona}, locale={locale}) in {hist_dir}"
            )
        return max(seen, key=lambda p: (_version_of(p), p.name))

    versioned = sorted(hist_dir.glob("resume_v*.md"))
    if not versioned:
        raise FileNotFoundError(
            f"no rendered resumes in {hist_dir} — run `render` first"
        )
    return versioned[-1]


#: Variant suffixes a render can emit (#55); "base" == no suffix.
_KNOWN_VARIANTS = ("ats", "detailed")


def resolve_variant_paths(
    hist_dir: Path, *, persona: str | None = None, locale: str | None = None
) -> dict[str, Path]:
    """Highest-version résumé per variant for a persona/locale (#91).

    Returns ``{variant_name: path}`` over ``ats`` / ``detailed`` / ``base`` (the
    non-suffixed render), each resolved to its highest VERSION. Empty dict if no
    matching file exists — lets ``review --variants`` score every freshly-rendered
    variant in one call."""
    if persona and locale:
        stem = f"{locale}_{persona}"
    elif locale:
        stem = f"{locale}*"
    elif persona:
        stem = f"*{persona}"
    else:
        stem = "*"
    out: dict[str, Path] = {}
    for variant in _KNOWN_VARIANTS:
        matches = list(hist_dir.glob(f"resume_v*_{stem}_{variant}.md"))
        if matches:
            out[variant] = max(matches, key=lambda p: (_version_of(p), p.name))
    # base = non-suffixed render (exclude variant-suffixed files)
    base = [
        p for p in hist_dir.glob(f"resume_v*_{stem}.md")
        if not any(p.name.endswith(f"_{v}.md") for v in _KNOWN_VARIANTS)
    ]
    if base:
        out["base"] = max(base, key=lambda p: (_version_of(p), p.name))
    return out


def review_file(
    md_path: Path,
    locale_key: str | None = None,
    jd_keywords: list[str] | None = None,
    persona: str | None = None,
    company: str | None = None,
    level: str | None = None,
    page_target: float | None = None,
) -> ReviewReport:
    text = Path(md_path).read_text(encoding="utf-8")
    # Infer locale from filename if not given. #92: capture ONLY the locale token
    # (xx_YY), not the trailing persona/variant suffix — the old greedy
    # `([a-zA-Z_]+)` grabbed e.g. `zh_TW_agentic_ats` from
    # resume_v012_zh_TW_agentic_ats.md → invalid → silently fell back to en_US,
    # under-scoring a non-English résumé. resume_v007.md (no token) → en_US.
    if not locale_key:
        m = re.search(r"resume_v\d+_([a-z]{2}_[A-Z]{2})(?:_|\.)", str(md_path))
        locale_key = m.group(1) if m else "en_US"
    # Pre-resolve company so the ``review()`` scorer can apply keyword-anchor
    # coverage in the same pass. Unknown keys fall through cleanly.
    from vibe_resume.core.company_profiles import get_company
    from vibe_resume.core.personas import get_persona

    c = get_company(company) if company else None
    p = get_persona(persona) if persona else None
    report = review(
        text,
        locale_key,
        source=str(Path(md_path).name),
        jd_keywords=jd_keywords,
        company=c,
        persona=p,
        page_target=page_target,
    )
    if p is not None:
        report.persona = p.key
        report.persona_tips = p.review_tips
    if c is not None:
        report.company = c.key
        report.company_label = c.label
        report.company_verified_at = c.last_verified_at
        report.company_tips = c.review_tips
    if level:
        from vibe_resume.core.levels import get_level

        lvl = get_level(level)
        if lvl is not None:
            report.level = lvl.key
            report.level_label = lvl.label
            report.level_tips = lvl.review_tips
    return report


# Structural / title words that appear in most JDs and carry no signal.
# Matched case-insensitively; don't put lowercase-only words here (they never
# survive the initial capitalized-token regex anyway).
_JD_STOPWORDS: set[str] = {
    # document structure
    "About", "Role", "Overview", "Summary", "Responsibilities", "Requirements",
    "Qualifications", "Benefits", "Bonus", "Plus", "Nice", "Preferred",
    "What", "You", "Your", "We", "Our", "Us", "Who",
    "Will", "Would", "Could", "Can", "Must", "Should", "May",
    # seniority / job-level labels
    "Senior", "Junior", "Mid", "Staff", "Principal", "Lead", "Head",
    "Manager", "Director", "VP", "Intern",
    # work-style labels
    "Remote", "Hybrid", "Onsite", "On-site", "Full-time", "Part-time",
    "Contract", "Contractor", "Permanent",
    # generic soft/business terms
    "Engineer", "Engineering", "Developer", "Development", "Software",
    "Team", "Teams", "Company", "Industry", "Product", "Products",
    "Experience", "Skills", "Years", "Year", "Strong",
    # generic verb-ish leads
    "Design", "Build", "Ship", "Ship", "Work", "Working", "Drive",
    "Deliver", "Own", "Partner", "Debug",
    # geographic / currency — keep the tech terms, drop the location noise
    "US", "UK", "EU", "USD", "EUR", "Taipei", "Taiwan", "Tokyo",
    "London", "Berlin", "Paris", "Seoul", "SG",
    # month/day (JDs often list "posted March 2026" etc.)
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
}

# Whitelist of framework / language / infra names — these jump to the top of
# the extracted keyword list regardless of JD position. Kept short and
# canonical (matches what our tech_canonical module produces).
_JD_TECH_PRIORITY: list[str] = [
    # languages
    "Python", "TypeScript", "JavaScript", "Go", "Rust", "Java", "Kotlin",
    "Swift", "Ruby", "PHP", "Scala", "C++",
    # frontend
    "React", "Next.js", "Vue", "Svelte", "Angular", "Tailwind",
    # backend
    "FastAPI", "Django", "Flask", "Express", "NestJS", "Rails", "Spring",
    "gRPC", "GraphQL",
    # data
    "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Kafka", "NATS",
    "Elasticsearch", "Snowflake", "BigQuery", "DuckDB", "pgvector",
    # infra / ops
    "Docker", "Kubernetes", "Terraform", "Ansible", "AWS", "GCP", "Azure",
    "Vercel", "Fly.io", "Heroku", "GitHub", "GitLab",
    # AI / agents
    "Claude", "GPT", "OpenAI", "LangChain", "LlamaIndex", "RAG", "LLM",
    "Embedding", "Cursor", "Copilot",
    # observability / billing / integrations
    "Sentry", "Datadog", "Stripe", "Twilio", "PagerDuty",
    # CI / infra glue
    "Actions", "CircleCI", "Jenkins", "ArgoCD",
]


def parse_jd_keywords(path: Path, limit: int = 12) -> list[str]:
    """JD tokenizer that prefers real tech/framework names over structural words.

    Strategy:
    1. Scan JD text for exact matches from `_JD_TECH_PRIORITY` (case-sensitive
       where it matters — "Actions" means GitHub Actions, not generic).
       Those go first, ordered by first appearance in the JD.
    2. Fill remaining slots with other capitalized tokens, skipping
       `_JD_STOPWORDS` so "About", "Remote", "Senior" never leak in.
    """
    text = Path(path).read_text(encoding="utf-8")

    selected: list[str] = []
    seen: set[str] = set()

    # pass 1 — prioritized tech/framework names, order by first appearance
    tech_hits: list[tuple[int, str]] = []
    for tech in _JD_TECH_PRIORITY:
        # word boundaries on both sides; allow trailing punctuation
        m = re.search(rf"\b{re.escape(tech)}\b", text)
        if m:
            tech_hits.append((m.start(), tech))
    tech_hits.sort()
    for _, tech in tech_hits:
        if tech not in seen:
            selected.append(tech)
            seen.add(tech)
            if len(selected) >= limit:
                return selected

    # pass 2 — fallback capitalized tokens, stopword-filtered
    stop_lower = {s.lower() for s in _JD_STOPWORDS}
    cands = re.findall(r"\b([A-Z][A-Za-z0-9+./-]{1,})\b", text)
    for c in cands:
        if c.lower() in {"i", "a", "the", "and", "or", "with"}:
            continue
        if c.lower() in stop_lower:
            continue
        if c in seen:
            continue
        selected.append(c)
        seen.add(c)
        if len(selected) >= limit:
            break
    return selected


def write_report(
    report: ReviewReport,
    out_dir: Path,
    previous: ReviewReport | None = None,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(report.source).stem or "review"
    md_path = out_dir / f"{stem}_review.md"
    json_path = out_dir / f"{stem}_review.json"
    md_path.write_text(report.as_markdown(previous=previous), encoding="utf-8")
    json_path.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return md_path, json_path


def load_reviews_by_locale(reviews_dir: Path) -> dict[str, list[tuple[int, ReviewReport]]]:
    """Scan reviews_dir for `resume_v*_review.json` and group by locale.

    Returns locale_key → [(version, ReviewReport)], sorted by version ascending.
    """
    out: dict[str, list[tuple[int, ReviewReport]]] = {}
    if not reviews_dir.exists():
        return out
    for j in reviews_dir.glob("resume_v*_review.json"):
        m = re.search(r"resume_v(\d+)", j.stem)
        if not m:
            continue
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        locale = data.get("locale", "en_US")
        out.setdefault(locale, []).append((int(m.group(1)), ReviewReport.from_dict(data)))
    for loc in out:
        out[loc].sort(key=lambda x: x[0])
    return out


def load_reviews_by_locale_persona(
    reviews_dir: Path,
) -> dict[tuple[str, str | None], list[tuple[int, ReviewReport]]]:
    """Group reviews by (locale, persona) parsed from the review JSON filename.

    resume_v007_en_US_tech_lead_review.json → (en_US, tech_lead)
    resume_v007_en_US_hr_review.json        → (en_US, hr)
    resume_v007_en_US_review.json           → (en_US, None)
    resume_v007_review.json                 → (en_US, None)  # legacy en_US default
    """
    _fname_re = re.compile(
        r"resume_v(\d+)(?:_([a-z]{2}_[A-Z]{2}))?(?:_(?!review)([a-z][a-z_]*))?_review\.json$"
    )
    grouped: dict[tuple[str, str | None], list[tuple[int, ReviewReport]]] = {}
    if not reviews_dir.exists():
        return grouped
    for j in reviews_dir.glob("resume_v*_review.json"):
        m = _fname_re.search(j.name)
        if not m:
            continue
        version = int(m.group(1))
        loc = m.group(2) or "en_US"
        pers = m.group(3) or None
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        report = ReviewReport.from_dict(data)
        grouped.setdefault((loc, pers), []).append((version, report))
    for k in grouped:
        grouped[k].sort(key=lambda t: t[0])
    return grouped


_LOCALE_PAGE_TARGETS: dict[str, float] = {
    "en_US": 2.0, "en_GB": 2.0, "en_EU": 2.0,
    "zh_TW": 2.0, "zh_HK": 2.0, "zh_CN": 2.0,
    "de_DE": 2.5, "fr_FR": 2.5,
    "ja_JP": 1.0,
    "ko_KR": 2.0,
}
DEFAULT_PAGE_TARGET = 2.0

# ASCII sparkline chars from low to high — classic U+2581..U+2588 block set.
_SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 24) -> str:
    """Return a one-line sparkline for a series. Empty/constant series → flat."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return _SPARK[len(_SPARK) // 2] * min(len(values), width)
    # down-sample if longer than target width — keep most recent bias
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values
    return "".join(_SPARK[min(int((v - lo) / span * (len(_SPARK) - 1)), len(_SPARK) - 1)] for v in sampled)


def find_previous_review(reviews_dir: Path, current_source: str, locale_key: str) -> ReviewReport | None:
    """Locate the most recent earlier review for the same locale.

    Sources are named `resume_v007.md` (en_US) or `resume_v010_zh_TW.md` —
    we extract the version number, then scan reviews_dir for any json with a
    smaller version + matching locale.
    """
    if not reviews_dir.exists():
        return None
    m = re.search(r"resume_v(\d+)", current_source)
    if not m:
        return None
    cur_v = int(m.group(1))

    candidates: list[tuple[int, Path]] = []
    for j in reviews_dir.glob("resume_v*_review.json"):
        m2 = re.search(r"resume_v(\d+)", j.stem)
        if not m2:
            continue
        v = int(m2.group(1))
        if v >= cur_v:
            continue
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("locale") != locale_key:
            continue
        candidates.append((v, j))

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    _, prev_path = candidates[0]
    return ReviewReport.from_dict(json.loads(prev_path.read_text(encoding="utf-8")))
