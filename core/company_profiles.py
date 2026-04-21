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
    "google_deepmind": CompanyProfile(
        key="google_deepmind",
        label="Google DeepMind",
        tier=TIER_FRONTIER_AI,
        locale_hint="en_US",
        must_haves=(
            "Named research projects with depth — every listed project must be "
            "something the candidate can discuss for 30+ minutes",
            "One-page résumé unless senior/research-heavy (two pages max)",
            "JD-keyword alignment — DeepMind screens with keyword overlap first",
        ),
        plus_signals=(
            "Peer-reviewed publications at NeurIPS / ICML / ICLR / JMLR",
            "Gemini, AlphaFold, RL, or interpretability-adjacent contributions",
            "Strong referral or mutual-network connection — still a meaningful "
            "signal in DeepMind's funnel",
        ),
        red_flags=(
            "Project list without depth — every project must withstand a "
            "technical deep-dive",
            "Two-plus pages without commensurate research record",
            "Generic ML blurbs instead of project-specific narratives",
        ),
        format_rules=(
            "1 page (2 allowed for PhD / senior research)",
            "No photo",
            "Per-project: what you built, what question it answered, what the "
            "result was — in that order",
        ),
        keyword_anchors=(
            "research", "publication", "RL", "transformers", "evaluation",
            "benchmark", "dataset", "reproducibility",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Google DeepMind. Treat every "
            "project entry as a mini-abstract: problem statement, method, "
            "concrete result. Prefer naming specific artefacts (paper titles, "
            "benchmark deltas, open-source repos) over listing frameworks. "
            "Match keywords to the target job description — DeepMind's "
            "screener weights keyword overlap heavily — but never fabricate "
            "experience to hit a keyword."
        ),
        review_tips=(
            "DeepMind reviewers expect every project to be defensible in a "
            "technical deep-dive. Flag: project lists without outcomes, "
            "résumés over one page without a research record, keyword-"
            "stuffed skill sections disconnected from the project narrative."
        ),
    ),
    "meta_fair": CompanyProfile(
        key="meta_fair",
        label="Meta FAIR",
        tier=TIER_FRONTIER_AI,
        locale_hint="en_US",
        must_haves=(
            "PhD (or equivalent practical experience) in CS / ML / stats / "
            "applied math",
            "Peer-reviewed publications in AI/ML venues — FAIR filters hard "
            "on this at the résumé stage",
            "Demonstrable Python / PyTorch proficiency with public code",
        ),
        plus_signals=(
            "Prior postdoc / faculty / industry research lab experience",
            "Agents, reasoning, planning, or multimodal-model work",
            "Grants, fellowships, patents, or top-tier competition placements",
        ),
        red_flags=(
            "No publications listed for a research-scientist role — this is a "
            "near-automatic filter at FAIR",
            "Industry-only track record framed as research — FAIR looks for "
            "peer-reviewed contribution, not internal shipping",
            "Missing dataset / benchmark / code links under each contribution",
        ),
        format_rules=(
            "1-2 pages; publication list can overflow to an extra page",
            "No photo",
            "Publications section must list venue + year + role (first author, "
            "co-author) explicitly",
        ),
        keyword_anchors=(
            "publication", "PhD", "PyTorch", "agents", "reasoning",
            "multimodal", "benchmark", "dataset",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Meta FAIR. Publications are the "
            "primary currency — surface them first, with venue, year, and "
            "author position. For each paper or project, name the dataset, "
            "the benchmark, and what the candidate contributed specifically "
            "versus co-authors. Industry engineering work, if present, should "
            "be framed as 'infrastructure enabling X paper' rather than as "
            "shipping stories."
        ),
        review_tips=(
            "FAIR reviewers filter on publications + venue quality + "
            "reproducibility artefacts. Flag: research-scientist résumé "
            "without peer-reviewed publications; papers listed without "
            "venue; industry bullets shaped like product-launch narratives "
            "instead of research contributions."
        ),
    ),
    "amazon_aws": CompanyProfile(
        key="amazon_aws",
        label="Amazon AWS (Applied Scientist)",
        tier=TIER_FRONTIER_AI,
        locale_hint="en_US",
        must_haves=(
            "PhD in CS / ML / stats / related — or MS with 4+ years industry "
            "ML experience",
            "Every past role must survive a 'Science Depth' deep-dive: what, "
            "why, how, outcome, what you'd do differently",
            "Production-scale ML experience (SageMaker, Spark, EMR, or "
            "equivalent)",
        ),
        plus_signals=(
            "Publications in NLP / RL / GenAI / LLMs at recognised venues",
            "Amazon Leadership-Principle-shaped bullets (Customer Obsession, "
            "Ownership, Dive Deep, Bias for Action)",
            "Cost-saving or operational-efficiency wins at scale",
        ),
        red_flags=(
            "Vague 'contributed to' bullets that collapse under deep-dive "
            "questioning",
            "No Leadership Principle alignment visible in narrative",
            "Research framing with no connection to business-measurable "
            "outcome (AWS blends research + applied)",
        ),
        format_rules=(
            "1-2 pages",
            "STAR-shaped bullets (Situation, Task, Action, Result) are the "
            "house style for deep-dive prep — résumé should foreshadow them",
            "Include AWS / cloud keywords (SageMaker, S3, EC2, Lambda) so "
            "ATS recognises relevance",
        ),
        keyword_anchors=(
            "SageMaker", "Spark", "EMR", "Leadership Principles",
            "customer obsession", "dive deep", "LLM", "A/B test",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Amazon AWS for an Applied "
            "Scientist or ML Engineer role. Every bullet must be something "
            "the candidate is ready to deep-dive on for 10+ minutes — no "
            "bragging claims without an underlying project. Use STAR shape "
            "(Situation, Task, Action, Result) implicitly. Name AWS-native "
            "services where relevant so the résumé surfaces in Amazon's "
            "internal ATS."
        ),
        review_tips=(
            "AWS reviewers will deep-dive any bullet in the on-site interview. "
            "Flag: any claim the candidate cannot support with a 5-minute "
            "narrative; missing Leadership-Principle-shaped framing; research "
            "bullets with no business outcome."
        ),
    ),
    "mercari": CompanyProfile(
        key="mercari",
        label="メルカリ / Mercari",
        tier=TIER_JP,
        locale_hint="ja_JP",
        must_haves=(
            "職務経歴書 (work-history CV) with *narrative between roles* — "
            "Mercari's HR explicitly reads for the story linking each move to "
            "the next",
            "Public artefact trail — GitHub profile, tech blog, conference "
            "talks; Mercari's HR states they always read submitted profiles",
            "Clear motivation for joining Mercari specifically (not 'any "
            "Japanese tech company')",
        ),
        plus_signals=(
            "OSS contributions to Go / Kubernetes / cloud-native ecosystem",
            "English-capable engineering (Mercari runs English-first for "
            "product dev)",
            "C2C-marketplace, trust-and-safety, or ML-for-recommendation "
            "experience",
        ),
        red_flags=(
            "履歴書 that is clearly template-filled with no personality — "
            "Mercari's HR states they 'basically don't read' a hollow 履歴書",
            "Job-hopping history with no connecting narrative between roles",
            "Missing public-artefact links (no GitHub, no blog, no talks) "
            "for an engineer with 3+ years of experience",
        ),
        format_rules=(
            "履歴書 + 職務経歴書 both required, but 職務経歴書 is the primary "
            "document — it should read as a cohesive story, not a list",
            "Photo optional (Mercari's modernised hiring allows no-photo)",
            "English résumé accepted and often preferred for engineering roles",
        ),
        keyword_anchors=(
            "職務経歴書", "GitHub", "OSS", "Go", "Kubernetes",
            "microservices", "C2C", "trust and safety",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Mercari — a 'new-school' "
            "Japanese tech company that reads 職務経歴書 and public-artefact "
            "trails over 履歴書 formalities. For each role, explain *why* "
            "the candidate moved and how that move connected to the next — "
            "Mercari's HR explicitly evaluates this narrative thread. Surface "
            "GitHub repos, blog posts, and conference talks; the review team "
            "will follow the links."
        ),
        review_tips=(
            "Mercari reviewers follow public-artefact links and read for "
            "inter-role narrative. Flag: 職務経歴書 that reads as a bullet "
            "list with no thread; missing GitHub / blog / talks for engineers "
            "with non-trivial experience; generic 'I like Japan' motivation "
            "that applies to any JP company."
        ),
    ),
    # ---------------- D. Taiwan local ----------------------------------------
    "taiwan_mobile": CompanyProfile(
        key="taiwan_mobile",
        label="台灣大哥大 / Taiwan Mobile",
        tier=TIER_TW_LOCAL,
        locale_hint="zh_TW",
        must_haves=(
            "Java stack depth (Spring / RESTful APIs / relational DB)",
            "Cross-team coordination experience — telco IT stacks span "
            "billing, CRM, OTT, network, and third-party integration",
            "Stable employment pattern — telcos discount short-tenure "
            "job-hopping for stability-oriented back-office roles",
        ),
        plus_signals=(
            "Telco billing / OSS/BSS / CRM / subscription-management "
            "experience",
            "OTT / streaming / payments third-party integration work",
            "Maintenance + rewrite of legacy systems (vs. only greenfield)",
        ),
        red_flags=(
            "Adjective-heavy résumé without quantification (Taiwanese "
            "recruiters increasingly penalise 熟悉 / 精通 / 負責 soup)",
            "Job-hop every year without reason — signals flight risk for "
            "stable-track roles",
            "Only describes tasks, never outcomes — 104-style lint failure",
        ),
        format_rules=(
            "中文 (zh_TW) or 中英對照 acceptable",
            "1-2 pages; tables/grids for technical-stack section are fine",
            "Company + role + dates + tech stack + quantified outcome per "
            "position",
        ),
        keyword_anchors=(
            "Java", "Spring", "REST API", "第三方串接", "跨部門",
            "系統維運", "CRM", "計費",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Taiwan Mobile. Use Traditional "
            "Chinese. For each role, show cross-team coordination (業務 / "
            "產品 / 網管 / 客服) explicitly — telco IT work is inherently "
            "cross-functional. Replace adjectives (熟悉 / 精通 / 負責) with "
            "verbs + quantified outcomes. Surface stable tenure and "
            "maintenance / migration work, not only greenfield shipping."
        ),
        review_tips=(
            "Taiwan Mobile reviewers weigh stability + cross-team coordination "
            "+ telco-stack familiarity. Flag: adjective-heavy phrasing without "
            "metrics; pure task descriptions with no outcome line; missing "
            "cross-team or third-party-integration evidence for senior roles."
        ),
    ),
    # ---------------- H. Korea -----------------------------------------------
    "kakao": CompanyProfile(
        key="kakao",
        label="Kakao",
        tier=TIER_KR,
        locale_hint="ko_KR",
        must_haves=(
            "Hangul-first résumé with English technical terms in parentheses "
            "— Korean ATS scans Hangul first, then English equivalents",
            "Demonstrated scale experience (Kakao serves 90%+ of Korean "
            "messaging traffic)",
            "Clear tenure timeline with month-level precision",
        ),
        plus_signals=(
            "Prior NKLCB experience (Naver / Kakao / Line / Coupang / Baedal "
            "Minjok / Danggeun / Toss) — widely used as a trust signal "
            "across the Korean tech network",
            "Kakao / KakaoBank / KakaoPay / KakaoGames ecosystem work",
            "High-QPS backend, messaging, or payments experience",
        ),
        red_flags=(
            "English-only résumé without Hangul fallback — misses the "
            "Korean ATS first pass",
            "Missing photo in traditional submission channels (photo is "
            "standard for most Korean résumés)",
            "No mention of tenure duration — Korean reviewers read this "
            "alongside the company name",
        ),
        format_rules=(
            "Hangul primary + English tech terms; photo commonly expected",
            "Reverse-chronological; company names in Korean with English "
            "short forms",
            "1-2 pages",
        ),
        keyword_anchors=(
            "카카오", "대규모 트래픽", "백엔드", "메시징", "결제",
            "Java", "Kotlin", "MSA",
        ),
        enrich_bias=(
            "This résumé will be reviewed by Kakao. Produce Korean "
            "(Hangul) as the primary language with English technical terms in "
            "parentheses — Korean ATS scans Hangul first. Surface scale "
            "(QPS, DAU, messaging volume) using numerical values that match "
            "Kakao's own product scale. If the candidate has prior NKLCB "
            "experience, it is a trust signal — name the company plainly."
        ),
        review_tips=(
            "Kakao reviewers scan for Hangul primary + scale numbers + NKLCB "
            "lineage. Flag: English-only résumé; missing tenure months; "
            "backend roles without a QPS / DAU / messaging-volume scale line."
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
