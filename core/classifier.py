"""Task-type classification aligned with 2026 resume focus points.

Produces multi-label categories per Activity so the enricher can later decide
whether a session is "frontend bug fix" vs "backend deployment" vs "cross-stack".
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from core.schema import Activity


class Category:
    FRONTEND = "frontend"
    BACKEND = "backend"
    FULLSTACK = "fullstack"
    DATABASE = "database"
    DEVOPS = "devops"
    DEPLOYMENT = "deployment"
    BUG_FIX = "bug-fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TESTING = "testing"
    UI_DESIGN = "ui-design"
    DOCS = "docs"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATA_ML = "data-ml"
    API_INTEGRATION = "api-integration"
    AGENT_TOOLING = "agent-tooling"
    RESEARCH = "research"


# (category, regex) — pattern matches against lowercase blob
RULES: list[tuple[str, re.Pattern]] = [
    (Category.FRONTEND, re.compile(r"\b(?:react|next\.js|vue|svelte|tailwind|\.tsx|\.jsx|\.vue|\.svelte|html|css|dom|ui(?:\s+component)?)\b")),
    (Category.BACKEND, re.compile(r"\b(?:fastapi|django|flask|express|nestjs|node|backend|api\s+(?:route|endpoint)|grpc|graphql|middleware|controller|service)\b")),
    (Category.DATABASE, re.compile(r"\b(?:postgres|postgresql|mysql|mongodb|redis|chroma|pinecone|pgvector|supabase|sql|migration|schema|orm|prisma)\b")),
    (Category.DEVOPS, re.compile(r"\b(?:docker|kubernetes|k8s|helm|terraform|ansible|caddy|nginx|cloudflare|ci/?cd|github\s*actions|workflow|pipeline|deploy)\b")),
    (Category.DEPLOYMENT, re.compile(r"(?:部署|上線|上 ?prod|deploy|release|ship|production|rollout|staging)")),
    (Category.BUG_FIX, re.compile(r"(?:\bbug\b|\bfix(?:ed|ing)?\b|\berror\b|\bexception\b|\bcrash\b|\bfail(?:ed|ing|ure)?\b|修(?:正|好)|找原因|報錯|壞了|除錯|排查)")),
    (Category.FEATURE, re.compile(r"(?:implement|add(?:ed|ing)?\s+(?:a\s+)?(?:feature|endpoint|page|component)|build\s+(?:a\s+)?new|新增|加入|實作|開發|做出)")),
    (Category.REFACTOR, re.compile(r"(?:refactor|clean\s*up|restructure|簡化|重構|整理|移除)")),
    (Category.TESTING, re.compile(r"\b(?:pytest|vitest|jest|unittest|mocha|cypress|playwright|smoke\s*test|\bspec\b|\btests?\b|測試)\b")),
    (Category.UI_DESIGN, re.compile(r"(?:figma|mockup|prototype|design\s+system|ux\b|typography|色票|按鈕|介面|排版|spacing|layout)")),
    (Category.DOCS, re.compile(r"(?:readme|documentation|\bdocs?\b|comment|docstring|文件|註解|說明)")),
    (Category.PERFORMANCE, re.compile(r"(?:optimi[sz]e|latency|cache|slow|speed\s*up|throughput|benchmark|profile|加速|效能|延遲)")),
    (Category.SECURITY, re.compile(r"(?:security|auth(?:entication|orization)?|token|oauth|jwt|csrf|xss|sql\s*injection|sanitize|權限|驗證|加密|漏洞)")),
    (Category.DATA_ML, re.compile(r"(?:training|inference|embed(?:ding)?|rag\b|llm|gpt|claude|gemini|dataset|pandas|polars|numpy|scikit|pytorch|tensorflow|jupyter|\.ipynb|model\s+evaluation)")),
    (Category.API_INTEGRATION, re.compile(r"(?:integrate|webhook|api\s+key|third[-\s]?party|\brest\s+api\b|stripe|twilio|slack\s+api|discord\s+api|sdk)")),
    (Category.AGENT_TOOLING, re.compile(r"(?:mcp\b|skill\b|agent|tool\s+use|sub[-\s]?agent|hook\b|claude\s*code|workflow\s*orchestration)")),
    (Category.RESEARCH, re.compile(r"(?:research|explore|investigate|compare|spike|調查|研究|評估|比較)")),
]


def classify(activity: Activity) -> list[str]:
    blob_parts = [
        activity.summary or "",
        " ".join(activity.keywords or []),
        " ".join(activity.files_touched or []),
        activity.project or "",
    ]
    blob = " ".join(blob_parts).lower()
    hits: list[str] = []
    for cat, pat in RULES:
        if pat.search(blob):
            hits.append(cat)

    # derive FULLSTACK from co-occurrence
    if Category.FRONTEND in hits and Category.BACKEND in hits:
        hits.append(Category.FULLSTACK)
    return hits


def tally_categories(activities: Iterable[Activity]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for a in activities:
        for cat in classify(a):
            c[cat] += 1
    return dict(c)


def capability_breadth(category_counts: dict[str, int]) -> int:
    """Return the number of distinct categories the user touched in this group.

    Used as a 'multi-disciplinary' signal on the resume.
    """
    # Collapse fullstack into frontend+backend so it doesn't double-count
    ignore = {Category.FULLSTACK}
    return sum(1 for k in category_counts if k not in ignore and category_counts[k] > 0)
