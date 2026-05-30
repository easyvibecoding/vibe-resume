"""Preflight + freshness disclosure (#64).

`pdf_engine_status` discloses whether the pandoc PDF engine (xelatex) is usable
and, when it's installed-but-not-on-PATH, the exact fix — so `render -f pdf`
doesn't silently drop the PDF. `stage_freshness` reports per-stage cache
timestamps + a staleness verdict so an agent can decide whether to re-run the
expensive `enrich` without shelling out to `ls -lt`.
"""
from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

# Common MacTeX / TeX Live locations xelatex lands in but that aren't always on PATH.
_TEX_DIR_GLOBS = [
    "/Library/TeX/texbin",
    "/usr/local/texlive/*/bin/*",
    "/opt/homebrew/bin",
    "/usr/local/bin",
]


def _find_xelatex_offpath() -> str | None:
    for pattern in _TEX_DIR_GLOBS:
        if "*" in pattern:
            for d in sorted(Path("/").glob(pattern.lstrip("/"))):
                if (d / "xelatex").exists():
                    return str(d)
        else:
            if (Path(pattern) / "xelatex").exists():
                return pattern
    return None


def pdf_engine_status() -> tuple[bool, str]:
    """(usable, message). Usable = pandoc + xelatex both reachable on PATH."""
    if not shutil.which("pandoc"):
        return False, "PDF engine: pandoc not found — PDF disabled (e.g. `brew install pandoc`)"
    if shutil.which("xelatex"):
        return True, "PDF engine: pandoc + xelatex on PATH"
    where = _find_xelatex_offpath()
    if where:
        return False, (
            f"PDF engine: xelatex installed at {where} but NOT on PATH — "
            f'run with `PATH="{where}:$PATH"` (or add it to your shell profile); '
            "otherwise `render -f pdf` silently drops the PDF"
        )
    return False, (
        "PDF engine: xelatex not found — install MacTeX/TeX Live for proper PDF "
        "(pandoc falls back to a basic engine, lower quality)"
    )


def _age(ts: datetime, now: datetime) -> str:
    secs = max(0, (now - ts).total_seconds())
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _mtime(p: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def stage_freshness(root: Path, *, now: datetime | None = None) -> list[dict]:
    """Per-stage cache freshness. Returns ordered dicts:
    {stage, file, mtime (datetime|None), age (str|None)} for extract / aggregate /
    enrich / render, newest representative file per stage."""
    now = now or datetime.now(UTC)
    cache = root / "data" / "cache"
    hist = root / "data" / "resume_history"

    def newest(paths: list[Path]) -> Path | None:
        paths = [p for p in paths if p.exists()]
        return max(paths, key=lambda p: p.stat().st_mtime) if paths else None

    # extract = raw per-source caches (exclude derived files)
    derived = {"_project_groups", "_window_stats", "_emphasis", "market_rubric", "_codebase_scan"}
    extract_files = [
        p for p in (cache.glob("*.json") if cache.exists() else [])
        if not any(p.stem.startswith(d) for d in derived)
    ]
    enrich_files = list(cache.glob("_project_groups.*.json")) if cache.exists() else []
    stages = [
        ("extract", newest(extract_files)),
        ("aggregate", cache / "_project_groups.json"),
        ("enrich", newest(enrich_files)),
        ("render", newest(list(hist.glob("resume_v*.md")) if hist.exists() else [])),
    ]
    out: list[dict] = []
    for name, p in stages:
        mt = _mtime(p) if p else None
        out.append({
            "stage": name,
            "file": p.name if p else None,
            "mtime": mt,
            "age": _age(mt, now) if mt else None,
        })
    return out


def freshness_verdict(stages: list[dict]) -> str:
    """One-line verdict: is the enrich cache newer than aggregate (reusable) or stale?"""
    by = {s["stage"]: s for s in stages}
    agg, enr = by.get("aggregate"), by.get("enrich")
    if not (enr and enr["mtime"]):
        return "no enrich cache yet — run `enrich` then `--ingest`"
    if agg and agg["mtime"] and enr["mtime"] < agg["mtime"]:
        return "enrich is OLDER than aggregate — re-run enrich to pick up new activity"
    return "enrich is newer than aggregate — reuse it (skip re-enrich)"
