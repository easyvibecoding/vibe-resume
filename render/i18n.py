"""Per-locale resume rendering metadata.

One dict per locale captures:
- `headings`: section heading labels (language-native)
- `style`: "xyz" (action-verb bullets) or "noun_phrase" (factual, understated)
- `photo`: "forbidden" | "optional" | "expected"
- `personal_fields`: which optional profile fields to render
- `date_format`: strftime pattern for experience periods
- `language_scale`: None | "cefr"
- `filename_style`: template key used by renderer for output filenames

See `docs/resume_locales.md` for the research behind these choices.
`LOCALES["en_US"]` is the conservative default; fallbacks go through it
when a locale entry is missing a key.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# en_US is the canonical fallback — every other locale diffs against it.
LOCALES: dict[str, dict[str, Any]] = {
    "en_US": {
        "language": "en",
        "style": "xyz",
        "photo": "forbidden",
        "personal_fields": ["email", "phone", "location", "linkedin", "github", "website"],
        "date_format": "%b %Y",
        "language_scale": None,
        "filename_style": "{last}_{first}_{role_slug}_{locale}_{yyyymm}",
        "headings": {
            "summary": "Summary",
            "skills": "Technical Skills",
            "ai_overview": "AI-assisted workflow overview",
            "projects": "AI-assisted project work",
            "experience": "Experience",
            "education": "Education",
            "certifications": "Certifications",
            "awards": "Awards",
            "talks": "Talks",
            "hobbies": "Interests",
            "target_role": "Target role",
            "last_30d": "Last 30-day intensity",
            "ai_tools": "AI tools used",
            "capabilities": "Cross-discipline capabilities",
            "period": "Period",
            "sessions": "Sessions",
            "breadth": "Breadth",
            "stack": "Stack",
            "domain_tags": "Domain tags",
            "impact": "Impact",
            "key_achievements": "Key achievements",
            "other_short": "Other short collaborations",
            "tailored_for": "Tailored for",
        },
    },
    "en_EU": {
        "language": "en",
        "style": "xyz",
        "photo": "optional",
        "personal_fields": ["email", "phone", "location", "nationality", "linkedin", "github", "website"],
        "date_format": "%m/%Y",
        "language_scale": "cefr",
        "filename_style": "{last}_{first}_{role_slug}_Europass_{yyyymm}",
        "headings": {
            "summary": "Personal statement",
            "skills": "Digital skills",
            "ai_overview": "AI-augmented work",
            "projects": "Work experience — project portfolio",
            "experience": "Work experience",
            "education": "Education and training",
            "certifications": "Certifications",
            "awards": "Honours and awards",
            "talks": "Conferences and publications",
            "hobbies": "Additional information",
            "target_role": "Applied position",
            "last_30d": "Recent activity (30 days)",
            "ai_tools": "Digital tools",
            "capabilities": "Cross-discipline capabilities",
            "period": "Dates",
            "sessions": "Sessions",
            "breadth": "Functional breadth",
            "stack": "Technologies",
            "domain_tags": "Domain",
            "impact": "Impact",
            "key_achievements": "Main activities and responsibilities",
            "other_short": "Additional short engagements",
            "tailored_for": "Tailored for",
        },
    },
    "en_GB": {
        "language": "en",
        "style": "xyz",
        "photo": "forbidden",
        "personal_fields": ["email", "phone", "location", "linkedin", "github", "website"],
        "date_format": "%B %Y",
        "language_scale": "cefr",
        "filename_style": "{last}_{first}_{role_slug}_{locale}_{yyyymm}",
        "headings": {
            "summary": "Personal statement",
            "skills": "Technical skills",
            "ai_overview": "AI-assisted workflow overview",
            "projects": "AI-assisted project work",
            "experience": "Work experience",
            "education": "Education",
            "certifications": "Certifications",
            "awards": "Awards",
            "talks": "Talks",
            "hobbies": "Interests",
            "target_role": "Target role",
            "last_30d": "Last 30-day activity",
            "ai_tools": "AI tools used",
            "capabilities": "Cross-discipline capabilities",
            "period": "Period",
            "sessions": "Sessions",
            "breadth": "Breadth",
            "stack": "Stack",
            "domain_tags": "Domain tags",
            "impact": "Impact",
            "key_achievements": "Key achievements",
            "other_short": "Other short collaborations",
            "tailored_for": "Tailored for",
        },
    },
    "zh_TW": {
        "language": "zh",
        "style": "noun_phrase",
        "photo": "optional",
        "personal_fields": ["email", "phone", "location", "linkedin", "github", "website"],
        "date_format": "%Y/%m",
        "language_scale": None,
        "filename_style": "{last}{first}_{role_slug}_{locale}_{yyyymm}",
        "headings": {
            "summary": "自我介紹",
            "skills": "技能專長",
            "ai_overview": "AI 協作工作概覽",
            "projects": "AI 協作專案經歷",
            "experience": "工作經歷",
            "education": "學歷",
            "certifications": "證照",
            "awards": "獲獎紀錄",
            "talks": "演講 / 分享",
            "hobbies": "興趣",
            "target_role": "應徵職位",
            "last_30d": "近 30 天活躍度",
            "ai_tools": "使用的 AI 工具",
            "capabilities": "跨職能能力",
            "period": "期間",
            "sessions": "對話次數",
            "breadth": "職能涵蓋",
            "stack": "技術堆疊",
            "domain_tags": "領域標籤",
            "impact": "成果",
            "key_achievements": "主要成果",
            "other_short": "其他短期合作",
            "tailored_for": "投遞目標",
        },
    },
    "zh_CN": {
        "language": "zh",
        "style": "noun_phrase",
        "photo": "optional",
        "personal_fields": ["email", "phone", "location", "linkedin", "github", "website"],
        "date_format": "%Y.%m",
        "language_scale": None,
        "filename_style": "{last}{first}_{role_slug}_{locale}_{yyyymm}",
        "headings": {
            "summary": "个人简介",
            "skills": "专业技能",
            "ai_overview": "AI 协作工作概览",
            "projects": "AI 协作项目经历",
            "experience": "工作经历",
            "education": "教育背景",
            "certifications": "证书",
            "awards": "获奖记录",
            "talks": "演讲 / 分享",
            "hobbies": "兴趣爱好",
            "target_role": "应聘岗位",
            "last_30d": "近 30 天活跃度",
            "ai_tools": "使用的 AI 工具",
            "capabilities": "跨职能能力",
            "period": "时间",
            "sessions": "对话次数",
            "breadth": "职能覆盖",
            "stack": "技术栈",
            "domain_tags": "领域标签",
            "impact": "成果",
            "key_achievements": "主要成果",
            "other_short": "其他短期合作",
            "tailored_for": "投递目标",
        },
    },
    "ja_JP": {
        "language": "ja",
        "style": "noun_phrase",
        "photo": "expected",
        "personal_fields": ["email", "phone", "location", "linkedin", "github"],
        "date_format": "%Y年%m月",
        "language_scale": None,
        "filename_style": "{last}_{first}_{role_slug}_{locale}_{yyyymm}",
        "headings": {
            "summary": "職務要約",
            "skills": "活かせる経験・スキル",
            "ai_overview": "AI 協働業務概要",
            "projects": "AI 協働プロジェクト経歴",
            "experience": "職務経歴",
            "education": "学歴",
            "certifications": "免許・資格",
            "awards": "受賞歴",
            "talks": "登壇・発表",
            "hobbies": "趣味・特技",
            "target_role": "志望職種",
            "last_30d": "直近30日の活動",
            "ai_tools": "使用AIツール",
            "capabilities": "担当領域の広さ",
            "period": "期間",
            "sessions": "セッション数",
            "breadth": "担当カテゴリ数",
            "stack": "技術スタック",
            "domain_tags": "ドメインタグ",
            "impact": "成果",
            "key_achievements": "主な成果",
            "other_short": "その他の短期参画",
            "tailored_for": "応募先",
        },
    },
    "de_DE": {
        "language": "de",
        "style": "noun_phrase",
        "photo": "expected",
        "personal_fields": ["email", "phone", "location", "dob", "nationality", "linkedin", "github"],
        "date_format": "%m/%Y",
        "language_scale": "cefr",
        "filename_style": "{last}_{first}_{role_slug}_Lebenslauf_{yyyymm}",
        "headings": {
            "summary": "Profil",
            "skills": "Kenntnisse",
            "ai_overview": "KI-gestützte Arbeitsweise",
            "projects": "KI-gestützte Projekte",
            "experience": "Berufserfahrung",
            "education": "Ausbildung",
            "certifications": "Zertifikate",
            "awards": "Auszeichnungen",
            "talks": "Vorträge",
            "hobbies": "Interessen",
            "target_role": "Zielposition",
            "last_30d": "Letzte 30 Tage",
            "ai_tools": "Eingesetzte KI-Werkzeuge",
            "capabilities": "Fachliche Breite",
            "period": "Zeitraum",
            "sessions": "Sitzungen",
            "breadth": "Aufgabenbreite",
            "stack": "Technologiestack",
            "domain_tags": "Domänen",
            "impact": "Wirkung",
            "key_achievements": "Wesentliche Erfolge",
            "other_short": "Weitere Kurzeinsätze",
            "tailored_for": "Zugeschnitten auf",
        },
    },
    "fr_FR": {
        "language": "fr",
        "style": "noun_phrase",
        "photo": "optional",
        "personal_fields": ["email", "phone", "location", "linkedin", "github"],
        "date_format": "%m/%Y",
        "language_scale": "cefr",
        "filename_style": "{last}_{first}_{role_slug}_CV_{yyyymm}",
        "headings": {
            "summary": "Profil",
            "skills": "Compétences",
            "ai_overview": "Flux de travail assisté par IA",
            "projects": "Projets avec assistance IA",
            "experience": "Expérience professionnelle",
            "education": "Formation",
            "certifications": "Certifications",
            "awards": "Distinctions",
            "talks": "Conférences",
            "hobbies": "Centres d'intérêt",
            "target_role": "Poste visé",
            "last_30d": "30 derniers jours",
            "ai_tools": "Outils IA utilisés",
            "capabilities": "Polyvalence",
            "period": "Période",
            "sessions": "Sessions",
            "breadth": "Diversité des tâches",
            "stack": "Stack technique",
            "domain_tags": "Domaines",
            "impact": "Impact",
            "key_achievements": "Réalisations clés",
            "other_short": "Autres missions courtes",
            "tailored_for": "Adapté pour",
        },
    },
    "ko_KR": {
        "language": "ko",
        "style": "noun_phrase",
        "photo": "expected",
        "personal_fields": ["email", "phone", "location", "linkedin", "github"],
        "date_format": "%Y.%m",
        "language_scale": None,
        "filename_style": "{last}{first}_{role_slug}_{locale}_{yyyymm}",
        "headings": {
            "summary": "자기소개",
            "skills": "보유 기술",
            "ai_overview": "AI 협업 업무 개요",
            "projects": "AI 협업 프로젝트 경력",
            "experience": "경력 사항",
            "education": "학력",
            "certifications": "자격증",
            "awards": "수상 내역",
            "talks": "발표 / 강연",
            "hobbies": "관심 분야",
            "target_role": "지원 직무",
            "last_30d": "최근 30일 활동",
            "ai_tools": "사용한 AI 도구",
            "capabilities": "다분야 역량",
            "period": "기간",
            "sessions": "세션 수",
            "breadth": "담당 영역 수",
            "stack": "기술 스택",
            "domain_tags": "도메인 태그",
            "impact": "성과",
            "key_achievements": "주요 성과",
            "other_short": "기타 단기 참여",
            "tailored_for": "지원 대상",
        },
    },
}

# aliases — let users ask for shortened locale keys
ALIASES = {
    "en": "en_US",
    "en-US": "en_US",
    "en-GB": "en_GB",
    "zh": "zh_TW",
    "zh-TW": "zh_TW",
    "zh-Hant": "zh_TW",
    "zh-CN": "zh_CN",
    "zh-Hans": "zh_CN",
    "ja": "ja_JP",
    "ja-JP": "ja_JP",
    "de": "de_DE",
    "fr": "fr_FR",
    "ko": "ko_KR",
}


def resolve_locale(key: str | None) -> str:
    """Normalize a user-supplied locale key to a canonical LOCALES key."""
    if not key:
        return "en_US"
    if key in LOCALES:
        return key
    if key in ALIASES:
        return ALIASES[key]
    # try case-insensitive prefix match
    lower = key.lower().replace("-", "_")
    for canon in LOCALES:
        if canon.lower() == lower:
            return canon
    return "en_US"


def get_locale(key: str | None) -> dict[str, Any]:
    """Return the full locale dict, falling back to en_US for missing keys."""
    canonical = resolve_locale(key)
    base = dict(LOCALES["en_US"])
    chosen = LOCALES.get(canonical, {})
    merged = {**base, **chosen}
    # deep-merge headings so a partial override still resolves fallbacks
    merged["headings"] = {**base["headings"], **chosen.get("headings", {})}
    merged["_key"] = canonical
    return merged


# -- date formatting ---------------------------------------------------------

_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
    "%Y-%m",
    "%Y/%m/%d",
    "%Y/%m",
    "%Y.%m.%d",
    "%Y.%m",
    "%Y",
)

_PRESENT_TOKENS = {
    "Present", "present", "PRESENT", "Now", "now",
    "現在", "現職", "在職", "進行中",
    "現在まで", "継続中",
    "재직중", "현재",
    "Aktuell", "aktuell", "heute",
    "actuel", "à ce jour", "présent",
}

_PRESENT_BY_LANG = {
    "en": "Present",
    "zh": "現在",
    "ja": "現在",
    "ko": "재직중",
    "de": "heute",
    "fr": "à ce jour",
}


def _parse_iso(s: str) -> datetime | None:
    s = s.strip()
    if not s:
        return None
    for fmt in _ISO_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # last-resort: ISO prefix up to YYYY-MM
    m = re.match(r"^(\d{4})[-/.](\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            return None
    m = re.match(r"^(\d{4})$", s)
    if m:
        return datetime(int(m.group(1)), 1, 1)
    return None


def format_date(value: Any, locale_key: str | None = None) -> str:
    """Format an ISO-like date string per locale.

    Passes through Present/現在-style tokens (normalized to the locale's word).
    Unparseable strings are returned as-is so we never silently lose content.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    loc = get_locale(locale_key)
    lang = loc.get("language", "en")

    if s in _PRESENT_TOKENS:
        return _PRESENT_BY_LANG.get(lang, s)

    dt = _parse_iso(s)
    if dt is None:
        return s

    fmt = loc.get("date_format", "%Y-%m")

    # strftime on macOS handles CJK literals inside the format string fine,
    # but we go manual to stay portable (Windows strftime chokes on non-ASCII).
    if "年" in fmt and "月" in fmt:
        if "%d" in fmt:
            return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"
        return f"{dt.year}年{dt.month:02d}月"
    return dt.strftime(fmt)


def format_date_range(start: Any, end: Any, locale_key: str | None = None) -> str:
    """Render `<start> – <end>` with locale-aware separator."""
    loc = get_locale(locale_key)
    lang = loc.get("language", "en")
    sep = {
        "en": " – ",
        "zh": " – ",
        "ja": "～",
        "ko": " – ",
        "de": " – ",
        "fr": " – ",
    }.get(lang, " – ")
    a = format_date(start, locale_key)
    b = format_date(end, locale_key)
    if not a and not b:
        return ""
    return f"{a}{sep}{b}"


# -- localized field fallback -----------------------------------------------

def localized(obj: Any, key: str, locale_key: str | None = None) -> Any:
    """Return `obj[key_<locale>]` when truthy, else `obj[key]`.

    Accepts dicts (for list-of-dict profile fields like experience) and
    Pydantic-dumped dicts; anything else falls through to `getattr`.
    """
    if obj is None:
        return None
    canon = resolve_locale(locale_key)
    loc_key = f"{key}_{canon}"
    if isinstance(obj, dict):
        v = obj.get(loc_key)
        if v:
            return v
        return obj.get(key)
    v = getattr(obj, loc_key, None)
    if v:
        return v
    return getattr(obj, key, None)
