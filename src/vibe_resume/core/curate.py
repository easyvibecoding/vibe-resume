"""Human-in-the-loop curation gate: file-based, traceable, re-runnable.

`curate` (emit) reads aggregated groups (with #37/#38 merge provenance) and
writes an editable `_curation.yaml` classifying every group into one of four
tiers. `curate --apply` executes keep / merge_into / drop into a non-destructive
`_project_groups.curated.json` that enrich/render prefer.
"""
from __future__ import annotations

import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import orjson
import yaml
from pydantic import BaseModel

from vibe_resume.core.paths import user_root
from vibe_resume.core.schema import ProjectGroup

DEFAULT_NOISE_GLOBS = ["**/tmp/**", "**/temp/**", "**/scratch/**", "**/sandbox/**"]

_ROOT = user_root()
GROUPS_PATH = _ROOT / "data" / "cache" / "_project_groups.json"
CURATION_YAML = _ROOT / "data" / "cache" / "_curation.yaml"
CURATED_PATH = _ROOT / "data" / "cache" / "_project_groups.curated.json"


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


def _load_prior(path: Path) -> CurationRecord | None:
    if not path.exists():
        return None
    try:
        return CurationRecord(**(yaml.safe_load(path.read_text()) or {}))
    except Exception:
        return None


def emit_curation(
    groups: list[ProjectGroup],
    noise_globs: list[str],
    out_path: Path,
    *,
    now: str,
) -> CurationRecord:
    """Classify groups, carry forward any prior human action/target keyed by
    canonical identity (canonical_key, else name), write `_curation.yaml`."""
    entries = classify(groups, noise_globs)
    prior = _load_prior(out_path)
    if prior:
        prior_by_id = {(p.canonical_key or p.name): p for p in prior.groups}
        for e in entries:
            p = prior_by_id.get(e.canonical_key or e.name)
            if p is not None:
                # informational fields refresh; human's action/target persists
                e.action = p.action
                e.target = p.target
    record = CurationRecord(version=1, generated_at=now, groups=entries)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(record.model_dump(), sort_keys=False, allow_unicode=True))
    return record


def headless_record(groups: list[ProjectGroup], noise_globs: list[str]) -> CurationRecord:
    """A record honoring ONLY the high-confidence auto tiers: keep auto_drop's
    `drop`, but downgrade needs_decision to `keep` (no human confirmation)."""
    entries = classify(groups, noise_globs)
    for e in entries:
        if e.tier == "needs_decision":
            e.action, e.target = "keep", None
    return CurationRecord(version=1, generated_at="headless", groups=entries)


def _union_into(target: ProjectGroup, sources: list[ProjectGroup]) -> None:
    acts = list(target.activities)
    for s in sources:
        acts.extend(s.activities)
    members = [target, *sources]
    target.activities = acts
    target.total_sessions = sum(g.total_sessions for g in members)
    target.sources = sorted({s for g in members for s in g.sources}, key=lambda s: s.value)
    target.first_activity = min(g.first_activity for g in members)
    target.last_activity = max(g.last_activity for g in members)
    target.tech_stack = sorted({t for g in members for t in g.tech_stack})
    cat: dict[str, int] = dict(target.category_counts)
    for s in sources:
        for k, v in s.category_counts.items():
            cat[k] = cat.get(k, 0) + v
    target.category_counts = cat
    target.capability_breadth = sum(1 for v in cat.values() if v > 0)
    paths: set[str] = set(target.merged_from)
    for s in sources:
        paths.update(s.merged_from or ([s.path] if s.path else []))
    target.merged_from = sorted(paths)
    target.merge_evidence = "; ".join(
        x for x in [target.merge_evidence, "curate merge"] if x
    )


def apply_curation(groups: list[ProjectGroup], record: CurationRecord) -> list[ProjectGroup]:
    """Execute keep / merge_into / drop into a new (non-destructive) group list."""
    by_name = {g.name: g for g in groups}
    entry_by_name = {e.name: e for e in record.groups}
    dropped = {e.name for e in record.groups if e.action == "drop"}

    merges: dict[str, list[ProjectGroup]] = defaultdict(list)
    survivors: list[ProjectGroup] = []
    for g in groups:
        if g.name in dropped:
            continue
        e = entry_by_name.get(g.name)
        if (e and e.action == "merge_into" and e.target
                and e.target in by_name and e.target not in dropped):
            merges[e.target].append(g)
        else:
            survivors.append(g)
    for target in survivors:
        if target.name in merges:
            _union_into(target, merges[target.name])
    return survivors


def _load_raw_groups() -> list[ProjectGroup]:
    if not GROUPS_PATH.exists():
        return []
    return [ProjectGroup(**g) for g in orjson.loads(GROUPS_PATH.read_bytes())]


def run_curate(cfg: dict[str, Any], *, apply: bool, now: str) -> str:
    """CLI entry. Without --apply: emit _curation.yaml + return a tier summary.
    With --apply: read _curation.yaml (or headless auto-only) → write curated."""
    curate_cfg = cfg.get("curate", {})
    noise_globs = curate_cfg.get("noise_globs") or DEFAULT_NOISE_GLOBS
    groups = _load_raw_groups()
    if not groups:
        return "no groups — run aggregate first"

    if not apply:
        rec = emit_curation(groups, noise_globs, CURATION_YAML, now=now)
        tiers: dict[str, int] = defaultdict(int)
        for e in rec.groups:
            tiers[e.tier] += 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(tiers.items()))
        return f"wrote {CURATION_YAML} — {summary}"

    prior = _load_prior(CURATION_YAML)
    record = prior if prior is not None else headless_record(groups, noise_globs)
    curated = apply_curation(groups, record)
    CURATED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURATED_PATH.write_bytes(
        orjson.dumps([g.model_dump(mode="json") for g in curated],
                     option=orjson.OPT_INDENT_2))
    return f"wrote {CURATED_PATH} — {len(curated)} groups"
