"""Orchestrate extractors, aggregator, enricher, renderer."""
from __future__ import annotations

import importlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

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

DEFAULT_PARALLELISM = 4


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


def _run_one(kind: str, mod_name: str, cfg: dict[str, Any]):
    """Execute one extractor. Returns (kind, mod_name, acts | None, elapsed, err_token)."""
    t0 = time.time()
    try:
        mod = _load(kind, mod_name)
        acts = mod.extract(cfg)
    except ModuleNotFoundError:
        return (kind, mod_name, None, time.time() - t0, "not_implemented")
    except Exception as e:  # noqa: BLE001 — per-extractor isolation; failure of one must not abort the batch
        return (kind, mod_name, None, time.time() - t0, f"error: {e}")
    return (kind, mod_name, acts, time.time() - t0, None)


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

    if not plan:
        console.print("[yellow]no extractors enabled[/yellow]")
        return

    workers = int(cfg.get("scan", {}).get("parallelism") or DEFAULT_PARALLELISM)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        overall = progress.add_task(
            f"[cyan]Extracting ({workers}× parallel)",
            total=len(plan),
        )
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_run_one, kind, mod_name, cfg): (kind, mod_name)
                for kind, mod_name, _ in plan
            }
            for fut in as_completed(futures):
                kind, mod_name, acts, elapsed, err = fut.result()
                if err == "not_implemented":
                    console.print(f"  [yellow]skip[/yellow] {kind}/{mod_name} (not implemented)")
                elif err:
                    console.print(f"  [red]✗[/red] {kind}/{mod_name}: {err} ({elapsed:.1f}s)")
                elif acts is not None:
                    out = CACHE_DIR / f"{mod_name}.json"
                    save_activities(acts, out)
                    console.print(
                        f"  [green]✓[/green] {kind}/{mod_name} — "
                        f"{len(acts)} activities ({elapsed:.1f}s)"
                    )
                progress.update(overall, advance=1)


def run_aggregator(cfg: dict[str, Any]) -> None:
    from core.aggregator import aggregate_from_cache

    aggregate_from_cache(cfg, CACHE_DIR)


def run_enricher(
    cfg: dict[str, Any],
    limit: int | None = None,
    locale: str | None = None,
    tailor: str | None = None,
    persona: str | None = None,
    company: str | None = None,
    level: str | None = None,
) -> None:
    from core.enricher import enrich_groups

    enrich_groups(
        cfg,
        CACHE_DIR,
        limit=limit,
        locale=locale,
        tailor=tailor,
        persona=persona,
        company=company,
        level=level,
    )


def run_render(
    cfg: dict[str, Any],
    fmt: str = "md",
    tailor: str | None = None,
    locale: str | None = None,
    persona: str | None = None,
) -> None:
    from render.renderer import render_draft

    render_draft(cfg, fmt=fmt, tailor=tailor, locale=locale, persona=persona)
