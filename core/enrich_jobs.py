"""Emit/ingest session-driven enrich job manifests.

Replaces the headless `claude -p` subprocess path with a two-step flow:
1. emit_jobs() writes a manifest + per-group prompt files under
   data/enrich_jobs/<persona-or-default>/<locale>/
2. The user's Claude Code session processes each *.prompt.md and writes
   *.yaml next to it.
3. ingest_jobs() reads the *.yaml back and merges into the per-locale
   enriched cache _project_groups.<persona>.<locale>.json.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import orjson
from pydantic import AwareDatetime, BaseModel, Field

from core.schema import ProjectGroup


class EnrichJobEntry(BaseModel):
    id: str = Field(..., description="Zero-padded index e.g. '001'")
    name: str
    prompt_path: str = Field(..., description="Relative to manifest.json dir")
    output_path: str = Field(..., description="Relative to manifest.json dir")
    status: Literal["pending", "done"]


class EnrichJobManifest(BaseModel):
    version: int = 1
    created_at: AwareDatetime
    locale: str
    persona: str | None = None
    tailor_keywords: list[str] | None = None
    company: str | None = None
    level: str | None = None
    groups: list[EnrichJobEntry]


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(name: str) -> str:
    """Make a filesystem-safe slug from a group name."""
    s = _SAFE_NAME.sub("-", name)
    return s[:60].strip("-") or "group"


def emit_jobs(
    groups: list[ProjectGroup],
    out_root: Path,
    *,
    persona: str | None,
    locale: str,
    tailor_keywords: list[str] | None,
    company: str | None,
    level: str | None,
    limit: int | None = None,
) -> Path:
    """Write manifest.json + N *.prompt.md files for the session to process.

    Re-emit semantics: manifest + *.prompt.md are overwritten; *.yaml left
    untouched so a partially-completed session is not lost.
    """
    from datetime import UTC, datetime

    from core.company_profiles import get_company
    from core.enricher import _build_prompt
    from core.levels import get_level
    from core.personas import get_persona
    from render.i18n import get_locale

    locale_meta = get_locale(locale)
    persona_obj = get_persona(persona)
    level_obj = get_level(level)
    company_obj = get_company(company)

    jobs_dir = out_root / (persona or "default") / locale
    jobs_dir.mkdir(parents=True, exist_ok=True)

    selected = groups if limit is None else groups[:limit]

    existing_statuses: dict[str, str] = {}
    manifest_path = jobs_dir / "manifest.json"
    if manifest_path.exists():
        try:
            old = EnrichJobManifest.model_validate_json(manifest_path.read_text())
            for e in old.groups:
                if (jobs_dir / e.output_path).exists():
                    existing_statuses[e.name] = e.status
        except Exception:
            existing_statuses = {}

    entries: list[EnrichJobEntry] = []
    for i, g in enumerate(selected, 1):
        idx = f"{i:03d}"
        slug = _slug(g.name)
        prompt_name = f"{idx}_{slug}.prompt.md"
        output_name = f"{idx}_{slug}.yaml"

        prompt_body = _build_prompt(
            g, locale_meta,
            tailor_keywords=tailor_keywords,
            persona=persona_obj,
            level=level_obj,
            company=company_obj,
        )
        (jobs_dir / prompt_name).write_text(prompt_body, encoding="utf-8")

        entries.append(EnrichJobEntry(
            id=idx, name=g.name,
            prompt_path=prompt_name, output_path=output_name,
            status=existing_statuses.get(g.name, "pending"),
        ))

    manifest = EnrichJobManifest(
        created_at=datetime.now(UTC),
        locale=locale,
        persona=persona,
        tailor_keywords=tailor_keywords,
        company=company,
        level=level,
        groups=entries,
    )
    (jobs_dir / "manifest.json").write_bytes(
        orjson.dumps(manifest.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
    )
    return jobs_dir
