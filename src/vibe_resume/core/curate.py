"""Human-in-the-loop curation gate: file-based, traceable, re-runnable.

`curate` (emit) reads aggregated groups (with #37/#38 merge provenance) and
writes an editable `_curation.yaml` classifying every group into one of four
tiers. `curate --apply` executes keep / merge_into / drop into a non-destructive
`_project_groups.curated.json` that enrich/render prefer.
"""
from __future__ import annotations

import fnmatch
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from vibe_resume.core.schema import ProjectGroup

DEFAULT_NOISE_GLOBS = ["**/tmp/**", "**/temp/**", "**/scratch/**", "**/sandbox/**"]


class CurationEntry(BaseModel):
    name: str
    canonical_key: str | None = None
    sessions: int
    tier: Literal["auto_merge", "auto_drop", "needs_decision", "keep"]
    action: Literal["keep", "merge_into", "drop"]
    target: str | None = None
    evidence: str | None = None
    merged_from: list[str] = []


class CurationRecord(BaseModel):
    version: int = 1
    generated_at: str
    groups: list[CurationEntry]


def _basename(g: ProjectGroup) -> str:
    return (g.path or g.name).rstrip("/").split("/")[-1].lower()


def classify(groups: list[ProjectGroup], noise_globs: list[str]) -> list[CurationEntry]:
    """Assign each group a tier + suggested action. Precedence:
    auto_drop > needs_decision > auto_merge > keep."""
    by_base: dict[str, list[ProjectGroup]] = defaultdict(list)
    for g in groups:
        by_base[_basename(g)].append(g)

    entries: list[CurationEntry] = []
    for g in groups:
        path = g.path or ""
        tier: str = "keep"
        action: str = "keep"
        target: str | None = None
        evidence: str | None = None

        if path and any(fnmatch.fnmatch(path, pat) for pat in noise_globs):
            tier, action = "auto_drop", "drop"
            evidence = "path matches a configured noise glob"
        else:
            # needs_decision: no identity proof (no remote/toplevel) but a
            # same-basename sibling exists → a human should confirm the merge.
            sib = None
            if g.canonical_key is None:
                siblings = [s for s in by_base[_basename(g)] if s.name != g.name]
                if siblings:
                    sib = max(siblings, key=lambda s: s.total_sessions)
            if sib is not None and sib.total_sessions >= g.total_sessions and sib.name != g.name:
                tier, action, target = "needs_decision", "merge_into", sib.name
                evidence = f"no remote proof; same basename as {sib.name}. CONFIRM?"
            elif len(g.merged_from) > 1:
                tier, action = "auto_merge", "keep"
                evidence = g.merge_evidence

        entries.append(CurationEntry(
            name=g.name, canonical_key=g.canonical_key, sessions=g.total_sessions,
            tier=tier, action=action, target=target, evidence=evidence,
            merged_from=g.merged_from,
        ))
    return entries
