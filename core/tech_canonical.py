"""Canonical display names and categorization for tech terms."""
from __future__ import annotations

# lowercase key → display form
CANONICAL: dict[str, str] = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "flutter": "Flutter",
    "swift": "Swift",
    "swiftui": "SwiftUI",
    "node": "Node.js",
    "nodejs": "Node.js",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "nextjs": "Next.js",
    "next": "Next.js",
    "nuxt": "Nuxt",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "helm": "Helm",
    "terraform": "Terraform",
    "nginx": "Nginx",
    "caddy": "Caddy",
    "cloudflare": "Cloudflare",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "chroma": "ChromaDB",
    "chromadb": "ChromaDB",
    "pinecone": "Pinecone",
    "pgvector": "pgvector",
    "supabase": "Supabase",
    "tailwind": "Tailwind CSS",
    "websocket": "WebSocket",
    "websockets": "WebSocket",
    "rag": "RAG",
    "llm": "LLM",
    "mcp": "MCP",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "jupyter": "Jupyter",
    "streamlit": "Streamlit",
    "fastmcp": "FastMCP",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "claude code": "Claude Code",
    "cursor": "Cursor",
    "copilot": "GitHub Copilot",
    "pydantic": "Pydantic",
    "celery": "Celery",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "agent workflow": "Agent Workflow",
    "bing webmasters": "Bing Webmasters",
    "seo": "SEO",
    "automation": "Automation",
    "full-stack": "Full-stack",
}

# category → list of canonical names (for grouped skills section)
CATEGORIES: dict[str, list[str]] = {
    "Frontend": [
        "React", "Vue", "Svelte", "Next.js", "Nuxt", "Tailwind CSS",
        "TypeScript", "JavaScript", "Flutter", "SwiftUI",
    ],
    "Backend": [
        "FastAPI", "Django", "Flask", "Node.js", "Python", "Pydantic", "Celery",
    ],
    "Database": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "ChromaDB", "Pinecone",
        "pgvector", "Supabase",
    ],
    "DevOps / Cloud": [
        "Docker", "Kubernetes", "Helm", "Terraform", "Nginx", "Caddy",
        "Cloudflare", "AWS", "GCP", "Azure",
    ],
    "AI / Data": [
        "RAG", "LLM", "MCP", "LangChain", "LlamaIndex", "PyTorch", "TensorFlow",
        "Jupyter", "Agent Workflow",
    ],
    "Realtime / Integration": [
        "WebSocket", "Kafka", "RabbitMQ", "Bing Webmasters", "Automation", "SEO",
    ],
    "AI Dev Tools": [
        "Claude Code", "Cursor", "GitHub Copilot", "FastMCP",
    ],
}


def canonicalize(raw: str) -> str:
    """Map a raw tech string to its canonical display form.

    - ``"postgres"`` / ``"POSTGRES"`` / ``"postgresql"`` → ``"PostgreSQL"``
    - Unknown but non-empty input passes through stripped (the enricher may
      legitimately emit a fresh 2026 stack name we haven't aliased yet).
    - Empty / whitespace-only input returns ``""`` — both downstream callers
      (``split_hard_skills`` and ``canonical_list``) already skip falsy
      returns, so this keeps stray blanks out of the Skills section.
    """
    stripped = raw.strip()
    if not stripped:
        return ""
    return CANONICAL.get(stripped.lower(), stripped)


# Set of canonical display names that count as "hard technical skills".
# Anything else returned by the enricher (SEO, Agent Workflow, Content Curation, ...)
# is classified as a domain/capability tag and rendered separately.
HARD_SKILLS: set[str] = set()
for members in CATEGORIES.values():
    HARD_SKILLS.update(members)


# Source identifiers → display names
SOURCE_DISPLAY: dict[str, str] = {
    "claude-code": "Claude Code",
    "claude-ai": "Claude.ai",
    "claude-desktop": "Claude Desktop",
    "chatgpt": "ChatGPT",
    "cursor": "Cursor",
    "cline": "Cline",
    "continue": "Continue.dev",
    "aider": "Aider",
    "windsurf": "Windsurf",
    "copilot-vscode": "GitHub Copilot (VS Code)",
    "copilot-activity": "Microsoft Copilot",
    "zed": "Zed AI",
    "gemini": "Gemini",
    "grok": "Grok",
    "perplexity": "Perplexity",
    "mistral": "Mistral Le Chat",
    "poe": "Poe",
    "notebooklm": "NotebookLM",
    "sora": "Sora",
    "comfyui": "ComfyUI",
    "a1111": "Automatic1111",
    "midjourney": "Midjourney",
    "runway": "Runway",
    "suno": "Suno",
    "elevenlabs": "ElevenLabs",
    "heygen": "HeyGen",
    "descript": "Descript",
    "git": "Git Commits",
    "devin": "Devin",
    "other": "Other",
}


# Task category keys → human-readable labels for the rendered resume.
CATEGORY_LABEL: dict[str, str] = {
    "frontend": "Frontend",
    "backend": "Backend",
    "fullstack": "Full-stack",
    "database": "Database",
    "devops": "DevOps / Infrastructure",
    "deployment": "Deployment",
    "bug-fix": "Bug fixes",
    "feature": "New features",
    "refactor": "Refactoring",
    "testing": "Testing",
    "ui-design": "UI design",
    "docs": "Documentation",
    "performance": "Performance",
    "security": "Security",
    "data-ml": "Data / ML",
    "api-integration": "API integration",
    "agent-tooling": "Agent tooling",
    "research": "Research / Exploration",
}


def source_display(raw: str) -> str:
    return SOURCE_DISPLAY.get(raw, raw)


def category_label(raw: str) -> str:
    return CATEGORY_LABEL.get(raw, raw)


def split_hard_skills(items: list[str]) -> tuple[list[str], list[str]]:
    """Return (hard_skills, domain_tags). Both dedupe-preserve order."""
    hard: list[str] = []
    domain: list[str] = []
    seen_h: set[str] = set()
    seen_d: set[str] = set()
    for raw in items:
        c = canonicalize(raw)
        if not c:
            continue
        if c in HARD_SKILLS:
            if c not in seen_h:
                seen_h.add(c)
                hard.append(c)
        else:
            # case-insensitive dedupe for tags
            low = c.lower()
            if low not in seen_d:
                seen_d.add(low)
                domain.append(c)
    return hard, domain


def canonical_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        c = canonicalize(it)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def group_by_category(items: list[str]) -> dict[str, list[str]]:
    """Return {category: [tech...]}; 'Other' holds anything unrecognized."""
    buckets: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    buckets["Other"] = []
    for it in items:
        placed = False
        for cat, members in CATEGORIES.items():
            if it in members:
                buckets[cat].append(it)
                placed = True
                break
        if not placed:
            buckets["Other"].append(it)
    return {k: v for k, v in buckets.items() if v}
