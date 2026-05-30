"""JD-gap explanation layer (#80 — `jd-check --explain`).

For each JD keyword, classify it as already *surfaced* in the resume,
*groundable* (genuinely present in the user's raw activity signals but not yet
in the bullets), or honestly *absent*. For groundable keywords it surfaces the
closest raw-activity snippets so a human can decide whether to surface them.

This is advisory only — it NEVER auto-inserts a keyword (the never-fabricate
guarantee, P1.3). It only reports where a term *nearly matches* a real signal,
leaving the decision to surface or accept the gap to the user.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from vibe_resume.core.evidence import disclose_all
from vibe_resume.core.schema import ProjectGroup

_SNIPPET = 90


def _snippet(text: str, around: str | None = None, width: int = _SNIPPET) -> str:
    """Short context snippet centred on `around` (mirrors evidence._snippet)."""
    t = (text or "").strip().replace("\n", " ")
    if around and around.lower() in t.lower():
        i = t.lower().index(around.lower())
        start = max(0, i - width // 3)
        end = min(len(t), i + len(around) + width)
        out = ("…" if start else "") + t[start:end].strip() + ("…" if end < len(t) else "")
    else:
        out = t[:width] + ("…" if len(t) > width else "")
    # hard cap so the snippet (incl. ellipses) never exceeds `width`
    return out[:width]


@dataclass
class GroundingSnippet:
    source: str   # activity source tag, e.g. "claude-code" / "git"
    snippet: str  # short context (<=90 chars) showing the near-match
    ref: str      # raw_ref or session_id for traceability

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KeywordExplanation:
    keyword: str
    status: str          # "surfaced" | "groundable" | "absent"
    matches: list[GroundingSnippet] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "status": self.status,
            "matches": [m.as_dict() for m in self.matches],
        }


def _ground_keyword(keyword: str, groups: list[ProjectGroup], limit: int = 3) -> list[GroundingSnippet]:
    """Collect up to `limit` raw-activity snippets where `keyword` nearly matches.

    Case-insensitive substring against each activity's summary, tech_stack and
    keywords. Never fuzzy beyond lowercase substring (deterministic, no
    fabrication). Snippets are deduped by (ref, snippet)."""
    low = keyword.lower()
    out: list[GroundingSnippet] = []
    seen: set[tuple[str, str]] = set()
    for g in groups:
        for a in g.activities:
            summary = (a.summary or "").strip()
            ref = a.raw_ref or a.session_id or ""
            # build the searchable haystack: summary + tech + keywords
            tech_kw = list(a.tech_stack) + list(a.keywords)
            hit_in_summary = low in summary.lower()
            hit_in_tags = next((t for t in tech_kw if t and low in t.lower()), None)
            if not hit_in_summary and not hit_in_tags:
                continue
            if hit_in_summary:
                snip = _snippet(summary, keyword)
            else:
                # term lives in a tag — show the tag with surrounding summary context
                base = summary or hit_in_tags or ""
                snip = _snippet(base) if summary else _snippet(hit_in_tags or "")
            key = (ref, snip)
            if key in seen:
                continue
            seen.add(key)
            out.append(GroundingSnippet(source=a.source.value, snippet=snip, ref=ref))
            if len(out) >= limit:
                return out
    return out


def explain_jd_gaps(
    jd_keywords: list[str],
    groups: list,            # list[ProjectGroup]
    surfaced_text: str,
    lang: str | None = None,
) -> list[KeywordExplanation]:
    """Classify each JD keyword as surfaced / groundable / absent (#80).

    - "surfaced": case-insensitive substring already in `surfaced_text`.
    - "groundable": not surfaced, but genuinely present in the groups' raw
      signals (activity summaries / tech_stack / keywords / evidence.backs_term)
      — `matches` holds up to 3 closest snippets for human review.
    - "absent": no supporting evidence anywhere — an honest gap, left alone.

    Advisory only: never inserts a keyword, only discloses where it nearly
    matches a real signal (P1.3 never-fabricate guardrail)."""
    low_surfaced = (surfaced_text or "").lower()
    evidences = disclose_all(groups, lang=lang)
    out: list[KeywordExplanation] = []
    for kw in jd_keywords:
        if kw.lower() in low_surfaced:
            out.append(KeywordExplanation(keyword=kw, status="surfaced", matches=[]))
            continue
        matches = _ground_keyword(kw, groups)
        backed = any(e.backs_term(kw) for e in evidences)
        if matches or backed:
            # backed-but-no-snippet (e.g. group-level tech_stack) still groundable
            out.append(KeywordExplanation(keyword=kw, status="groundable", matches=matches))
        else:
            out.append(KeywordExplanation(keyword=kw, status="absent", matches=[]))
    return out
