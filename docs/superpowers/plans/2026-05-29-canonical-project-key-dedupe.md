# Canonical-key 跨路徑專案去重 Implementation Plan (#37 / 0.8.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把同一個邏輯 git repo 在不同路徑工作所產生的多個 project group 合併成一個，靠 extract 時捕捉的 git remote / toplevel 推導 canonical key。

**Architecture:** 新增共用 helper `extractors/base.py::git_identity(path, cache)`（解析並正規化 git remote + toplevel）；三個路徑型 extractor（git_repos / claude_code / codex）在 extract 時呼叫它，把結果寫入 `Activity.extra["git_remote"]` / `["git_toplevel"]`；aggregator 新增 `_canonical_key` + `_reconcile_local_projects`，接在 `_reconcile_github_projects` 之後，依 canonical key 把同一 repo 的 activities 的 `project` 改寫成單一代表路徑（仿 0.7.0 的 A5 改寫手法），既有 grouping 自然收斂。只用身分證明（remote/toplevel）合併，絕不用 basename。

**Tech Stack:** Python 3.12+, `git` CLI (subprocess), Pydantic v2, pytest, ruff, uv。Spec: `docs/superpowers/specs/2026-05-29-canonical-project-key-dedupe-design.md`。

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/extractors/base.py` | 加 `_normalize_remote` + `git_identity` | Modify |
| `src/vibe_resume/extractors/local/git_repos.py` | 每 repo 呼叫 `git_identity`，寫入 extra | Modify |
| `src/vibe_resume/extractors/local/claude_code.py` | 對 session `cwd` 呼叫 `git_identity` | Modify |
| `src/vibe_resume/extractors/local/codex.py` | 對 session `cwd` 呼叫 `git_identity` | Modify |
| `src/vibe_resume/core/aggregator.py` | `_canonical_key` + `_reconcile_local_projects` + call site | Modify |
| `tests/test_extractors_base.py` | `_normalize_remote` + `git_identity` 單元測試 | Modify |
| `tests/test_extractors.py` | 三 extractor 捕捉測試 + 修現有 numstat 測試 | Modify |
| `tests/test_aggregator.py` | canonical key + local reconcile 測試 | Modify |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.8.0 release bump | Modify |

**Execution order:** Task 1（helper）必須先做，Task 2–4（extractor 捕捉）依賴它，Task 5（aggregator reconcile）依賴 extra 鍵存在，Task 6 release 最後。

---

### Task 1: `_normalize_remote` + `git_identity` helper

**Files:**
- Modify: `src/vibe_resume/extractors/base.py`
- Test: `tests/test_extractors_base.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_extractors_base.py` 頂部 import 區加入 `import subprocess`，並把 base import 行改為：

```python
from vibe_resume.extractors.base import (
    _normalize_remote,
    git_identity,
    iter_jsonl,
    load_activities,
    save_activities,
)
```

在檔案末端追加：

```python
# ─────────────────────── git_identity ─────────────────────────────────────

import pytest


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/Acme/Project-A.git", "github.com/acme/project-a"),
    ("https://github.com/acme/project-a", "github.com/acme/project-a"),
    ("git@github.com:Acme/Project-A.git", "github.com/acme/project-a"),
    ("ssh://git@github.com/acme/project-a.git", "github.com/acme/project-a"),
    ("https://github.com/acme/project-a/", "github.com/acme/project-a"),
])
def test_normalize_remote(url, expected):
    assert _normalize_remote(url) == expected


def _git_dispatch(monkeypatch, *, toplevel="/repo/foo", toplevel_rc=0, remote="git@github.com:acme/foo.git", remote_rc=0):
    import vibe_resume.extractors.base as base
    calls = {"n": 0}

    def run(cmd, **kw):
        calls["n"] += 1
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(
                cmd, toplevel_rc, stdout=(toplevel + "\n") if toplevel_rc == 0 else "", stderr="")
        if "remote" in cmd:
            return subprocess.CompletedProcess(
                cmd, remote_rc, stdout=(remote + "\n") if remote_rc == 0 else "", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(base.subprocess, "run", run)
    return calls


def test_git_identity_remote_and_toplevel(tmp_path, monkeypatch):
    _git_dispatch(monkeypatch, toplevel=str(tmp_path), remote="git@github.com:acme/foo.git")
    remote, toplevel = git_identity(tmp_path)
    assert remote == "github.com/acme/foo"
    assert toplevel == str(tmp_path)


def test_git_identity_worktree_without_remote(tmp_path, monkeypatch):
    _git_dispatch(monkeypatch, toplevel=str(tmp_path), remote_rc=1)
    remote, toplevel = git_identity(tmp_path)
    assert remote is None
    assert toplevel == str(tmp_path)


def test_git_identity_non_worktree(tmp_path, monkeypatch):
    _git_dispatch(monkeypatch, toplevel_rc=128)
    assert git_identity(tmp_path) == (None, None)


def test_git_identity_nonexistent_path_skips_subprocess(monkeypatch):
    calls = _git_dispatch(monkeypatch)
    assert git_identity("/no/such/path/xyz") == (None, None)
    assert calls["n"] == 0   # guard short-circuits before any git call


def test_git_identity_memoizes_per_path(tmp_path, monkeypatch):
    calls = _git_dispatch(monkeypatch, toplevel=str(tmp_path))
    cache = {}
    git_identity(tmp_path, cache)
    git_identity(tmp_path, cache)
    assert calls["n"] == 2   # one rev-parse + one remote, NOT four
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_extractors_base.py -k "normalize_remote or git_identity" -v`
Expected: FAIL（`_normalize_remote` / `git_identity` 未定義 → ImportError）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/extractors/base.py` 的 import 區加入：

```python
import subprocess
```

在 `sample_spread` 之後（`save_activities` 之前）加入：

```python
def _normalize_remote(url: str) -> str:
    """Collapse the many spellings of one git remote into a single key:
    strip scheme / userinfo, turn the scp-style `host:owner/repo` colon into
    a slash, drop a trailing `.git`, lowercase. So
    `git@github.com:Acme/Repo.git` and `https://github.com/acme/repo` both
    become `github.com/acme/repo`."""
    u = url.strip()
    for scheme in ("https://", "http://", "ssh://", "git://"):
        if u.startswith(scheme):
            u = u[len(scheme):]
            break
    else:
        if u.startswith("git@"):
            u = u[len("git@"):]
    head = u.split("/", 1)[0]
    # ssh:// form may leave `user@host`; scp form leaves `host:owner`
    if "@" in head:
        u = u.split("@", 1)[1]
        head = u.split("/", 1)[0]
    if ":" in head:
        u = u.replace(":", "/", 1)
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/").lower()


def _run_git(args: list[str]) -> str | None:
    """Run a git subcommand; return stripped stdout on rc 0, else None.
    Never raises (missing git / timeout / non-zero → None)."""
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    s = out.stdout.strip()
    return s or None


def git_identity(
    path: str | Path,
    cache: dict[str, tuple[str | None, str | None]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve (normalized origin remote, work-tree toplevel) for `path`.

    - Not a git work-tree (or path gone / git missing) → (None, None).
    - Work-tree with no `origin` remote → (None, toplevel).
    Memoized per path when a `cache` dict is supplied (sessions often share
    a cwd)."""
    key = str(path)
    if cache is not None and key in cache:
        return cache[key]
    if not Path(path).exists():
        result: tuple[str | None, str | None] = (None, None)
    else:
        toplevel = _run_git(["-C", key, "rev-parse", "--show-toplevel"])
        if toplevel is None:
            result = (None, None)
        else:
            raw = _run_git(["-C", key, "remote", "get-url", "origin"])
            remote = _normalize_remote(raw) if raw else None
            result = (remote, toplevel)
    if cache is not None:
        cache[key] = result
    return result
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_extractors_base.py -v`
Expected: PASS（全部，含既有 iter_jsonl / save / load）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/base.py tests/test_extractors_base.py
git commit -m "feat(extractors): git_identity helper — normalized remote + toplevel (#37)"
```

---

### Task 2: git_repos 捕捉 git_remote / git_toplevel

**Files:**
- Modify: `src/vibe_resume/extractors/local/git_repos.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: 寫失敗測試 + 修既有 numstat 測試**

在 `tests/test_extractors.py` 的 `test_git_repos_parses_numstat` 內，於 `monkeypatch.setattr(git_repos.subprocess, "run", fake_run)` 之後加入一行（讓既有測試對 git_identity 保持 hermetic、不 shell 真 git）：

```python
    monkeypatch.setattr(git_repos, "git_identity", lambda *a, **k: (None, None))
```

在該測試函式後面追加新測試：

```python
def test_git_repos_captures_remote_and_toplevel(monkeypatch, tmp_path):
    from vibe_resume.extractors.local import git_repos

    repo = tmp_path / "work" / "demo"
    (repo / ".git").mkdir(parents=True)

    def fake_run(cmd, **_kw):
        if "log" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=_FAKE_LOG, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="user@example.com\n", stderr="")

    monkeypatch.setattr(git_repos.subprocess, "run", fake_run)
    monkeypatch.setattr(
        git_repos, "git_identity",
        lambda path, cache=None: ("github.com/acme/demo", str(repo)),
    )
    cfg = {
        "scan": {"mode": "whitelist", "roots": [str(tmp_path / "work")], "exclude_globs": []},
        "extractors": {"git_repos": {"author_emails": ["user@example.com"]}},
    }
    acts = git_repos.extract(cfg)
    assert acts[0].extra["git_remote"] == "github.com/acme/demo"
    assert acts[0].extra["git_toplevel"] == str(repo)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_extractors.py::test_git_repos_captures_remote_and_toplevel -v`
Expected: FAIL（`extra` 沒有 `git_remote` 鍵 → KeyError）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/extractors/local/git_repos.py` 的 import 區（`from vibe_resume.core.schema import ...` 之後）加入：

```python
from vibe_resume.extractors.base import git_identity
```

在 `extract` 的 repo 迴圈內，於 `if not commits: continue` 之後、`buckets` 建立之前，加入每 repo 一次的身分捕捉（用共用 cache）。把迴圈開頭改為：

```python
    activities: list[Activity] = []
    git_cache: dict = {}
    for repo in repos:
        commits = _git_log(repo, emails)
        if not commits:
            continue
        remote, toplevel = git_identity(repo, git_cache)
```

在該 repo 的月份迴圈裡，把 `extra={...}` 區塊改成先建 dict 再條件補鍵：

```python
            extra = {
                "commits": len(items),
                "insertions": ins,
                "deletions": dels,
                "subjects": subjects,
                "commit_bodies": [b[:_BODY_EXCERPT] for b in bodies],
            }
            if remote:
                extra["git_remote"] = remote
            if toplevel:
                extra["git_toplevel"] = toplevel
            activities.append(
                Activity(
                    source=Source.GIT,
                    session_id=f"{repo.name}:{ym}",
                    timestamp_start=first.astimezone(UTC),
                    timestamp_end=last.astimezone(UTC),
                    project=str(repo),
                    activity_type=ActivityType.COMMIT,
                    user_prompts_count=len(items),
                    tool_calls_count=0,
                    summary=summary[:_SUMMARY_MAX],
                    files_touched=files,
                    raw_ref=f"{repo}@{ym}",
                    extra=extra,
                )
            )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_extractors.py -k git -v`
Expected: PASS（新測試 + 既有 numstat / body-files / no-emails / timeout 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/git_repos.py tests/test_extractors.py
git commit -m "feat(git): capture normalized remote + toplevel per repo (#37)"
```

---

### Task 3: claude_code 對 cwd 捕捉

**Files:**
- Modify: `src/vibe_resume/extractors/local/claude_code.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_extractors.py` 追加：

```python
def test_claude_code_captures_git_identity(tmp_path, monkeypatch):
    import vibe_resume.extractors.local.claude_code as cc

    rows = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z",
             "cwd": "/Users/me/dev/foo",
             "message": {"content": "do a thing"}}]
    _write_session(tmp_path, rows)
    monkeypatch.setattr(
        cc, "git_identity",
        lambda path, cache=None: ("github.com/me/foo", "/Users/me/dev/foo"),
    )
    acts = cc.extract({"extractors": {"claude_code": {"path": str(tmp_path)}}})
    assert acts[0].extra["git_remote"] == "github.com/me/foo"
    assert acts[0].extra["git_toplevel"] == "/Users/me/dev/foo"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_extractors.py::test_claude_code_captures_git_identity -v`
Expected: FAIL（無 `git_remote` 鍵）。

- [ ] **Step 3: 實作**

在 `claude_code.py` import 區把 base import 改為：

```python
from vibe_resume.extractors.base import git_identity, iter_jsonl, sample_spread
```

`extract` 內建立共用 cache 並傳入 `_process_session`。把 extract 迴圈改為：

```python
    activities: list[Activity] = []
    git_cache: dict = {}
    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            if "/subagents/" in str(jsonl_file):
                continue
            act = _process_session(jsonl_file, project_dir.name,
                                   sample_n, per_chars, capture_args, git_cache)
            if act:
                activities.append(act)
    return activities
```

`_process_session` 簽名加 `git_cache`：

```python
def _process_session(path: Path, project_dirname: str,
                     sample_n: int, per_chars: int, capture_args: bool,
                     git_cache: dict) -> Activity | None:
```

在 `extra` 建好（含 `tool_args` 後）、`return Activity(...)` 之前加入：

```python
    if cwd:
        remote, toplevel = git_identity(cwd, git_cache)
        if remote:
            extra["git_remote"] = remote
        if toplevel:
            extra["git_toplevel"] = toplevel
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_extractors.py -k claude_code -v`
Expected: PASS（新測試 + 既有 happy-path / samples_more / missing-path 全綠；fake cwd 不存在 → git_identity guard 直接 (None,None)，毋須 patch）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/claude_code.py tests/test_extractors.py
git commit -m "feat(claude_code): capture git remote + toplevel of session cwd (#37)"
```

---

### Task 4: codex 對 cwd 捕捉

**Files:**
- Modify: `src/vibe_resume/extractors/local/codex.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_extractors.py` 追加：

```python
def test_codex_captures_git_identity(tmp_path, monkeypatch):
    import vibe_resume.extractors.local.codex as cx

    rows = [{"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z",
             "payload": {"cwd": "/Users/me/dev/bar", "id": "s1"}},
            {"type": "response_item", "timestamp": "2026-01-01T00:01:00Z",
             "payload": {"type": "message", "role": "user", "content": "hi"}}]
    f = tmp_path / "rollout-2026-01-01-uuid.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(
        cx, "git_identity",
        lambda path, cache=None: ("github.com/me/bar", "/Users/me/dev/bar"),
    )
    acts = cx.extract({"extractors": {"codex": {"path": str(tmp_path)}}})
    assert acts[0].extra["git_remote"] == "github.com/me/bar"
    assert acts[0].extra["git_toplevel"] == "/Users/me/dev/bar"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_extractors.py::test_codex_captures_git_identity -v`
Expected: FAIL（無 `git_remote` 鍵）。

- [ ] **Step 3: 實作**

在 `codex.py` import 區把 base import 改為：

```python
from vibe_resume.extractors.base import git_identity, iter_jsonl, sample_spread
```

`extract` 內建立共用 cache 並傳入：

```python
    activities: list[Activity] = []
    seen_session_ids: set[str] = set()
    git_cache: dict = {}
    for base in bases:
        for rollout_file in base.rglob("rollout-*.jsonl"):
            act = _process_session(rollout_file, sample_n, per_chars, capture_args, git_cache)
            if not act:
                continue
            if act.session_id in seen_session_ids:
                continue
            seen_session_ids.add(act.session_id)
            activities.append(act)
    return activities
```

`_process_session` 簽名加 `git_cache`：

```python
def _process_session(path: Path, sample_n: int, per_chars: int,
                     capture_args: bool, git_cache: dict) -> Activity | None:
```

在 `extra` 建好（`cli_version` / `git_branch` / `tool_args` 後）、`return Activity(...)` 之前加入：

```python
    if cwd:
        remote, toplevel = git_identity(cwd, git_cache)
        if remote:
            extra["git_remote"] = remote
        if toplevel:
            extra["git_toplevel"] = toplevel
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_extractors.py -k codex -v`
Expected: PASS（新測試 + 既有 happy-path / samples_more 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/codex.py tests/test_extractors.py
git commit -m "feat(codex): capture git remote + toplevel of session cwd (#37)"
```

---

### Task 5: aggregator canonical key + local reconcile

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py`
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_aggregator.py` 把 import 行改為：

```python
from vibe_resume.core.aggregator import (
    _canonical_key,
    _is_meaningful,
    _reconcile_github_projects,
    _reconcile_local_projects,
)
```

追加測試：

```python
def _act(source, project, remote=None, toplevel=None, sid="s"):
    extra = {}
    if remote:
        extra["git_remote"] = remote
    if toplevel:
        extra["git_toplevel"] = toplevel
    return Activity(source=source, session_id=sid,
                    timestamp_start="2026-01-01T00:00:00+00:00",
                    project=project, extra=extra)


def test_canonical_key_prefers_remote_then_toplevel():
    assert _canonical_key(_act(Source.GIT, "/a", remote="github.com/me/foo")) == "remote:github.com/me/foo"
    assert _canonical_key(_act(Source.GIT, "/a", toplevel="/repo/foo")) == "toplevel:/repo/foo"
    assert _canonical_key(_act(Source.GIT, "/a")) is None


def test_reconcile_merges_same_remote_different_paths():
    acts = [
        _act(Source.GIT, "/Users/me/dev/foo", remote="github.com/me/foo", toplevel="/Users/me/dev/foo", sid="a"),
        _act(Source.CODEX, "/Users/me/side/foo", remote="github.com/me/foo", toplevel="/Users/me/side/foo", sid="b"),
    ]
    _reconcile_local_projects(acts)
    assert acts[0].project == acts[1].project   # collapsed to one representative


def test_reconcile_subpackage_collapses_to_toplevel():
    acts = [
        _act(Source.GIT, "/repo/foo", remote="github.com/me/foo", toplevel="/repo/foo", sid="a"),
        _act(Source.CODEX, "/repo/foo/packages/x", remote="github.com/me/foo", toplevel="/repo/foo", sid="b"),
    ]
    _reconcile_local_projects(acts)
    assert acts[0].project == "/repo/foo"
    assert acts[1].project == "/repo/foo"


def test_reconcile_same_basename_different_remote_stays_split():
    acts = [
        _act(Source.GIT, "/work/test", remote="github.com/me/test", toplevel="/work/test", sid="a"),
        _act(Source.GIT, "/play/test", remote="github.com/you/test", toplevel="/play/test", sid="b"),
    ]
    _reconcile_local_projects(acts)
    assert acts[0].project == "/work/test"
    assert acts[1].project == "/play/test"   # different remote → NOT merged


def test_reconcile_no_remote_no_toplevel_unchanged():
    acts = [_act(Source.CLAUDE_CODE, "/some/dir", sid="a")]
    _reconcile_local_projects(acts)
    assert acts[0].project == "/some/dir"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_aggregator.py -k "canonical or reconcile_merges or subpackage or same_basename or no_remote" -v`
Expected: FAIL（`_canonical_key` / `_reconcile_local_projects` 未定義 → ImportError）。

- [ ] **Step 3: 實作**

在 `src/vibe_resume/core/aggregator.py`，於既有 `_reconcile_github_projects` 函式之後加入：

```python
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


def _reconcile_local_projects(acts: list[Activity]) -> None:
    """Collapse groups that are the same logical repo worked from different
    paths (clones, renamed dirs, sub-packages). Cluster by canonical key,
    rewrite each cluster's `project` to one representative path so the
    existing path-based grouping merges them. Identity-proven only — never
    merges by name, so unrelated same-named repos stay separate."""
    clusters: dict[str, list[Activity]] = defaultdict(list)
    for a in acts:
        k = _canonical_key(a)
        if k:
            clusters[k].append(a)
    for members in clusters.values():
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
        for a in members:
            a.project = rep
```

在 `aggregate_from_cache` 內，把現有的：

```python
    _reconcile_github_projects(all_acts)
```

改為：

```python
    _reconcile_github_projects(all_acts)
    _reconcile_local_projects(all_acts)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_aggregator.py -v`
Expected: PASS（新測試 + 既有 reconcile_github / external 全綠）。

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): collapse same-repo groups across paths by canonical key (#37)"
```

---

### Task 6: Release 0.8.0

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: 找出所有 0.7.0 字串**

Run: `grep -rn "0\.7\.0" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: 6 處（pyproject `version`、SKILL.md `metadata.version`、plugin.json `version`、marketplace.json self-version + plugin entry、codex plugin.json `version`）。

- [ ] **Step 2: 全部改為 0.8.0 並刷新 lockfile**

逐處 `0.7.0` → `0.8.0`，然後：

Run: `uv lock`
Expected: `uv.lock` 把 `vibe-resume` 更新為 0.8.0。

- [ ] **Step 3: 加 CHANGELOG 區段**

在 `CHANGELOG.md` 最前面加（注意 em-dash `—`，沿用 house style）：

```markdown
## [0.8.0] — 2026-05-29

### Changed

- **Same logical repo worked from multiple paths now collapses into one
  project group** (#37). Extractors capture each path's normalized git
  `origin` remote + work-tree toplevel (`git_remote` / `git_toplevel` in
  `Activity.extra`); the aggregator derives an identity-proven canonical
  key (remote → toplevel) and rewrites duplicate groups onto one
  representative path. Fixes double-counted projects from clones, renamed
  dirs, and sub-package working directories. Merges only on proven identity
  — unrelated same-named repos (different remote) stay separate.

### Added

- `extractors/base.py::git_identity(path, cache)` helper + `_normalize_remote`
  — shared, memoized git-remote/toplevel resolver (reused by the upcoming
  #38 curate gate).
```

- [ ] **Step 4: 全套測試 + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: 全 PASS（含 `tests/test_skill_spec.py` 版本一致性斷言），ruff clean。

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.7.0 → 0.8.0"
```

---

## Self-Review

**1. Spec coverage**（對照 `2026-05-29-canonical-project-key-dedupe-design.md`）：
- extract 時捕捉 remote+toplevel → Task 2/3/4。✓
- `git_identity` 共用 helper + 正規化規則 → Task 1。✓
- canonical key 優先序（remote→toplevel→None）→ Task 5 `_canonical_key`。✓
- reconcile 代表路徑（優先 toplevel）→ Task 5 `_reconcile_local_projects`。✓
- 過度合併防護（同 basename 不同 remote 不併）→ Task 5 `test_reconcile_same_basename_different_remote_stays_split`。✓
- 接在 `_reconcile_github_projects` 之後 → Task 5 call site。✓
- 既有 extractor 測試相依修復（依子指令分派 / guard）→ Task 2 patch numstat；Task 3/4 靠 `Path.exists()` guard 自動 hermetic。✓
- memoize / timeout / 失敗 fallback → Task 1 `git_identity` / `_run_git`。✓
- project_aliases + GitHub 統一 = 非目標 → 計畫未含，正確。✓
- release 0.8.0 → Task 6。✓

**2. Placeholder scan:** 無 TBD/TODO；每個 code step 皆有完整程式碼。✓

**3. Type consistency:**
- `git_identity(path, cache=None) -> tuple[str|None, str|None]`：Task 1 定義，Task 2/3/4 呼叫一致（git_repos 用 `(repo, git_cache)`；claude_code/codex 用 `(cwd, git_cache)`）。✓
- `_canonical_key(act) -> str|None` / `_reconcile_local_projects(acts) -> None`：Task 5 定義與測試一致。✓
- extra 鍵 `git_remote` / `git_toplevel`：Task 2/3/4 寫入、Task 5 讀取，一致。✓
- `_process_session` 新增 `git_cache` 參數：claude_code（6 參數）、codex（5 參數）各自 extract 呼叫端一致更新。✓
