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

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EnrichJobEntry(BaseModel):
    id: str = Field(..., description="Zero-padded index e.g. '001'")
    name: str
    prompt_path: str = Field(..., description="Relative to manifest.json dir")
    output_path: str = Field(..., description="Relative to manifest.json dir")
    status: Literal["pending", "done"]


class EnrichJobManifest(BaseModel):
    version: int = 1
    created_at: datetime
    locale: str
    persona: str | None = None
    tailor_keywords: list[str] | None = None
    company: str | None = None
    level: str | None = None
    groups: list[EnrichJobEntry]
