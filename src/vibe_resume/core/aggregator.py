"""Normalize cached activities and group by project."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import orjson
import yaml
from rich.console import Console

from vibe_resume.core.classifier import capability_breadth, tally_categories
from vibe_resume.core.paths import user_root
from vibe_resume.core.privacy import PrivacyFilter
from vibe_resume.core.schema import Activity, ProjectGroup, Source
from vibe_resume.core.tech_canonical import canonical_list
from vibe_resume.extractors.base import load_activities

console = Console()

ROOT = user_root()
GROUPS_PATH = ROOT / "data" / "cache" / "_project_groups.json"
OBSERVED_SUMMARY_PATH = ROOT / "data" / "cache" / "_observed_summary.json"
WINDOW_STATS_PATH = ROOT / "data" / "cache" / "_window_stats.json"

# --- tunable heuristics -----------------------------------------------------
# Every threshold here was chosen empirically on the author's own machine; the
# names are more important than the values. Tuning one means understanding
# what it filters, not just bumping a number.

# Display-truncation widths (for headline and raw-key fallback).
NAME_MAX_LEN = 30              # raw leaf name longer than this gets trimmed
NAME_TRUNCATED_LEN = 25        # width we trim to (leaves room for ellipsis)
SUMMARY_PREVIEW_LEN = 25       # single-summary activity fallback width
RAW_PREFIX_FALLBACK_LEN = 8    # "no summary" fallback: first N chars of raw

# Session-count thresholds for `_is_meaningful` — a group below these is
# treated as noise and dropped before rendering.
MIN_SESSIONS_DEFAULT = 2       # overall minimum; bumped via config.render.min_sessions
MIN_SESSIONS_HASH_ID = 2       # hash-named project needs at least this many sessions to survive
MIN_SESSIONS_NO_TECH = 3       # no-tech + no-breadth project needs at least this many

# Category share threshold for the headline summary. Below this, a category
# won't be named (so "backend 4% / frontend 3% / …" never appears).
HEADLINE_CATEGORY_PCT = 5

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
_ID_NAME_RE = re.compile(r"^[a-z0-9_]+:[0-9a-fA-F]{6,}$")
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
                return s[:SUMMARY_PREVIEW_LEN].replace("\n", " ").rstrip(" ,.·|")
        return raw[:RAW_PREFIX_FALLBACK_LEN] + "…"
    leaf = raw.split("/")[-1] or raw
    # "Add Required Parameter for Restaurant List Screen" → keep; but chinese long prompts → truncate
    if len(leaf) > NAME_MAX_LEN:
        return leaf[:NAME_TRUNCATED_LEN].rstrip() + "…"
    return leaf


def _humanize_group_name(name: str, path: str | None) -> str:
    """Post-process: replace source-prefixed hex IDs with a human-readable label.

    Handles names like ``gemini:a1b2c3d4e5`` that slip through ``_humanize_name``
    because they are shorter than HASH_ID_RE's 20-char floor.
    """
    if path:
        base = Path(path).name
        if base:
            return base
    if _ID_NAME_RE.match(name or ""):
        prefix = name.split(":", 1)[0]
        return f"{prefix} session {name.split(':', 1)[1][:6]}"
    return name


def _is_meaningful(raw_key: str, g: ProjectGroup, min_sessions: int) -> bool:
    key_lc = raw_key.lower().strip()
    if any(sub in key_lc for sub in NOISE_SUBSTRINGS):
        return False
    leaf = key_lc.split("/")[-1].lstrip(".")
    if leaf in NOISE_LEAFS:
        return False
    # A single high-value external (open-source) merged PR is signal, not noise:
    # exempt it from the session-count floor (other noise rules still apply).
    if any(
        a.source == Source.GITHUB
        and (a.extra or {}).get("contribution") == "external"
        and (a.extra or {}).get("merged")
        for a in g.activities
    ):
        return True
    if HASH_ID_RE.match(leaf) and g.total_sessions < MIN_SESSIONS_HASH_ID:
        return False
    if g.total_sessions < min_sessions and g.capability_breadth <= 1:
        return False
    if not g.tech_stack and g.capability_breadth == 0 and g.total_sessions < MIN_SESSIONS_NO_TECH:
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
    parts = [f"{k} {v*100//total}%" for k, v in top if v * 100 // total >= HEADLINE_CATEGORY_PCT]
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


def _load_prior_enrichment() -> dict[str, dict[str, Any]]:
    """Carry LLM-written achievements/summary forward across aggregate runs.

    Without this, running `aggregate` after `enrich` would blow away the
    LLM output. Only projects that actually have a summary or bullets are
    preserved — projects aggregated-but-never-enriched shouldn't
    resurrect themselves with blank content.
    """
    prior: dict[str, dict[str, Any]] = {}
    if not GROUPS_PATH.exists():
        return prior
    try:
        for g in orjson.loads(GROUPS_PATH.read_bytes()):
            if g.get("achievements") or g.get("summary"):
                prior[g["name"]] = {
                    "summary": g.get("summary"),
                    "achievements": g.get("achievements"),
                    "headline": g.get("headline"),
                    "tech_stack": g.get("tech_stack"),
                    "domain_tags": g.get("domain_tags"),
                }
    except (orjson.JSONDecodeError, KeyError):
        pass
    return prior


def _load_user_metrics() -> dict[str, list[str]]:
    """Read `project_metrics:` from profile.yaml so users can hand-supply
    impact numbers the extractors couldn't infer (revenue moved, users
    reached, etc). Absent / malformed profile: empty dict, no error."""
    profile_path = ROOT / "profile.yaml"
    if not profile_path.exists():
        return {}
    try:
        pdata = yaml.safe_load(profile_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}
    metrics = pdata.get("project_metrics") or {}
    return metrics if isinstance(metrics, dict) else {}


def _metrics_for_project(
    display_name: str, all_metrics: dict[str, list[str]]
) -> list[str]:
    """Fuzzy-match lookup: profile keys don't have to exactly match the
    extractor-inferred project name. Either side being a substring of the
    other counts as a hit. First name-match wins (dict order) — a
    non-list value for that key yields `[]` and we do NOT keep searching,
    matching the pre-refactor behaviour."""
    dn = display_name.lower()
    for k, v in all_metrics.items():
        k_lc = k.lower()
        if k_lc in dn or dn in k_lc:
            if isinstance(v, list):
                return [str(m) for m in v]
            return []
    return []


def _reconcile_github_projects(acts: list[Activity]) -> None:
    """Rewrite GitHub activities' `project` to a local git-repo path when the
    repo basename matches one git_repos already scanned, so commits + PRs +
    review land in one project group. Conservative: only GitHub activities,
    only on exact basename hit against a present local repo."""
    local_by_base: dict[str, str] = {}
    for a in acts:
        if a.source == Source.GIT and a.project:
            base = a.project.rstrip("/").split("/")[-1].lower()
            local_by_base.setdefault(base, a.project)
    if not local_by_base:
        return
    for a in acts:
        if a.source != Source.GITHUB:
            continue
        nwo = (a.extra or {}).get("repo") or a.project or ""
        repo_base = nwo.split("/")[-1].lower()
        if repo_base in local_by_base:
            a.project = local_by_base[repo_base]


def _canonical_key(act: Activity) -> str | None:
    """Identity-proven grouping key for an activity's path. Prefer the git
    origin remote, fall back to the work-tree toplevel; None means 'no proof
    of identity' → keep the existing path-based key."""
    extra = act.extra or {}
    remote = extra.get("git_remote")
    if remote:
        return f"remote:{remote}"
    toplevel = extra.get("git_toplevel")
    if toplevel:
        return f"toplevel:{toplevel}"
    return None


def _reconcile_local_projects(acts: list[Activity]) -> dict[str, dict[str, Any]]:
    """Collapse groups that are the same logical repo worked from different
    paths (clones, renamed dirs, sub-packages). Cluster by canonical key,
    rewrite each cluster's `project` to one representative path so the
    existing path-based grouping merges them, and return per-representative
    provenance (canonical_key / merged_from / evidence) for the audit trail.
    Identity-proven only — never merges by name, so unrelated same-named
    repos stay separate."""
    clusters: dict[str, list[Activity]] = defaultdict(list)
    for a in acts:
        k = _canonical_key(a)
        if k:
            clusters[k].append(a)
    prov: dict[str, dict[str, Any]] = {}
    for key, members in clusters.items():
        rep: str | None = None
        for a in members:
            tl = (a.extra or {}).get("git_toplevel")
            if tl:
                rep = tl
                break
        if rep is None:
            counts: dict[str, int] = defaultdict(int)
            for a in members:
                if a.project:
                    counts[a.project] += 1
            if not counts:
                continue
            rep = max(counts, key=lambda p: counts[p])
        merged_from = sorted({a.project for a in members if a.project})
        kind, _, value = key.partition(":")
        for a in members:
            a.project = rep
        prov[rep] = {
            "canonical_key": key,
            "merged_from": merged_from,
            "evidence": f"same {kind} {value}",
        }
    return prov


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

    _reconcile_github_projects(all_acts)
    prov_by_rep = _reconcile_local_projects(all_acts)

    prior_enrich = _load_prior_enrichment()
    user_metrics = _load_user_metrics()

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
        display_name = _humanize_group_name(_humanize_name(key, path_val, acts), path_val)
        canonical_tech = canonical_list(sorted(tech))

        prior = prior_enrich.get(display_name, {})
        project_metrics = _metrics_for_project(display_name, user_metrics)
        prov = prov_by_rep.get(path_val or "", {})

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
            canonical_key=prov.get("canonical_key"),
            merged_from=prov.get("merged_from", []),
            merge_evidence=prov.get("evidence"),
        )
        groups.append(grp)

    min_sessions = int(cfg.get("render", {}).get("min_sessions") or MIN_SESSIONS_DEFAULT)
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
    from vibe_resume.core.stats import compute_window_stats

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


def groups_path_for(persona: str | None = None, locale: str | None = None) -> Path:
    """Cache path for enriched project groups, scoped to (persona, locale).

    - groups_path_for(None, None)  → GROUPS_PATH (raw aggregator output)
    - groups_path_for(persona_or_none, locale) → _project_groups.<persona-or-default>.<locale>.json

    Per-locale split (added 0.4.0) prevents zh_TW enrich from overwriting
    a prior en_US enrich. Aggregator still writes the locale-free GROUPS_PATH;
    enrich --ingest writes the per-locale variants.
    """
    if locale is None:
        return GROUPS_PATH
    p = persona or "default"
    return GROUPS_PATH.parent / f"_project_groups.{p}.{locale}.json"


def load_groups(
    persona: str | None = None,
    locale: str | None = None,
) -> list[ProjectGroup]:
    """Load enriched groups with fallback chain.

    Order: (persona, locale) → (None, locale) → GROUPS_PATH → [].
    The final fallback (raw aggregator output) lets `render` show something
    coherent even when enrich has not been run for the requested locale yet.
    """
    candidates: list[Path] = []
    if locale is not None:
        candidates.append(groups_path_for(persona, locale))
        if persona is not None:
            candidates.append(groups_path_for(None, locale))
    candidates.append(GROUPS_PATH)

    for path in candidates:
        if path.exists():
            raw = orjson.loads(path.read_bytes())
            return [ProjectGroup(**g) for g in raw]
    return []
