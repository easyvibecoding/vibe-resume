"""Company-specific résumé-review profiles — distilled from public hiring signals.

Each ``CompanyProfile`` captures what one named employer's reviewers
consistently weight differently from the generic 8-point rubric in
``core/review.py``. The three dimensions compose:

    enrich bias / review bias  =  persona  ×  level  ×  company

- ``core/personas.py``       → reviewer role (tech_lead / hr / exec / …)
- ``core/levels.py``         → seniority bracket (new_grad … staff_plus)
- ``core/company_profiles.py`` (this file) → target employer

Sources: first-party careers pages, engineering blogs, and published
interview guides collected under the "resume_review_templates_progress"
memory. Each profile is a distillation — treat ``review_tips`` as hints
a user can override per résumé version, not hard filters.

Schema is deliberately conservative: every field is a ``tuple[str, ...]``
or a plain string so profiles serialise cleanly if later moved to YAML.
"""
from __future__ import annotations

from dataclasses import dataclass

# Tier groupings used by downstream code to select default format rules
# (e.g. frontier_ai rarely wants a photo; jp often wants 職務経歴書 companion).
TIER_FRONTIER_AI = "frontier_ai"
TIER_AI_UNICORN = "ai_unicorn"
TIER_REGIONAL_AI = "regional_ai"
TIER_TW_LOCAL = "tw_local"
TIER_US_TIER2 = "us_tier2"
TIER_EU = "eu"
TIER_JP = "jp"
TIER_KR = "kr"


@dataclass(frozen=True)
class CompanyProfile:
    key: str
    label: str
    tier: str
    locale_hint: str  # preferred render locale (en_US, ja_JP, ko_KR, zh_TW, …)
    must_haves: tuple[str, ...]
    plus_signals: tuple[str, ...]
    red_flags: tuple[str, ...]
    format_rules: tuple[str, ...]
    keyword_anchors: tuple[str, ...]
    enrich_bias: str
    review_tips: str


COMPANY_PROFILES: dict[str, CompanyProfile] = {
    # ---------------- A. Frontier AI labs ------------------------------------
    "openai": CompanyProfile(
        key="openai",
        label="OpenAI",
        tier=TIER_FRONTIER_AI,
        locale_hint="en_US",
        must_haves=(
            "Evidence of working at significant scale (millions of users or "
            "massive data-processing volumes)",
            "Concrete Python + deep-learning framework depth (PyTorch or TF)",
            "Quantified results — latency, throughput, accuracy, cost — on every "
            "non-trivial bullet",
        ),
        plus_signals=(
            "Distributed systems ownership",
            "Inference optimisation or serving-layer contributions",
            "Open-source contributions to major ML ecosystems",
        ),
        red_flags=(
            "Tool lists without defensible depth (named a framework you cannot "
            "discuss for 10 minutes)",
            "Vague 'improved performance' bullets with no metric",
            "More than two pages for ICs without a research track record",
        ),
        format_rules=(
            "1 page preferred (2 allowed for senior/staff+)",
            "No photo",
            "Lead each role with a verb + metric in the first bullet",
        ),
        keyword_anchors=(
            "PyTorch", "distributed training", "inference", "evals",
            "post-training", "RLHF", "scaling", "latency",
        ),
        enrich_bias=(
            "This résumé will be reviewed by OpenAI. Emphasise scale (users, "
            "data volume, compute), the specific ML stack (PyTorch, CUDA, "
            "distributed trainers, inference engines), and quantified outcomes "
            "on every achievement bullet. Small-team agility is valued: phrases "
            "like 'led a team of 2 to ship X' are preferred over 'was part of a "
            "large org that did Y'. Initiative signals — projects the candidate "
            "scoped and drove — outrank titles."
        ),
        review_tips=(
            "OpenAI reviewers skim for scale + ML depth + quantified impact. "
            "Flag: any bullet without a metric, any tool listed without a "
            "defensible project behind it, any passive 'contributed to' phrasing. "
            "Two-page résumés below staff level get discounted."
        ),
    ),
    "anthropic": CompanyProfile(
        key="anthropic",
        label="Anthropic",
        tier=TIER_FRONTIER_AI,
        locale_hint="en_US",
        must_haves=(
            "At least one substantive LLM project where the candidate drove "
            "intricate model behaviour (not just an API wrapper)",
            "Strong software engineering fundamentals — ML alone is not enough",
            "Authentic AI-safety or alignment engagement (specific paper, "
            "specific concern, specific prior work)",
        ),
        plus_signals=(
            "Public writing or code on interpretability, RLHF, constitutional AI, "
            "scalable oversight, or evaluation methodology",
            "Infrastructure work supporting large-model training or serving",
        ),
        red_flags=(
            "Generic 'passionate about AI' framing with no specific paper or "
            "prior engagement cited",
            "Safety framing that reads as buzzword bingo rather than a "
            "demonstrated research interest",
            "LLM work limited to prompt-engineering demos",
        ),
        format_rules=(
            "1-2 pages, no photo",
            "Cover letter recommended; cite a specific Anthropic paper that "
            "shaped the candidate's interest",
            "Anthropic itself suggests using Claude to tailor the résumé — so "
            "generic boilerplate is especially penalised",
        ),
        keyword_anchors=(
            "LLM", "alignment", "interpretability", "RLHF", "evals",
            "red-teaming", "constitutional AI", "scalable oversight",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Anthropic. Surface LLM projects "
            "where the candidate shaped model behaviour — fine-tuning, RLHF, "
            "eval design, interpretability probes, adversarial testing. Pair "
            "every ML project with the engineering substrate (training infra, "
            "dataset pipeline, eval harness) so the résumé shows both halves "
            "of the ML-engineer profile. If mission alignment can be "
            "demonstrated through prior contributions (OSS, writing, research), "
            "name the specific artefact."
        ),
        review_tips=(
            "Anthropic reviewers read for LLM depth + engineering rigour + "
            "specific-not-generic safety interest. Flag: 'passionate about AI "
            "safety' with no prior engagement; LLM projects that stop at "
            "prompt engineering; cover letters that could have been sent to "
            "any frontier lab."
        ),
    ),
    # ---------------- E. US Tier-2 --------------------------------------------
    "stripe": CompanyProfile(
        key="stripe",
        label="Stripe",
        tier=TIER_US_TIER2,
        locale_hint="en_US",
        must_haves=(
            "Deep skill in at least one of: Python, Go, Ruby, Java, JavaScript",
            "An example of API design where the candidate weighed developer "
            "experience explicitly (clear naming, idempotency, error surfaces)",
            "A bullet showing intellectual honesty — acknowledged a mistake, "
            "reverted a bad decision, learned from an outage",
        ),
        plus_signals=(
            "Open-source contributions with accepted PRs",
            "Payments / fintech / compliance-adjacent experience",
            "Incident ownership with post-mortem narrative",
        ),
        red_flags=(
            "Bragging claims without a specific artefact ('solved scaling for "
            "billions of users' with no named system)",
            "Tool-stacking without defensible depth",
            "API-design bullets framed purely around internal perf, no user "
            "empathy lens",
        ),
        format_rules=(
            "1-2 pages, no photo",
            "Lead bullet per role must be a named shipped outcome, not a "
            "responsibility description",
        ),
        keyword_anchors=(
            "API design", "idempotency", "webhooks", "distributed systems",
            "Go", "Ruby", "Python", "developer experience",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Stripe. For each project, make "
            "the API-or-interface boundary visible — what other engineers / "
            "services consumed this, and what did the candidate do to make "
            "that consumption clearer, safer, or more reliable. Intellectual "
            "honesty is part of Stripe's hiring signal: if a project involved "
            "a reversal, a bad assumption caught late, or a post-mortem, name "
            "it — that narrative outweighs a polished success story."
        ),
        review_tips=(
            "Stripe reviewers scan for API-design empathy and intellectual "
            "honesty. Flag: bullets claiming outcomes without a named system; "
            "pure backend-optimisation framing with no developer-experience "
            "dimension; résumés that never acknowledge a mistake or reversal."
        ),
    ),
    # ---------------- G. Japan — traditional (書類-heavy) --------------------
    "rakuten": CompanyProfile(
        key="rakuten",
        label="楽天 / Rakuten",
        tier=TIER_JP,
        locale_hint="ja_JP",
        must_haves=(
            "Both 履歴書 (personal résumé) AND 職務経歴書 (work-history CV) — "
            "Rakuten screens out at the document stage if either is missing",
            "Chronological company list with precise entry / exit dates and "
            "employment type (正社員 / 契約 / 派遣 / 業務委託)",
            "Per-role: project name, team size, candidate's role, technical "
            "stack, and outcome",
        ),
        plus_signals=(
            "Global-product experience (English-language collaboration)",
            "E-commerce, fintech, or ads-platform background — Rakuten's core "
            "verticals",
            "Demonstrated Japanese business-level language proficiency OR a "
            "clear stance on English-only internal communication",
        ),
        red_flags=(
            "Missing 職務経歴書 — the hiring team treats this as 'not serious'",
            "Narrative-style career summary with no date-precise timeline",
            "Self-promotional superlatives without supporting numbers — "
            "Japanese reviewers discount 最高 / 素晴らしい without proof",
        ),
        format_rules=(
            "履歴書: JIS Z 8303 format preferred; photo required in traditional "
            "document (though Rakuten's English-forward teams may waive it)",
            "職務経歴書: 1-3 pages, reverse-chronological, per-project grid "
            "(期間 / 会社 / プロジェクト / 役割 / 技術 / 成果)",
            "No creative layouts — traditional grids signal professionalism",
        ),
        keyword_anchors=(
            "職務経歴書", "正社員", "プロジェクト", "技術スタック",
            "成果", "担当範囲", "チーム規模",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Rakuten as a traditional Japanese "
            "書類選考 package. Produce a 職務経歴書 structure: for each role, "
            "emit a date range, company name, project title, team size, "
            "candidate's specific 担当範囲 (scope of responsibility), technical "
            "stack, and 成果 (outcome). Use neutral factual phrasing, not "
            "marketing language. Avoid superlatives; Japanese reviewers treat "
            "unbacked claims as weaker than modest verified ones."
        ),
        review_tips=(
            "Rakuten reviewers filter at the document stage: 履歴書 + 職務経歴書 "
            "both required, dates must be precise, each role needs a project "
            "grid (期間/会社/プロジェクト/役割/技術/成果). Flag: narrative paragraphs "
            "instead of grids; missing team-size or scope; superlatives without "
            "numbers."
        ),
    ),
}


def get_company(key: str | None) -> CompanyProfile | None:
    if not key:
        return None
    return COMPANY_PROFILES.get(key)


def list_company_keys() -> list[str]:
    return list(COMPANY_PROFILES.keys())


def list_by_tier(tier: str) -> list[CompanyProfile]:
    return [p for p in COMPANY_PROFILES.values() if p.tier == tier]
