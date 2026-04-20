"""Orchestrate extractors, aggregator, enricher, renderer."""
from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any

from rich.console import Console

from extractors.base import save_activities

console = Console()
ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "data" / "cache"

LOCAL_EXTRACTORS = [
    "claude_code",
    "claude_code_archive",
    "cursor",
    "copilot_vscode",
    "cline",
    "continue_dev",
    "aider",
    "windsurf",
    "zed_ai",
    "claude_desktop",
    "git_repos",
]

CLOUD_EXTRACTORS = [
    ("chatgpt", "cloud_chatgpt"),
    ("claude_ai", "cloud_claude_ai"),
    ("gemini_takeout", "cloud_gemini"),
    ("grok", "cloud_grok"),
    ("perplexity", "cloud_perplexity"),
    ("mistral", "cloud_mistral"),
    ("poe", "cloud_poe"),
]

AIGC_EXTRACTORS = [
    "image_local",
    "suno",
    "elevenlabs",
    "midjourney",
    "runway",
    "heygen",
]


def _load(kind: str, name: str):
    if kind == "local":
        return importlib.import_module(f"extractors.local.{name}")
    if kind == "cloud":
        return importlib.import_module(f"extractors.cloud_export.{name}")
    if kind == "aigc":
        return importlib.import_module(f"extractors.api.{name}")
    raise ValueError(kind)


def _enabled(cfg: dict[str, Any], key: str) -> bool:
    ex = cfg.get("extractors", {}).get(key)
    if not ex:
        return False
    return bool(ex.get("enabled", True))


def run_extractors(cfg: dict[str, Any], only: list[str] | None = None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    plan: list[tuple[str, str, str]] = []
    for n in LOCAL_EXTRACTORS:
        if _enabled(cfg, n) and (not only or n in only):
            plan.append(("local", n, n))
    for mod_name, cfg_key in CLOUD_EXTRACTORS:
        if _enabled(cfg, cfg_key) and (not only or mod_name in only):
            plan.append(("cloud", mod_name, cfg_key))
    for n in AIGC_EXTRACTORS:
        if _enabled(cfg, n) and (not only or n in only):
            plan.append(("aigc", n, n))

    for kind, mod_name, _cfg_key in plan:
        console.print(f"[cyan]▶[/cyan] {kind}/{mod_name}")
        t0 = time.time()
        try:
            mod = _load(kind, mod_name)
            acts = mod.extract(cfg)
        except ModuleNotFoundError:
            console.print(f"  [yellow]skip[/yellow] (module not yet implemented)")
            continue
        except Exception as e:
            console.print(f"  [red]error[/red] {e}")
            continue
        out = CACHE_DIR / f"{mod_name}.json"
        save_activities(acts, out)
        console.print(
            f"  [green]✓[/green] {len(acts)} activities → {out.name} ({time.time()-t0:.1f}s)"
        )


def run_aggregator(cfg: dict[str, Any]) -> None:
    from core.aggregator import aggregate_from_cache

    aggregate_from_cache(cfg, CACHE_DIR)


def run_enricher(
    cfg: dict[str, Any],
    limit: int | None = None,
    locale: str | None = None,
    tailor: str | None = None,
) -> None:
    from core.enricher import enrich_groups

    enrich_groups(cfg, CACHE_DIR, limit=limit, locale=locale, tailor=tailor)


def run_render(
    cfg: dict[str, Any],
    fmt: str = "md",
    tailor: str | None = None,
    locale: str | None = None,
) -> None:
    from render.renderer import render_draft

    render_draft(cfg, fmt=fmt, tailor=tailor, locale=locale)
