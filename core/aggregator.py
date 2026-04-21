"""Normalize cached activities and group by project."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import orjson
from rich.console import Console

from core.classifier import capability_breadth, tally_categories
from core.privacy import PrivacyFilter
from core.schema import Activity, ProjectGroup
from core.tech_canonical import canonical_list
from extractors.base import load_activities

console = Console()

ROOT = Path(__file__).parent.parent
GROUPS_PATH = ROOT / "data" / "cache" / "_project_groups.json"
OBSERVED_SUMMARY_PATH = ROOT / "data" / "cache" / "_observed_summary.json"
WINDOW_STATS_PATH = ROOT / "data" / "cache" / "_window_stats.json"

# Simple tech-stack detector — matches against summary, keywords, files_touched.
TECH_MARKERS = {
    "python": r"\b(?:python|\.py\b|pip|poetry|uv\b|pytest|fastapi|django|flask|pydantic|celery|langchain|llamaindex)\b",
    "typescript": r"\b(?:typescript|\.tsx?\b|tsconfig|vite|esbuild)\b",
    "react": r"\b(?:react|next\.js|nextjs|jsx|tsx)\b",
    "vue": r"\b(?:vue|nuxt)\b",
    "flutter": r"\b(?:flutter|dart\b)\b",
    "swift": r"\b(?:swift|swiftui|\.swift\b)\b",
    "node": r"\b(?:node\.js|nodejs|npm|pnpm|yarn)\b",
    "docker": r"\b(?:docker|Dockerfile|docker-compose)\b",
    "kubernetes": r"\b(?:kubernetes|kubectl|helm|k8s)\b",
    "postgres": r"\b(?:postgres|postgresql|pgvector)\b",
    "redis": r"\bredis\b",
    "chroma": r"\bchromadb?\b",
    "rag": r"\b(?:rag|retrieval[-\s]augmented|vector search)\b",
    "mcp": r"\b(?:mcp server|model context protocol)\b",
    "caddy": r"\bcaddy\b",
    "cloudflare": r"\bcloudflare\b",
    "fastapi": r"\bfastapi\b",
    "websocket": r"\bwebsockets?\b",
    "tailwind": r"\btailwind\b",
    "aws": r"\b(?:aws|s3|ec2|lambda|dynamodb)\b",
    "gcp": r"\b(?:gcp|google cloud|bigquery|cloud run)\b",
    "supabase": r"\bsupabase\b",
    "langchain": r"\blangchain\b",
    "llamaindex": r"\bllama[-\s]?index\b",
    "streamlit": r"\bstreamlit\b",
    "jupyter": r"\bjupyter|\.ipynb\b",
}


def _infer_tech(act: Activity) -> list[str]:
    blob = " ".join(
        [
            act.summary or "",
            " ".join(act.keywords or []),
            " ".join(act.files_touched or []),
            act.project or "",
        ]
    ).lower()
    hits = []
    for name, pat in TECH_MARKERS.items():
        if re.search(pat, blob, re.IGNORECASE):
            hits.append(name)
    return hits


HASH_ID_RE = re.compile(r"^[0-9a-f]{20,}$")
NOISE_SUBSTRINGS = {
    "new chat",
    "cursor:misc",
    "claude-desktop:misc",
    "untitled",
    "(not on disk)",
}
# Path leaf components that indicate scratch/test/home-root — filter the group.
# We include the current user's home-directory leaf automatically so that
# "Users/<username>" (generic bucket) is dropped regardless of who runs this.
NOISE_LEAFS: set[str] = {"tmp", "temp", "private", Path.home().name.lower()}


def _humanize_name(raw: str, path: str | None, activities: list[Activity]) -> str:
    """Turn path-like names into reader-friendly project labels."""
    if path:
        base = path.rstrip("/").split("/")[-1]
        if base and not HASH_ID_RE.match(base.lower()):
            return base
    if HASH_ID_RE.match(raw.lower().split("/")[-1]):
        for a in activities:
            s = (a.summary or "").strip()
            if s:
                return s[:25].replace("\n", " ").rstrip(" ,.·|")
        return raw[:8] + "…"
    leaf = raw.split("/")[-1] or raw
    # "Add Required Parameter for Restaurant List Screen" → keep; but chinese long prompts → truncate
    if len(leaf) > 30:
        return leaf[:25].rstrip() + "…"
    return leaf


def _is_meaningful(raw_key: str, g: ProjectGroup, min_sessions: int) -> bool:
    key_lc = raw_key.lower().strip()
    if any(sub in key_lc for sub in NOISE_SUBSTRINGS):
        return False
    leaf = key_lc.split("/")[-1].lstrip(".")
    if leaf in NOISE_LEAFS:
        return False
    if HASH_ID_RE.match(leaf) and g.total_sessions < 2:
        return False
    if g.total_sessions < min_sessions and g.capability_breadth <= 1:
        return False
    if not g.tech_stack and g.capability_breadth == 0 and g.total_sessions < 3:
        return False
    return True


def _significance(g: ProjectGroup) -> float:
    """Higher = more prominent. Used to rank projects on the resume."""
    days = max((g.last_activity - g.first_activity).days, 1)
    sessions = max(g.total_sessions, 1)
    breadth = max(g.capability_breadth, 1)
    return sessions * breadth * math.log1p(days)


def _make_headline(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    total = sum(counts.values())
    if total == 0:
        return None
    # Exclude fullstack (derived) and sort by share
    filtered = {k: v for k, v in counts.items() if k != "fullstack"}
    top = sorted(filtered.items(), key=lambda kv: -kv[1])[:4]
    parts = [f"{k} {v*100//total}%" for k, v in top if v * 100 // total >= 5]
    if not parts:
        return None
    return " / ".join(parts)


def _project_key(act: Activity) -> str:
    if act.project:
        # Normalize absolute path: use last two segments for readability
        p = act.project.rstrip("/")
        if "/" in p:
            parts = p.split("/")
            return "/".join(parts[-2:]) if len(parts) >= 2 else p
        return p
    return f"{act.source.value}:misc"


def aggregate_from_cache(cfg: dict[str, Any], cache_dir: Path) -> list[ProjectGroup]:
    pf = PrivacyFilter(cfg)
    all_acts: list[Activity] = []
    for f in cache_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        for a in load_activities(f):
            pa = pf.apply(a)
            if pa is not None:
                all_acts.append(pa)

    # Preserve enrichment from any previous run, keyed by display name.
    prior_enrich: dict[str, dict[str, Any]] = {}
    if GROUPS_PATH.exists():
        try:
            for g in orjson.loads(GROUPS_PATH.read_bytes()):
                if g.get("achievements") or g.get("summary"):
                    prior_enrich[g["name"]] = {
                        "summary": g.get("summary"),
                        "achievements": g.get("achievements"),
                        "headline": g.get("headline"),
                        "tech_stack": g.get("tech_stack"),
                        "domain_tags": g.get("domain_tags"),
                    }
        except (orjson.JSONDecodeError, KeyError):
            pass

    # Load project_metrics from profile.yaml, if present.
    user_metrics: dict[str, list[str]] = {}
    profile_path = ROOT / "profile.yaml"
    if profile_path.exists():
        try:
            import yaml

            pdata = yaml.safe_load(profile_path.read_text()) or {}
            user_metrics = pdata.get("project_metrics") or {}
        except Exception:
            pass

    buckets: dict[str, list[Activity]] = defaultdict(list)
    for a in all_acts:
        buckets[_project_key(a)].append(a)

    groups: list[ProjectGroup] = []
    raw_keys: list[str] = []
    for key, acts in buckets.items():
        raw_keys.append(key)
        acts.sort(key=lambda a: a.timestamp_start)
        sources = sorted({a.source for a in acts}, key=lambda s: s.value)
        tech: set[str] = set()
        for a in acts:
            tech.update(_infer_tech(a))
            tech.update(a.tech_stack or [])

        path_val = None
        for a in acts:
            if a.project and "/" in a.project:
                path_val = a.project
                break

        cat_counts = tally_categories(acts)
        breadth = capability_breadth(cat_counts)
        headline = _make_headline(cat_counts)
        display_name = _humanize_name(key, path_val, acts)
        canonical_tech = canonical_list(sorted(tech))

        prior = prior_enrich.get(display_name, {})
        # Look up user-supplied metrics by project name (case/fuzzy tolerant).
        project_metrics: list[str] = []
        for k, v in user_metrics.items():
            if k.lower() in display_name.lower() or display_name.lower() in k.lower():
                if isinstance(v, list):
                    project_metrics = [str(m) for m in v]
                break

        grp = ProjectGroup(
            name=display_name,
            path=path_val,
            first_activity=acts[0].timestamp_start,
            last_activity=max(a.timestamp_end or a.timestamp_start for a in acts),
            total_sessions=len(acts),
            tech_stack=prior.get("tech_stack") or canonical_tech,
            sources=list(sources),
            activities=acts,
            category_counts=cat_counts,
            capability_breadth=breadth,
            headline=prior.get("headline") or headline,
            summary=prior.get("summary") or "",
            achievements=prior.get("achievements") or [],
            domain_tags=prior.get("domain_tags") or [],
            metrics=project_metrics,
        )
        groups.append(grp)

    min_sessions = int(cfg.get("render", {}).get("min_sessions") or 2)
    groups = [
        g for (raw_key, g) in zip(raw_keys, groups) if _is_meaningful(raw_key, g, min_sessions)
    ]
    groups.sort(key=_significance, reverse=True)

    GROUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GROUPS_PATH.write_bytes(
        orjson.dumps(
            [g.model_dump(mode="json") for g in groups], option=orjson.OPT_INDENT_2
        )
    )
    _write_observed_summary(groups)
    _write_window_stats(groups, cfg)
    console.print(
        f"[green]aggregated[/green] {len(all_acts)} activities → {len(groups)} project groups"
    )
    return groups


def _write_window_stats(groups: list[ProjectGroup], cfg: dict[str, Any]) -> None:
    from core.stats import compute_window_stats

    windows = cfg.get("stats", {}).get("windows") or [30, 7]
    payload: dict[str, Any] = {}
    for w in windows:
        stats = compute_window_stats(groups, window_days=int(w))
        payload[f"last_{w}d"] = stats.to_dict()
    WINDOW_STATS_PATH.write_bytes(
        orjson.dumps(payload, option=orjson.OPT_INDENT_2)
    )


def load_window_stats() -> dict | None:
    if not WINDOW_STATS_PATH.exists():
        return None
    return orjson.loads(WINDOW_STATS_PATH.read_bytes())


def _write_observed_summary(groups: list[ProjectGroup]) -> None:
    """Compute a headline paragraph describing the user's observed range."""
    if not groups:
        return
    first = min(g.first_activity for g in groups)
    last = max(g.last_activity for g in groups)
    total_sessions = sum(g.total_sessions for g in groups)

    # pick top 3 projects by significance
    top = groups[:3]
    cat_counter: dict[str, int] = {}
    for g in groups:
        for c, n in (g.category_counts or {}).items():
            if c == "fullstack":
                continue
            cat_counter[c] = cat_counter.get(c, 0) + n
    top_caps = sorted(cat_counter, key=lambda k: -cat_counter[k])[:5]

    all_tech: dict[str, int] = {}
    for g in groups:
        for t in g.tech_stack:
            all_tech[t] = all_tech.get(t, 0) + 1
    top_tech = sorted(all_tech, key=lambda k: -all_tech[k])[:6]

    months = (last.year - first.year) * 12 + (last.month - first.month)
    summary = (
        f"Last ~{months} months: {total_sessions} AI-assisted sessions across "
        f"{len(groups)} projects. "
        f"Primary stack: {', '.join(top_tech) or '—'}. "
        f"Capabilities: {', '.join(top_caps) or '—'}. "
        f"Most active: {', '.join(g.name for g in top)}."
    )
    OBSERVED_SUMMARY_PATH.write_bytes(
        orjson.dumps(
            {
                "summary": summary,
                "total_sessions": total_sessions,
                "total_projects": len(groups),
                "top_tech": top_tech,
                "top_capabilities": top_caps,
                "first": first.isoformat(),
                "last": last.isoformat(),
            },
            option=orjson.OPT_INDENT_2,
        )
    )


def load_observed_summary() -> dict | None:
    if not OBSERVED_SUMMARY_PATH.exists():
        return None
    return orjson.loads(OBSERVED_SUMMARY_PATH.read_bytes())


def groups_path_for(persona: str | None = None) -> Path:
    """Cache path for project groups, scoped to a reviewer persona when set.

    Persona-less pipelines write to ``_project_groups.json`` (backwards compat).
    Per-persona runs write to ``_project_groups.<persona>.json`` so two enrich
    passes can coexist and render can pick the right variant by filename.
    """
    if not persona:
        return GROUPS_PATH
    return GROUPS_PATH.parent / f"_project_groups.{persona}.json"


def load_groups(persona: str | None = None) -> list[ProjectGroup]:
    """Load groups for the given persona, falling back to the default file.

    The fallback matters for `render --persona X` when the user hasn't run
    `enrich --persona X` yet: they still get a reasonable draft instead of
    an empty one.
    """
    path = groups_path_for(persona)
    if not path.exists():
        path = GROUPS_PATH
        if not path.exists():
            return []
    raw = orjson.loads(path.read_bytes())
    return [ProjectGroup(**g) for g in raw]
