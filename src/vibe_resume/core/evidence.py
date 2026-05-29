"""Evidence-disclosure layer (P2 — disclosure over opacity, #51).

Discloses, per project group, the *real* signals behind enrich/review/iterate
decisions so the consuming agent can self-mine what it needs to see and every
automated change is traceable to a disclosed real signal (P1.6 auditability).

This is the shared substrate for:
- #53 metric backfill   → `candidate_metrics` (numbers literally in the activity)
- #54 keyword-gap        → `backed_terms` (terms genuinely present in signals)
- #56 human-gate framing → `human_gate_evidence` (where a real gate appears)
- #57 auto-iterate        → all of the above + `provenance` for the audit trail

It never invents: it only surfaces what is literally present in the activities.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from vibe_resume.core.review import CJK_METRIC_RE, METRIC_RE
from vibe_resume.core.rubric import MarketRubric, gate_terms, load_rubric
from vibe_resume.core.schema import ProjectGroup

_SNIPPET = 90


def _snippet(text: str, around: str | None = None, width: int = _SNIPPET) -> str:
    t = (text or "").strip().replace("\n", " ")
    if around and around in t:
        i = t.index(around)
        start = max(0, i - width // 3)
        end = min(len(t), i + len(around) + width)
        return ("…" if start else "") + t[start:end].strip() + ("…" if end < len(t) else "")
    return t[:width] + ("…" if len(t) > width else "")


@dataclass
class MetricCandidate:
    value: str          # the literal quantity found, e.g. "40%", "2k", "3x"
    source_ref: str     # raw_ref / session for traceability
    context: str        # snippet of the activity it came from

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HumanGateEvidence:
    term: str           # the gate term that matched (e.g. "reviewed", "人工把關")
    source_ref: str
    context: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GroupEvidence:
    """What the tool can truthfully see for one group — the disclosure surface."""

    group: str
    activity_count: int
    candidate_metrics: list[MetricCandidate] = field(default_factory=list)
    backed_terms: list[str] = field(default_factory=list)
    human_gate_evidence: list[HumanGateEvidence] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)

    @property
    def has_real_metrics(self) -> bool:
        return bool(self.candidate_metrics)

    @property
    def has_human_gate(self) -> bool:
        return bool(self.human_gate_evidence)

    def backs_term(self, term: str) -> bool:
        """True iff `term` is genuinely present in this group's signals (#54)."""
        low = term.lower()
        return any(low in t.lower() for t in self.backed_terms)

    def as_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "activity_count": self.activity_count,
            "candidate_metrics": [m.as_dict() for m in self.candidate_metrics],
            "backed_terms": self.backed_terms,
            "human_gate_evidence": [h.as_dict() for h in self.human_gate_evidence],
            "provenance": self.provenance,
        }


# An impact metric carries a unit/operator; bare integers (years, IPs, ports,
# PR/issue numbers, IDs/phone-like runs) are incidental noise — not achievements.
_IMPACT_SHAPE = re.compile(
    r"[%×]"                       # percent / multiplier sign
    r"|\d\s*[xX]\b"               # 2x / 2.0 x
    r"|[倍萬億千]"                  # CJK magnitude/multiplier units
    r"|\d\s*[kKmMbB]\b"           # 1M / 12k magnitude
    r"|[$€£¥]"                    # currency
    r"|\d\s*(?:ms|s|min|hrs?|h|d|day|days|week|month|quarter|year|個|天|小時|週|個月|年|人)\b"
)


def _is_impact_metric(value: str) -> bool:
    """#58: keep only impact-shaped quantities; drop bare integers (dates, IPs,
    ports, PR#, long ID/phone-like runs) that the bare-integer branch of the
    metric regex incidentally matches. Precision only — not a score lever (#51)."""
    return bool(_IMPACT_SHAPE.search(value))


def _find_metrics(text: str) -> list[str]:
    raw = METRIC_RE.findall(text) + CJK_METRIC_RE.findall(text)
    return [v for v in raw if _is_impact_metric(v)]


def disclose_evidence(
    group: ProjectGroup,
    rubric: MarketRubric | None = None,
    lang: str | None = None,
) -> GroupEvidence:
    rb = rubric or load_rubric()
    gates = gate_terms(rb, lang)

    metrics: list[MetricCandidate] = []
    gate_ev: list[HumanGateEvidence] = []
    backed: list[str] = []
    provenance: list[str] = []
    seen_metric: set[tuple[str, str]] = set()
    seen_term: set[str] = set()

    for a in group.activities:
        summary = (a.summary or "").strip()
        ref = a.raw_ref or a.session_id or ""
        if ref:
            provenance.append(ref)
        # candidate metrics — numbers literally present (never invented)
        for val in _find_metrics(summary):
            key = (val, ref)
            if key not in seen_metric:
                seen_metric.add(key)
                metrics.append(MetricCandidate(value=val, source_ref=ref,
                                               context=_snippet(summary, val)))
        # terms genuinely backed by the signal
        for t in list(a.tech_stack) + list(a.keywords):
            if t and t.lower() not in seen_term:
                seen_term.add(t.lower())
                backed.append(t)
        # human-gate evidence — only where a gate term actually appears
        low = summary.lower()
        for g in gates:
            if g and g in low:
                gate_ev.append(HumanGateEvidence(term=g, source_ref=ref,
                                                 context=_snippet(summary, g)))
                break

    # group-level tech_stack also counts as backed terms
    for t in group.tech_stack:
        if t and t.lower() not in seen_term:
            seen_term.add(t.lower())
            backed.append(t)

    return GroupEvidence(
        group=group.name,
        activity_count=len(group.activities),
        candidate_metrics=metrics,
        backed_terms=backed,
        human_gate_evidence=gate_ev,
        provenance=provenance,
    )


def disclose_all(
    groups: list[ProjectGroup],
    rubric: MarketRubric | None = None,
    lang: str | None = None,
) -> list[GroupEvidence]:
    rb = rubric or load_rubric()
    return [disclose_evidence(g, rb, lang) for g in groups]


# -- gap reconciliation on the disclosure layer (#53 metrics, #54 keywords) ---

@dataclass
class KeywordGap:
    """Split JD keywords against what the signals actually back (#54)."""

    present_but_omitted: list[str] = field(default_factory=list)  # backed yet not in bullets → surface
    genuinely_absent: list[str] = field(default_factory=list)     # not backed → honest gap, leave
    already_surfaced: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def keyword_gap(
    jd_keywords: list[str],
    evidences: list[GroupEvidence],
    surfaced_text: str,
) -> KeywordGap:
    """Reconcile JD keywords against disclosed evidence + what bullets already say.

    Surfaces only keywords **genuinely backed by the user's activity** but missing
    from the bullets (a recall gap). Keywords the data doesn't back are reported as
    `genuinely_absent` and left alone — never stuffed (P1.3 guardrail)."""
    low_surfaced = (surfaced_text or "").lower()
    gap = KeywordGap()
    for kw in jd_keywords:
        backed = any(e.backs_term(kw) for e in evidences)
        surfaced = kw.lower() in low_surfaced
        if surfaced:
            gap.already_surfaced.append(kw)
        elif backed:
            gap.present_but_omitted.append(kw)
        else:
            gap.genuinely_absent.append(kw)
    return gap


def unsurfaced_metrics(
    evidence: GroupEvidence,
    surfaced_text: str,
) -> list[MetricCandidate]:
    """Real metrics present in the activity but not yet in the bullets (#53).

    These are *suggestions a human confirms* — only numbers literally in the
    signals, never invented or estimated (P1.1 guardrail)."""
    low = (surfaced_text or "").lower()
    out: list[MetricCandidate] = []
    seen: set[str] = set()
    for m in evidence.candidate_metrics:
        if m.value.lower() in low or m.value in seen:
            continue
        seen.add(m.value)
        out.append(m)
    return out
