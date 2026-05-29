# Curate Gate Implementation Plan (#38 Gate A / 0.9.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `aggregate` 與 `enrich` 之間加一個 file-based 人工審核 checkpoint（`curate`），把同一 repo 合併的 provenance 公開化、噪音目錄可審核剔除、無 remote 的同名群組交人工確認，全部集中在單一可 git-diff 的 `_curation.yaml`。

**Architecture:** `ProjectGroup` 增 provenance 欄位（`canonical_key` / `merged_from` / `merge_evidence`），`aggregate` 的 `_reconcile_local_projects` 回傳並填入這些欄位（不退化 0.8.0 自動合併）。新模組 `core/curate.py` 提供 tier 分類（auto_drop / auto_merge / needs_decision / keep）、emit（寫 `_curation.yaml`、carry-forward 人工決策）、apply（執行 keep/merge_into/drop → `_project_groups.curated.json`）。`load_groups` 在 curated 快取存在時優先採用。新 CLI `curate [--apply]`。

**Tech Stack:** Python 3.12+, Pydantic v2, pyyaml, orjson, click, pytest, ruff, uv。Spec: `docs/superpowers/specs/2026-05-29-curate-gate-design.md`。

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/schema.py` | `ProjectGroup` 加 provenance 欄位 | Modify |
| `src/vibe_resume/core/aggregator.py` | `_reconcile_local_projects` 回傳 provenance；group loop 填欄位；`load_groups` curated 優先 | Modify |
| `src/vibe_resume/core/curate.py` | models + classify + emit + apply | Create |
| `src/vibe_resume/cli.py` | `curate` 指令；enrich/render `--curated/--no-curated` | Modify |
| `config.example.yaml` | `curate:` 區塊 | Modify |
| `tests/test_schema.py` | provenance 欄位預設 + round-trip | Modify |
| `tests/test_aggregator.py` | `_reconcile_local_projects` 回傳 provenance | Modify |
| `tests/test_curate.py` | classify / emit carry-forward / apply / headless | Create |
| `tests/test_curate_consumption.py` | `load_groups` curated 優先 | Create |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.9.0 bump | Modify |

**Execution order:** Task 1（schema）→ Task 2（aggregate provenance）→ Task 3（models+classify）→ Task 4（emit）→ Task 5（apply）→ Task 6（consumption）→ Task 7（CLI+config）→ Task 8（release）。

---

### Task 1: ProjectGroup provenance 欄位

**Files:**
- Modify: `src/vibe_resume/core/schema.py:113-116`（`metrics` 欄位之後）
- Test: `tests/test_schema.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_schema.py` 追加：

```python
def test_project_group_provenance_defaults_and_roundtrip():
    from vibe_resume.core.schema import ProjectGroup
    g = ProjectGroup(name="x", first_activity="2026-01-01T00:00:00+00:00",
                     last_activity="2026-01-01T00:00:00+00:00", total_sessions=1)
    assert g.canonical_key is None
    assert g.merged_from == []
    assert g.merge_evidence is None
    g2 = ProjectGroup(**g.model_dump())
    g2.canonical_key = "remote:github.com/me/foo"
    g2.merged_from = ["/a", "/b"]
    g2.merge_evidence = "same remote github.com/me/foo"
    back = ProjectGroup(**g2.model_dump(mode="json"))
    assert back.canonical_key == "remote:github.com/me/foo"
    assert back.merged_from == ["/a", "/b"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_schema.py::test_project_group_provenance_defaults_and_roundtrip -v`
Expected: FAIL（`canonical_key` attribute 不存在）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/schema.py` 的 `ProjectGroup` 內，`metrics` 欄位之後加入：

```python
    canonical_key: str | None = Field(
        default=None,
        description="Identity-proven grouping key (remote:… / toplevel:…) from #37 reconcile",
    )
    merged_from: list[str] = Field(
        default_factory=list,
        description="Original project paths collapsed into this group (len>1 = a merge happened)",
    )
    merge_evidence: str | None = Field(
        default=None,
        description="Human-readable merge justification, e.g. 'same remote github.com/me/foo'",
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/schema.py tests/test_schema.py
git commit -m "feat(schema): ProjectGroup provenance fields (canonical_key/merged_from/merge_evidence) (#38)"
```

---

### Task 2: aggregate 記錄 provenance

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py`（`_reconcile_local_projects` 回傳值 + group loop + call site）
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_aggregator.py` 追加（沿用既有 `_act` helper）：

```python
def test_reconcile_returns_provenance_for_merged_cluster():
    acts = [
        _act(Source.GIT, "/dev/foo", remote="github.com/me/foo", toplevel="/dev/foo", sid="a"),
        _act(Source.CODEX, "/side/foo", remote="github.com/me/foo", toplevel="/side/foo", sid="b"),
    ]
    prov = _reconcile_local_projects(acts)
    rep = acts[0].project
    assert rep in prov
    assert prov[rep]["canonical_key"] == "remote:github.com/me/foo"
    assert sorted(prov[rep]["merged_from"]) == ["/dev/foo", "/side/foo"]
    assert "github.com/me/foo" in prov[rep]["evidence"]
```

（既有 `test_reconcile_merges_*` 仍斷言「改寫 project」，不受影響。）

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_aggregator.py::test_reconcile_returns_provenance_for_merged_cluster -v`
Expected: FAIL（`_reconcile_local_projects` 回傳 None，不可下標）。

- [ ] **Step 3: 實作**

把 `src/vibe_resume/core/aggregator.py` 的 `_reconcile_local_projects` 改為記錄並回傳 provenance（保留改寫 `project` 行為）：

```python
def _reconcile_local_projects(acts: list[Activity]) -> dict[str, dict[str, Any]]:
    """Collapse groups that are the same logical repo worked from different
    paths (clones, renamed dirs, sub-packages). Cluster by canonical key,
    rewrite each cluster's `project` to one representative path so the
    existing path-based grouping merges them, and return per-representative
    provenance (canonical_key / merged_from / evidence) for the audit trail.
    Identity-proven only — never merges by name."""
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
```

在 `aggregate_from_cache`，把：

```python
    _reconcile_github_projects(all_acts)
    _reconcile_local_projects(all_acts)
```

改為：

```python
    _reconcile_github_projects(all_acts)
    prov_by_rep = _reconcile_local_projects(all_acts)
```

在 group-building loop 內，把 `grp = ProjectGroup(...)` 之前插入 provenance 取值，並把三個欄位加進建構子。將該段改為：

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_aggregator.py -v`
Expected: PASS（新測試 + 既有 reconcile/external/canonical 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): record merge provenance on ProjectGroup (#38)"
```

---

### Task 3: curate models + tier 分類

**Files:**
- Create: `src/vibe_resume/core/curate.py`
- Test: `tests/test_curate.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_curate.py`：

```python
from vibe_resume.core.curate import (
    DEFAULT_NOISE_GLOBS,
    CurationEntry,
    CurationRecord,
    classify,
)
from vibe_resume.core.schema import ProjectGroup


def _g(name, path=None, sessions=1, canonical_key=None, merged_from=None):
    return ProjectGroup(
        name=name, path=path,
        first_activity="2026-01-01T00:00:00+00:00",
        last_activity="2026-01-01T00:00:00+00:00",
        total_sessions=sessions, canonical_key=canonical_key,
        merged_from=merged_from or [],
    )


def test_classify_auto_drop_on_noise_glob():
    g = _g("scratch", path="/Users/me/tmp/scratch")
    [e] = classify([g], DEFAULT_NOISE_GLOBS)
    assert e.tier == "auto_drop" and e.action == "drop"


def test_classify_auto_merge_when_merged_from_multi():
    g = _g("foo", path="/dev/foo", canonical_key="remote:github.com/me/foo",
           merged_from=["/dev/foo", "/side/foo"])
    [e] = classify([g], DEFAULT_NOISE_GLOBS)
    assert e.tier == "auto_merge" and e.action == "keep"
    assert e.merged_from == ["/dev/foo", "/side/foo"]


def test_classify_needs_decision_same_basename_no_remote():
    a = _g("CRM", path="/work/CRM", sessions=10)          # no canonical_key
    b = _g("CRM-copy", path="/test/CRM", sessions=3)       # same basename, no key
    entries = {e.name: e for e in classify([a, b], DEFAULT_NOISE_GLOBS)}
    # smaller one is asked to merge into the bigger
    assert entries["CRM-copy"].tier == "needs_decision"
    assert entries["CRM-copy"].action == "merge_into"
    assert entries["CRM-copy"].target == "CRM"


def test_classify_keep_default():
    g = _g("solo", path="/dev/solo", canonical_key="remote:github.com/me/solo",
           merged_from=["/dev/solo"])
    [e] = classify([g], DEFAULT_NOISE_GLOBS)
    assert e.tier == "keep" and e.action == "keep"


def test_classify_proven_different_remotes_not_flagged():
    a = _g("test", path="/a/test", canonical_key="remote:github.com/me/test", merged_from=["/a/test"])
    b = _g("test", path="/b/test", canonical_key="remote:github.com/you/test", merged_from=["/b/test"])
    entries = classify([a, b], DEFAULT_NOISE_GLOBS)
    assert all(e.tier == "keep" for e in entries)   # different remotes → not needs_decision
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_curate.py -v`
Expected: FAIL（`curate` 模組不存在）。

- [ ] **Step 3: 實作**

Create `src/vibe_resume/core/curate.py`：

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_curate.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/curate.py tests/test_curate.py
git commit -m "feat(curate): CurationRecord models + tier classifier (#38)"
```

---

### Task 4: curate emit（寫 yaml + carry-forward）

**Files:**
- Modify: `src/vibe_resume/core/curate.py`
- Test: `tests/test_curate.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_curate.py` 追加：

```python
import yaml as _yaml

from vibe_resume.core.curate import emit_curation


def test_emit_writes_yaml_and_carries_forward_human_action(tmp_path):
    groups = [
        _g("CRM", path="/work/CRM", sessions=10),
        _g("CRM-copy", path="/test/CRM", sessions=3),
    ]
    out = tmp_path / "_curation.yaml"
    # first emit: CRM-copy is needs_decision → merge_into CRM
    rec = emit_curation(groups, DEFAULT_NOISE_GLOBS, out, now="2026-01-01T00:00:00Z")
    assert out.exists()
    e = {x.name: x for x in rec.groups}["CRM-copy"]
    assert e.action == "merge_into"

    # human edits: reject the merge (keep) and re-save
    data = _yaml.safe_load(out.read_text())
    for grp in data["groups"]:
        if grp["name"] == "CRM-copy":
            grp["action"] = "keep"
            grp["target"] = None
    out.write_text(_yaml.safe_dump(data))

    # re-emit: prior human action (keep) must be carried forward
    rec2 = emit_curation(groups, DEFAULT_NOISE_GLOBS, out, now="2026-01-02T00:00:00Z")
    e2 = {x.name: x for x in rec2.groups}["CRM-copy"]
    assert e2.action == "keep"     # human override preserved
    assert e2.target is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_curate.py::test_emit_writes_yaml_and_carries_forward_human_action -v`
Expected: FAIL（`emit_curation` 未定義）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/curate.py` 頂部 import 加：

```python
from pathlib import Path

import yaml
```

並加入：

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_curate.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/curate.py tests/test_curate.py
git commit -m "feat(curate): emit _curation.yaml with human-decision carry-forward (#38)"
```

---

### Task 5: curate apply（merge/drop → curated.json）

**Files:**
- Modify: `src/vibe_resume/core/curate.py`
- Test: `tests/test_curate.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_curate.py` 追加：

```python
from vibe_resume.core.curate import apply_curation


def test_apply_drop_merge_keep():
    crm = _g("CRM", path="/work/CRM", sessions=10)
    crm_copy = _g("CRM-copy", path="/test/CRM", sessions=3)
    tmp = _g("scratch", path="/Users/me/tmp/scratch", sessions=1)
    groups = [crm, crm_copy, tmp]
    record = CurationRecord(version=1, generated_at="t", groups=[
        CurationEntry(name="CRM", sessions=10, tier="keep", action="keep"),
        CurationEntry(name="CRM-copy", sessions=3, tier="needs_decision",
                      action="merge_into", target="CRM"),
        CurationEntry(name="scratch", sessions=1, tier="auto_drop", action="drop"),
    ])
    out = apply_curation(groups, record)
    names = {g.name for g in out}
    assert names == {"CRM"}                       # scratch dropped, CRM-copy merged
    merged = out[0]
    assert merged.total_sessions == 13            # 10 + 3 unioned
    assert "/test/CRM" in merged.merged_from


def test_apply_headless_no_record_applies_auto_only():
    crm = _g("CRM", path="/work/CRM", sessions=10)
    tmp = _g("scratch", path="/Users/me/tmp/scratch", sessions=1)
    # headless: derive a record from auto tiers only
    record = headless_record([crm, tmp], DEFAULT_NOISE_GLOBS)
    out = apply_curation([crm, tmp], record)
    assert {g.name for g in out} == {"CRM"}       # noise auto-dropped, no merge_into
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_curate.py -k apply -v`
Expected: FAIL（`apply_curation` / `headless_record` 未定義）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/curate.py` 加入：

```python
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
    target.activities = acts
    target.total_sessions = sum(g.total_sessions for g in [target, *sources])
    target.sources = sorted({s for g in [target, *sources] for s in g.sources},
                            key=lambda s: s.value)
    target.first_activity = min(g.first_activity for g in [target, *sources])
    target.last_activity = max(g.last_activity for g in [target, *sources])
    target.tech_stack = sorted({t for g in [target, *sources] for t in g.tech_stack})
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_curate.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/curate.py tests/test_curate.py
git commit -m "feat(curate): apply keep/merge_into/drop → curated groups + headless default (#38)"
```

---

### Task 6: `load_groups` 優先採 curated 快取

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py`（`load_groups` + 新 `CURATED_PATH`）
- Test: `tests/test_curate_consumption.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_curate_consumption.py`：

```python
import orjson

from vibe_resume.core import aggregator
from vibe_resume.core.schema import ProjectGroup


def _dump(path, names):
    groups = [ProjectGroup(name=n, first_activity="2026-01-01T00:00:00+00:00",
                           last_activity="2026-01-01T00:00:00+00:00", total_sessions=1)
              for n in names]
    path.write_bytes(orjson.dumps([g.model_dump(mode="json") for g in groups]))


def test_load_groups_prefers_curated(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    _dump(aggregator.GROUPS_PATH, ["raw1", "raw2"])
    _dump(aggregator.CURATED_PATH, ["curated1"])
    got = aggregator.load_groups()
    assert [g.name for g in got] == ["curated1"]       # curated wins over raw


def test_load_groups_no_curated_uses_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    _dump(aggregator.GROUPS_PATH, ["raw1"])
    got = aggregator.load_groups()
    assert [g.name for g in got] == ["raw1"]


def test_load_groups_no_curated_flag_ignores_curated(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    _dump(aggregator.GROUPS_PATH, ["raw1"])
    _dump(aggregator.CURATED_PATH, ["curated1"])
    got = aggregator.load_groups(use_curated=False)
    assert [g.name for g in got] == ["raw1"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_curate_consumption.py -v`
Expected: FAIL（`CURATED_PATH` / `use_curated` 不存在）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/aggregator.py` 的 `GROUPS_PATH` 定義之後（line 24 附近）加：

```python
CURATED_PATH = ROOT / "data" / "cache" / "_project_groups.curated.json"
```

把 `load_groups` 簽名與 fallback chain 改為（curated 作為 raw 層之前的優先候選）：

```python
def load_groups(
    persona: str | None = None,
    locale: str | None = None,
    use_curated: bool = True,
) -> list[ProjectGroup]:
    """Load enriched groups with fallback chain.

    Order: (persona, locale) → (None, locale) → curated → GROUPS_PATH → [].
    The curated cache (from `curate --apply`) is preferred over the raw
    aggregator output as the un-enriched base; `use_curated=False` ignores it.
    """
    candidates: list[Path] = []
    if locale is not None:
        candidates.append(groups_path_for(persona, locale))
        if persona is not None:
            candidates.append(groups_path_for(None, locale))
    if use_curated and CURATED_PATH.exists():
        candidates.append(CURATED_PATH)
    candidates.append(GROUPS_PATH)

    for path in candidates:
        if path.exists():
            raw = orjson.loads(path.read_bytes())
            return [ProjectGroup(**g) for g in raw]
    return []
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_curate_consumption.py tests/test_resolve_resume_path.py -v`
Expected: PASS（新測試 + 既有 load_groups 路徑相關測試不受影響）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_curate_consumption.py
git commit -m "feat(aggregator): load_groups prefers curated cache over raw (#38)"
```

---

### Task 7: CLI `curate` 指令 + config

**Files:**
- Modify: `src/vibe_resume/core/curate.py`（加 `run_curate` orchestration）
- Modify: `src/vibe_resume/cli.py`（`curate` 指令）
- Modify: `config.example.yaml`
- Test: `tests/test_cli_e2e.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_cli_e2e.py` 追加（沿用該檔既有的 CliRunner 模式；若無 helper 則用下列自足版）：

```python
def test_curate_emit_then_apply(tmp_path, monkeypatch):
    import orjson
    from click.testing import CliRunner

    from vibe_resume.cli import cli
    from vibe_resume.core import aggregator, curate
    from vibe_resume.core.schema import ProjectGroup

    # point cache paths at tmp
    monkeypatch.setattr(aggregator, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(aggregator, "CURATED_PATH", tmp_path / "_project_groups.curated.json")
    monkeypatch.setattr(curate, "GROUPS_PATH", tmp_path / "_project_groups.json")
    monkeypatch.setattr(curate, "CURATION_YAML", tmp_path / "_curation.yaml")
    monkeypatch.setattr(curate, "CURATED_PATH", tmp_path / "_project_groups.curated.json")

    groups = [
        ProjectGroup(name="app", path="/dev/app", first_activity="2026-01-01T00:00:00+00:00",
                     last_activity="2026-01-01T00:00:00+00:00", total_sessions=5),
        ProjectGroup(name="scratch", path="/Users/me/tmp/scratch",
                     first_activity="2026-01-01T00:00:00+00:00",
                     last_activity="2026-01-01T00:00:00+00:00", total_sessions=1),
    ]
    (tmp_path / "_project_groups.json").write_bytes(
        orjson.dumps([g.model_dump(mode="json") for g in groups]))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["curate"])
    assert r1.exit_code == 0, r1.output
    assert (tmp_path / "_curation.yaml").exists()

    r2 = runner.invoke(cli, ["curate", "--apply"])
    assert r2.exit_code == 0, r2.output
    curated = orjson.loads((tmp_path / "_project_groups.curated.json").read_bytes())
    names = {g["name"] for g in curated}
    assert names == {"app"}      # scratch auto-dropped
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_cli_e2e.py::test_curate_emit_then_apply -v`
Expected: FAIL（無 `curate` 指令 → exit code != 0 / "No such command"）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/curate.py` 頂部加路徑常數（import 區之後）：

```python
import orjson

from vibe_resume.core.paths import user_root

_ROOT = user_root()
GROUPS_PATH = _ROOT / "data" / "cache" / "_project_groups.json"
CURATION_YAML = _ROOT / "data" / "cache" / "_curation.yaml"
CURATED_PATH = _ROOT / "data" / "cache" / "_project_groups.curated.json"
```

並加入 orchestration（讀 raw groups、emit 或 apply）：

```python
def _load_raw_groups() -> list[ProjectGroup]:
    if not GROUPS_PATH.exists():
        return []
    return [ProjectGroup(**g) for g in orjson.loads(GROUPS_PATH.read_bytes())]


def run_curate(cfg: dict, *, apply: bool, now: str) -> str:
    """CLI entry. Without --apply: emit _curation.yaml + return summary.
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
```

在 `src/vibe_resume/cli.py`，`aggregate` 指令（line 73-79）之後加入：

```python
@cli.command()
@click.option("--apply", "apply_", is_flag=True, default=False,
              help="Execute the edited _curation.yaml into _project_groups.curated.json")
@click.pass_context
def curate(ctx: click.Context, apply_: bool) -> None:
    """Review/auto-curate project groups (merge dupes, drop noise) via an
    editable _curation.yaml checkpoint between aggregate and enrich."""
    from datetime import UTC, datetime

    from vibe_resume.core.curate import run_curate

    msg = run_curate(ctx.obj["config"], apply=apply_,
                     now=datetime.now(UTC).isoformat(timespec="seconds"))
    click.echo(msg)
```

在 `config.example.yaml`，於 `enrich:` 區塊之前（或 `stats:` 之後）加：

```yaml
curate:
  enabled: true                  # enrich/render prefer _project_groups.curated.json when present
  noise_globs:
    - "**/tmp/**"
    - "**/temp/**"
    - "**/scratch/**"
    - "**/sandbox/**"
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_cli_e2e.py -k curate -v && uv run pytest tests/ -q`
Expected: PASS（curate e2e + 全套無回歸）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/curate.py src/vibe_resume/cli.py config.example.yaml tests/test_cli_e2e.py
git commit -m "feat(cli): curate command (emit/apply) + curate config block (#38)"
```

---

### Task 8: Release 0.9.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.8.0 字串**

Run: `grep -rn "0\.8\.0" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處。

- [ ] **Step 2: 全部改為 0.9.0 並刷新 lockfile**

逐處 `0.8.0` → `0.9.0`，然後 `uv lock`。
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.9.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（em-dash）：

```markdown
## [0.9.0] — 2026-05-29

### Added

- **`curate` gate** — a file-based human-in-the-loop checkpoint between
  `aggregate` and `enrich` (#38). `vibe-resume curate` writes an editable
  `_curation.yaml` classifying every project group into `auto_merge` /
  `auto_drop` / `needs_decision` / `keep` with evidence; `curate --apply`
  executes keep/merge_into/drop into a non-destructive
  `_project_groups.curated.json` that `enrich`/`render` prefer. Human
  decisions carry forward across re-runs (keyed by canonical identity);
  headless runs apply only the high-confidence auto tiers. New `curate:`
  config block (`enabled`, `noise_globs`).
- Merge **provenance** on `ProjectGroup` (`canonical_key` / `merged_from` /
  `merge_evidence`): the #37 cross-path auto-merge is now traceable in
  `_project_groups.json` instead of silently rewriting paths.
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.8.0 → 0.9.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-curate-gate-design.md`）：
- §1 ProjectGroup provenance 欄位 → Task 1。✓
- §2 aggregate 記 provenance（`_reconcile_local_projects` 回傳 + group loop 填欄）→ Task 2。✓
- §3 curate emit 四 tier → Task 3（classify）+ Task 4（emit/carry-forward）。✓
- §4 curate --apply（drop/merge_into/keep + headless）→ Task 5。✓
- §5 enrich/render 優先 curated → Task 6（`load_groups` use_curated）。✓
- §6 pydantic 模型 → Task 3。✓
- §7 CLI + config → Task 7。✓
- 持久化 carry-forward → Task 4。✓
- 非破壞（raw 不動、curated sidecar）→ Task 5 `apply_curation` 回新 list；Task 7 寫 CURATED_PATH。✓
- 過度合併防護（不同 remote 不 needs_decision）→ Task 3 `test_classify_proven_different_remotes_not_flagged`。✓
- release 0.9.0 → Task 8。✓

**2. Placeholder scan:** 無 TBD/TODO；每個 code step 有完整程式碼。✓

**3. Type consistency:**
- `classify(groups, noise_globs) -> list[CurationEntry]`：Task 3 定義，Task 4/5/7 一致使用。✓
- `emit_curation(groups, noise_globs, out_path, *, now) -> CurationRecord`：Task 4 定義，Task 7 `run_curate` 一致呼叫。✓
- `apply_curation(groups, record) -> list[ProjectGroup]` / `headless_record(groups, noise_globs)`：Task 5 定義，Task 7 一致呼叫。✓
- `_load_prior(path) -> CurationRecord | None`：Task 4 定義，Task 7 重用。✓
- `CurationEntry` 欄位（name/canonical_key/sessions/tier/action/target/evidence/merged_from）：Task 3 定義，Task 4/5 測試一致。✓
- `load_groups(persona, locale, use_curated=True)`：Task 6 簽名，Task 6 測試一致；既有呼叫端（無第三參數）採預設 True，行為相容。✓
- `CURATED_PATH` 在 aggregator（Task 6）與 curate（Task 7）各自定義並在 e2e 測試 monkeypatch 兩處。✓
- `ProjectGroup.canonical_key/merged_from/merge_evidence`：Task 1 定義，Task 2 寫入、Task 3/5 讀取，一致。✓
