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


# Context-based metric classification (#62): even an impact-shaped value (%/x)
# can be noise — a UI threshold, CSS value, model-spec, or URL fragment. Classify
# from the surrounding text so iterate surfaces ONLY genuine, surfaceable metrics
# (turning the in-code "never fabricate" guardrail into a signal the agent sees).
_KIND_RULES: list[tuple[str, re.Pattern[str]]] = [
    # #79 (security/privacy): a value sliced from a secret/key or a UUID hex-group
    # must never surface — e.g. `487B` from `CWA-BF1B60DA-2A68-487B-…`. Match the
    # common key prefixes plus the dash-delimited hex-group (UUID/key) shape.
    ("secret_fragment", re.compile(
        r"(?i)\bCWA-|\bsk-[a-z0-9]|\bghp_|\bgho_|\bgithub_pat_|AIza[0-9A-Za-z_-]"
        r"|x-access-token|api[_-]?key|secret|bearer\s|"
        r"[0-9A-Fa-f]{4,}-[0-9A-Fa-f]{2,}-[0-9A-Fa-f]{2,}")),
    # #79: hash/digest context — `256 h` is from `SHA-256`, not hours.
    ("hash_digest", re.compile(r"(?i)\bsha-?\d{1,3}\b|\bmd5\b|\bsha1\b|\bdigest\b|\bchecksum\b|\bhash\b")),
    # #79: ANSI colour codes / stack-trace line markers (`0m`/`4m`, `line 42`).
    ("ansi_marker", re.compile(r"(?i)\x1b\[|\[[0-9;]+m\b|traceback|stack\s*trace|\bline\s+\d+\b")),
    # #79: path/UUID fragments (`4d`/`8d` from `~/.claude/image-cache/<uuid>`).
    ("path_fragment", re.compile(r"(?i)image-cache|/\.?cache/|~/\.|/var/|/tmp/|[0-9a-f]{8}-[0-9a-f]{4}-")),
    # #79: the enricher's OWN prompt-template text (self-reference like
    # `寫「…壓縮約 40%」`, `e.g. …`, `範例:…`) — an example, not the user's metric.
    ("prompt_example", re.compile(r"(?i)寫「|填「|填入|占位|placeholder|範例|示例|例如|\be\.g\.|for example|such as")),
    ("url_fragment", re.compile(r"(?i)https?://|%[0-9a-f]{2}|\burl\b|encoded|\.jsonl")),
    ("css_value", re.compile(r"(?i)max-width|min-width|width\s*:|height\s*:|\bpx\b|margin|padding|\bvh\b|\bvw\b|css|tailwind|rounded|flex")),
    ("model_spec", re.compile(r"(?i)\bcontext\b|opus|sonnet|haiku|gpt-|co-?author|token window|context window|參數|模型")),
    ("id_number", re.compile(r"#\s*\d|\bissue\s*\d|\bpull request\b|\bPR\s*#")),  # #67: PR/issue refs
    # #67/#69: explicit band/threshold cues (color words, 邊框/門檻, comparison ops)
    # are UI thresholds — but a BARE X-Y% range is NOT (handled below, #69).
    ("ui_threshold", re.compile(r"(?i)threshold|confidence|信心|閾值|門檻|邊框|色|紅|橙|綠|黃|band|color|color-?cod|[<>≤≥]\s*\d+\s*%")),
]
# #67: a value whose numeric core is a 4-digit year is a date fragment, not a
# metric — even when a stray unit is glued on (e.g. "2026 h").
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}\b")
# #69: a bare X-Y% range (no band/threshold cue) is a range-expressed metric.
_RANGE_RE = re.compile(r"\d\s*[-–~]\s*\d+\s*%")
_PERF_RE = re.compile(
    r"(?i)reduc|cut|decreas|improv|faster|slower|latency|throughput|optimi|saved?|"
    r"speed|減少|優化|提升|壓縮|加速|節省|延遲|吞吐|降低"
)
_COMMIT_RE = re.compile(r"(?i)commit|numstat|\bpr\b|pull request|diff")


def classify_metric(value: str, context: str, source_ref: str = "") -> tuple[str, str, bool]:
    """Return (kind, confidence, safe_to_surface) for a candidate metric (#62).

    kind ∈ {real_metric, ui_threshold, css_value, model_spec, url_fragment};
    confidence ∈ {high (commit-confirmed), medium (mentioned), low}. Only a
    real_metric with non-low confidence is safe for the agent to surface."""
    ctx = context or ""
    if _YEAR_RE.match(value.strip()):
        return "date_fragment", "low", False
    for kind, rx in _KIND_RULES:
        if rx.search(ctx):
            return kind, "low", False
    committed = _COMMIT_RE.search(source_ref) or _COMMIT_RE.search(ctx)
    # #69: a bare X-Y% range with no improvement verb and no commit provenance is
    # ambiguous — surface it WITH CAUTION (low confidence) rather than hiding it.
    # A hidden true metric is costlier than a low-confidence true positive the
    # agent can vet. (With an improvement verb / commit it falls through to a
    # higher-confidence real_metric below.)
    if _RANGE_RE.search(ctx) and not _PERF_RE.search(ctx) and not committed:
        return "real_metric", "low", True
    # genuine metric — grade confidence by provenance
    conf = "high" if committed else "medium"
    return "real_metric", conf, True


@dataclass
class MetricCandidate:
    value: str          # the literal quantity found, e.g. "40%", "2k", "3x"
    source_ref: str     # raw_ref / session for traceability
    context: str        # snippet of the activity it came from
    kind: str = "real_metric"        # #62 classification
    confidence: str = "medium"
    safe_to_surface: bool = True

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
                ctx = _snippet(summary, val)
                kind, conf, safe = classify_metric(val, ctx, ref)
                metrics.append(MetricCandidate(value=val, source_ref=ref, context=ctx,
                                               kind=kind, confidence=conf, safe_to_surface=safe))
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
    signals, never invented or estimated (P1.1 guardrail). #62: only metrics
    classified `safe_to_surface` (real_metric, non-low confidence) are returned;
    UI thresholds / CSS / model-specs / URL fragments are filtered out so the
    agent isn't handed noise that invites fabrication."""
    low = (surfaced_text or "").lower()
    out: list[MetricCandidate] = []
    seen: set[str] = set()
    for m in evidence.candidate_metrics:
        if not m.safe_to_surface or m.value.lower() in low or m.value in seen:
            continue
        seen.add(m.value)
        out.append(m)
    return out
