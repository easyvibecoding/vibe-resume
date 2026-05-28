# 0.7.0 — GitHub PR/Issue Extractor + Richer git/session Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `github` extractor that pulls PR/issue content + the author's own review-thread comments via `gh` CLI (issue #34), and widen the signal captured by the git/session extractors and the enricher input window (issue #35).

**Architecture:** A new `extractors/local/github.py` shells out to `gh` (no token handling, no new deps), maps each PR/issue to one `Activity`, and tags it `owned`/`external`. The aggregator gains a conservative reconcile pass that merges GitHub activities into the local git-repo project group by repo basename, plus a noise-filter exemption so a single high-value external merged PR is not dropped. Existing git/session extractors stop discarding body/file/conversation signal; the enricher's hard-coded `[:12]`/`[:200]` input window becomes config-driven. `PrivacyFilter` is extended to redact `list[str]` values in `extra` so review comments are scrubbed.

**Tech Stack:** Python 3.12+, `gh` CLI (subprocess), Pydantic v2, pytest, ruff, uv. Spec: `docs/superpowers/specs/2026-05-29-github-pr-issue-extractor-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/vibe_resume/core/privacy.py` | redaction; extend to scrub `list[str]` in `extra` | Modify |
| `src/vibe_resume/core/schema.py` | add `Source.GITHUB` | Modify |
| `src/vibe_resume/extractors/local/github.py` | gh shell, PR/issue→Activity, ownership detect | Create |
| `src/vibe_resume/core/runner.py` | register `github` in `LOCAL_EXTRACTORS` | Modify |
| `src/vibe_resume/core/aggregator.py` | `_reconcile_github_projects` + `_is_meaningful` exemption | Modify |
| `src/vibe_resume/core/enricher.py` | group-level external "contributed to" framing; config input window | Modify |
| `src/vibe_resume/core/enrich_jobs.py` | thread input-window params into `_build_prompt` | Modify |
| `src/vibe_resume/cli.py` | read `enrich.input_*` from cfg, pass to `emit_jobs` | Modify |
| `src/vibe_resume/extractors/base.py` | add `sample_spread` helper | Modify |
| `src/vibe_resume/extractors/local/git_repos.py` | capture `%b` body + filenames | Modify |
| `src/vibe_resume/extractors/local/claude_code.py` | spread-sample prompts + optional tool args | Modify |
| `src/vibe_resume/extractors/local/codex.py` | spread-sample prompts + optional function_call args | Modify |
| `src/vibe_resume/extractors/cloud_export/claude_ai.py` | keep assistant responses + more prompts | Modify |
| `config.example.yaml` | add `github:` + `sessions:` blocks; `enrich.input_*` | Modify |
| `tests/test_github_extractor.py` | extractor unit tests (mock `_gh_json`) | Create |
| `tests/test_privacy.py` | list[str] redaction test | Modify/Create |
| `tests/test_aggregator.py` | basename merge + external exemption | Modify |
| `tests/test_extractors.py` | git body/files + session sampling | Modify |
| `tests/test_enricher.py` | configurable window + framing | Modify |
| `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock` | 0.7.0 release bump | Modify |

**Execution order:** Part A (#34) → Part B (#35) → Part C (release). A1 must come before A2 (own_comments rely on list redaction). B2 (`sample_spread`) before B3/B4/B5.

---

# Part A — #34 GitHub PR/Issue Extractor

### Task A1: Extend PrivacyFilter to redact list[str] in `extra`

**Files:**
- Modify: `src/vibe_resume/core/privacy.py:78-88` (`PrivacyFilter.apply`)
- Test: `tests/test_privacy.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_privacy.py` (create the file if missing, with the import header):

```python
from vibe_resume.core.privacy import PrivacyFilter
from vibe_resume.core.schema import Activity, Source


def _cfg():
    return {"privacy": {"redact_patterns": ["sk-[A-Za-z0-9]{20,}"]}}


def test_redacts_str_list_in_extra():
    pf = PrivacyFilter(_cfg())
    act = Activity(
        source=Source.GITHUB,
        session_id="o/r#1",
        timestamp_start="2026-01-01T00:00:00+00:00",
        extra={
            "own_comments": ["looks good sk-ABCDEFGHIJKLMNOPQRSTU here", "second"],
            "number": 1,
        },
    )
    out = pf.apply(act)
    assert out is not None
    assert out.extra["own_comments"][0] == "looks good [REDACTED] here"
    assert out.extra["own_comments"][1] == "second"
    assert out.extra["number"] == 1  # non-str/list untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_privacy.py::test_redacts_str_list_in_extra -v`
Expected: FAIL (list element not redacted — equals original string with `sk-...`).

- [ ] **Step 3: Implement**

Replace the `extra` redaction block in `PrivacyFilter.apply` (currently `src/vibe_resume/core/privacy.py:84-87`):

```python
        if act.extra:
            act.extra = {k: self._redact_value(v) for k, v in act.extra.items()}
        return act

    def _redact_value(self, v: Any) -> Any:
        if isinstance(v, str):
            return self.redact(v)
        if isinstance(v, list):
            return [self.redact(x) if isinstance(x, str) else x for x in v]
        return v
```

(`Any` is already imported at `privacy.py:5`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_privacy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/privacy.py tests/test_privacy.py
git commit -m "fix(privacy): redact str elements inside list values in extra"
```

---

### Task A2: Add `Source.GITHUB` + github.py PR listing + ownership → Activity

**Files:**
- Modify: `src/vibe_resume/core/schema.py:59` (add enum value next to `GIT`)
- Create: `src/vibe_resume/extractors/local/github.py`
- Test: `tests/test_github_extractor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_github_extractor.py`:

```python
from datetime import UTC, datetime

import vibe_resume.extractors.local.github as gh
from vibe_resume.core.schema import ActivityType, Source


def _cfg(**over):
    base = {
        "enabled": True,
        "author_logins": ["alice"],
        "owned_owners": [],
        "repos_allow": [],
        "repos_block": [],
        "max_age_days": 100000,
        "max_items": 300,
        "include_issues": False,
        "fetch_comments": False,
        "fetch_files": False,
    }
    base.update(over)
    return {"extractors": {"github": base}}


def _pr(num, owner, repo, title="t", body="b", state="closed"):
    return {
        "number": num,
        "title": title,
        "body": body,
        "url": f"https://github.com/{owner}/{repo}/pull/{num}",
        "repository": {"name": repo, "nameWithOwner": f"{owner}/{repo}"},
        "state": state,
        "createdAt": "2026-01-01T00:00:00Z",
        "closedAt": "2026-01-02T00:00:00Z",
        "labels": [{"name": "bug"}],
        "isDraft": False,
    }


def test_pr_to_activity_owned_vs_external(monkeypatch):
    def fake_gh(args, timeout=30):
        if args[:2] == ["search", "prs"]:
            return [_pr(1, "alice", "myapp"), _pr(2, "facebook", "react")]
        return None
    monkeypatch.setattr(gh, "_gh_json", fake_gh)

    acts = gh.extract(_cfg())
    assert len(acts) == 2
    by_repo = {a.extra["repo"]: a for a in acts}

    owned = by_repo["alice/myapp"]
    assert owned.source == Source.GITHUB
    assert owned.activity_type == ActivityType.CODING
    assert owned.session_id == "alice/myapp#1"
    assert owned.extra["contribution"] == "owned"
    assert owned.extra["repo_owner"] == "alice"
    assert owned.keywords == ["bug"]
    assert owned.timestamp_start == datetime(2026, 1, 1, tzinfo=UTC)
    assert owned.timestamp_end == datetime(2026, 1, 2, tzinfo=UTC)

    external = by_repo["facebook/react"]
    assert external.extra["contribution"] == "external"
    assert external.extra["merged"] is False  # state closed, merged unknown → False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_github_extractor.py::test_pr_to_activity_owned_vs_external -v`
Expected: FAIL (module `github` has no `extract`/`_gh_json`).

- [ ] **Step 3a: Add enum value**

In `src/vibe_resume/core/schema.py`, add after line 59 (`GIT = "git"`):

```python
    GITHUB = "github"
```

- [ ] **Step 3b: Create github.py (PR path only for this task)**

Create `src/vibe_resume/extractors/local/github.py`:

```python
"""Collect the author's GitHub PRs/issues + own review-thread comments via `gh`.

One Activity per PR/issue. Owner-vs-author comparison tags each as
`owned` (your repo/org) or `external` (open-source / outside contribution).
All gh interaction funnels through `_gh_json` so tests can mock it; the
extractor never touches a token (auth is delegated to `gh`).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from typing import Any

from vibe_resume.core.schema import Activity, ActivityType, Source

NAME = "github"

PR_FIELDS = "number,title,body,url,repository,state,createdAt,closedAt,labels,isDraft"
ISSUE_FIELDS = "number,title,body,url,repository,state,createdAt,closedAt,labels"
BODY_MAX = 4000
SUMMARY_MAX = 500


def _gh_json(args: list[str], timeout: int = 30) -> Any:
    """Run `gh <args>` and json-parse stdout. Returns None on any failure
    (gh missing, non-zero exit, unparseable output)."""
    if not shutil.which("gh"):
        return None
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _resolve_logins(sub: dict[str, Any]) -> list[str]:
    logins = [str(x) for x in (sub.get("author_logins") or []) if str(x).strip()]
    if logins:
        return logins
    me = _gh_json(["api", "user", "--jq", ".login"])
    if isinstance(me, str) and me.strip():
        return [me.strip()]
    return ["@me"]


def _name_with_owner(item: dict[str, Any]) -> str:
    repo = item.get("repository") or {}
    return str(repo.get("nameWithOwner") or "")


def _labels(item: dict[str, Any]) -> list[str]:
    out = []
    for lb in item.get("labels") or []:
        name = lb.get("name") if isinstance(lb, dict) else None
        if name:
            out.append(str(name))
    return out


def _to_activity(item: dict[str, Any], kind: str, owned_set: set[str]) -> Activity | None:
    nwo = _name_with_owner(item)
    if "/" not in nwo:
        return None
    owner, repo = nwo.split("/", 1)
    num = item.get("number")
    start = _parse_ts(item.get("createdAt"))
    if start is None or num is None:
        return None
    end = _parse_ts(item.get("closedAt")) or start
    title = str(item.get("title") or "")
    body = str(item.get("body") or "")
    state = str(item.get("state") or "").lower()
    merged = bool(item.get("merged")) if kind == "pr" else False
    contribution = "owned" if owner in owned_set else "external"

    summary = title
    if body:
        summary = f"{title} — {body}".replace("\n", " ")
    return Activity(
        source=Source.GITHUB,
        session_id=f"{nwo}#{num}",
        timestamp_start=start,
        timestamp_end=end,
        project=nwo,
        activity_type=ActivityType.CODING if kind == "pr" else ActivityType.OTHER,
        keywords=_labels(item),
        summary=summary[:SUMMARY_MAX],
        raw_ref=str(item.get("url") or ""),
        extra={
            "kind": kind,
            "number": int(num),
            "repo": nwo,
            "repo_owner": owner,
            "contribution": contribution,
            "state": state,
            "merged": merged,
            "is_draft": bool(item.get("isDraft")) if kind == "pr" else False,
            "body": body[:BODY_MAX],
            "own_comments": [],
            "review_comment_count": 0,
        },
    )


def extract(cfg: dict[str, Any]) -> list[Activity]:
    sub = cfg["extractors"]["github"]
    logins = _resolve_logins(sub)
    owned_set = {x for x in logins if x != "@me"} | {
        str(o) for o in (sub.get("owned_owners") or [])
    }
    max_items = int(sub.get("max_items", 300))

    items: list[tuple[dict[str, Any], str]] = []
    for login in logins:
        prs = _gh_json(
            ["search", "prs", "--author", login, "--json", PR_FIELDS,
             "--limit", str(max_items)]
        )
        for it in prs or []:
            items.append((it, "pr"))

    acts: list[Activity] = []
    for it, kind in items:
        a = _to_activity(it, kind, owned_set)
        if a is not None:
            acts.append(a)
    return acts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_github_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/schema.py src/vibe_resume/extractors/local/github.py tests/test_github_extractor.py
git commit -m "feat(github): PR→Activity with owned/external ownership detection (#34)"
```

---

### Task A3: Issues, own-comments, fetch_files, and filters

**Files:**
- Modify: `src/vibe_resume/extractors/local/github.py`
- Test: `tests/test_github_extractor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_github_extractor.py`:

```python
def _issue(num, owner, repo, title="i"):
    return {
        "number": num, "title": title, "body": "ibody",
        "url": f"https://github.com/{owner}/{repo}/issues/{num}",
        "repository": {"name": repo, "nameWithOwner": f"{owner}/{repo}"},
        "state": "open", "createdAt": "2026-01-01T00:00:00Z",
        "closedAt": None, "labels": [],
    }


def test_includes_issues_and_own_comments_only(monkeypatch):
    def fake_gh(args, timeout=30):
        if args[:2] == ["search", "prs"]:
            return [_pr(1, "alice", "myapp")]
        if args[:2] == ["search", "issues"]:
            return [_issue(7, "alice", "myapp")]
        if args[0] == "api" and "/comments" in args[1]:
            return [
                {"user": {"login": "alice"}, "body": "my note"},
                {"user": {"login": "bob"}, "body": "their note"},
            ]
        return None
    monkeypatch.setattr(gh, "_gh_json", fake_gh)

    acts = gh.extract(_cfg(include_issues=True, fetch_comments=True))
    kinds = sorted(a.extra["kind"] for a in acts)
    assert kinds == ["issue", "pr"]
    pr = next(a for a in acts if a.extra["kind"] == "pr")
    assert pr.extra["own_comments"] == ["my note"]   # bob filtered out
    assert pr.extra["review_comment_count"] == 1
    assert pr.user_prompts_count == 1


def test_repos_block_and_max_age(monkeypatch):
    old = _pr(1, "alice", "old")
    old["createdAt"] = "2000-01-01T00:00:00Z"
    blocked = _pr(2, "alice", "secret")
    keep = _pr(3, "alice", "myapp")

    def fake_gh(args, timeout=30):
        if args[:2] == ["search", "prs"]:
            return [old, blocked, keep]
        return None
    monkeypatch.setattr(gh, "_gh_json", fake_gh)

    acts = gh.extract(_cfg(max_age_days=3650, repos_block=["alice/secret"]))
    repos = {a.extra["repo"] for a in acts}
    assert repos == {"alice/myapp"}   # old dropped by age, secret by block


def test_repos_allow_whitelist(monkeypatch):
    def fake_gh(args, timeout=30):
        if args[:2] == ["search", "prs"]:
            return [_pr(1, "alice", "myapp"), _pr(2, "alice", "other")]
        return None
    monkeypatch.setattr(gh, "_gh_json", fake_gh)
    acts = gh.extract(_cfg(repos_allow=["alice/myapp"]))
    assert {a.extra["repo"] for a in acts} == {"alice/myapp"}


def test_gh_missing_returns_empty(monkeypatch):
    monkeypatch.setattr(gh, "_gh_json", lambda args, timeout=30: None)
    assert gh.extract(_cfg()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_github_extractor.py -v`
Expected: the four new tests FAIL (issues/comments/filters not implemented).

- [ ] **Step 3: Implement**

Add helpers and rewrite `extract` in `src/vibe_resume/extractors/local/github.py`.

Add a `from datetime import timedelta` to the datetime import line:

```python
from datetime import UTC, datetime, timedelta
```

Add these helpers above `extract`:

```python
def _allowed(nwo: str, allow: list[str], block: list[str]) -> bool:
    if block and nwo in block:
        return False
    if allow:
        return nwo in allow
    return True


def _own_comments(nwo: str, kind: str, number: int, logins: set[str]) -> list[str]:
    owner, repo = nwo.split("/", 1)
    endpoints = [f"repos/{owner}/{repo}/issues/{number}/comments"]
    if kind == "pr":
        endpoints.insert(0, f"repos/{owner}/{repo}/pulls/{number}/comments")
    out: list[str] = []
    for ep in endpoints:
        data = _gh_json(["api", ep])
        for c in data or []:
            user = (c.get("user") or {}).get("login")
            body = c.get("body")
            if user in logins and isinstance(body, str) and body.strip():
                out.append(body)
    return out


def _changed_files(nwo: str, number: int) -> list[str]:
    owner, repo = nwo.split("/", 1)
    data = _gh_json(["api", f"repos/{owner}/{repo}/pulls/{number}/files",
                     "--jq", ".[].filename"])
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, str):
        return [ln for ln in data.splitlines() if ln.strip()]
    return []
```

Replace `extract` with:

```python
def extract(cfg: dict[str, Any]) -> list[Activity]:
    sub = cfg["extractors"]["github"]
    logins = _resolve_logins(sub)
    login_set = {x for x in logins if x != "@me"}
    owned_set = login_set | {str(o) for o in (sub.get("owned_owners") or [])}
    max_items = int(sub.get("max_items", 300))
    allow = [str(x) for x in (sub.get("repos_allow") or [])]
    block = [str(x) for x in (sub.get("repos_block") or [])]
    include_issues = bool(sub.get("include_issues", True))
    fetch_comments = bool(sub.get("fetch_comments", True))
    fetch_files = bool(sub.get("fetch_files", False))
    max_age = int(sub.get("max_age_days", 1095))
    cutoff = datetime.now(UTC) - timedelta(days=max_age)

    raw: list[tuple[dict[str, Any], str]] = []
    for login in logins:
        prs = _gh_json(["search", "prs", "--author", login, "--json", PR_FIELDS,
                        "--limit", str(max_items)])
        for it in prs or []:
            raw.append((it, "pr"))
        if include_issues:
            iss = _gh_json(["search", "issues", "--author", login,
                            "--json", ISSUE_FIELDS, "--limit", str(max_items)])
            for it in iss or []:
                raw.append((it, "issue"))

    acts: list[Activity] = []
    for it, kind in raw:
        a = _to_activity(it, kind, owned_set)
        if a is None:
            continue
        if not _allowed(a.extra["repo"], allow, block):
            continue
        if a.timestamp_start < cutoff:
            continue
        if fetch_comments:
            comments = _own_comments(a.extra["repo"], kind, a.extra["number"],
                                     login_set or {a.extra["repo_owner"]})
            a.extra["own_comments"] = comments
            a.extra["review_comment_count"] = len(comments)
            a.user_prompts_count = len(comments)
        if fetch_files and kind == "pr":
            a.files_touched = _changed_files(a.extra["repo"], a.extra["number"])[:20]
        acts.append(a)

    acts.sort(key=lambda a: a.timestamp_start, reverse=True)
    return acts[:max_items]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_github_extractor.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/github.py tests/test_github_extractor.py
git commit -m "feat(github): issues, own-comments filter, file fetch, repo/age filters (#34)"
```

---

### Task A4: Register extractor + config block

**Files:**
- Modify: `src/vibe_resume/core/runner.py:26-41` (`LOCAL_EXTRACTORS`)
- Modify: `config.example.yaml` (after the `git_repos:` block, ~line 74)
- Test: `tests/test_github_extractor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_github_extractor.py`:

```python
def test_github_registered_and_in_config_example():
    from pathlib import Path

    import yaml

    from vibe_resume.core.runner import LOCAL_EXTRACTORS

    assert "github" in LOCAL_EXTRACTORS

    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config.example.yaml").read_text())
    gh_cfg = cfg["extractors"]["github"]
    assert gh_cfg["enabled"] is False          # default off (network + gh + account-bound)
    assert gh_cfg["fetch_files"] is False
    assert "author_logins" in gh_cfg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_github_extractor.py::test_github_registered_and_in_config_example -v`
Expected: FAIL (`github` not in `LOCAL_EXTRACTORS`).

- [ ] **Step 3a: Register in runner**

In `src/vibe_resume/core/runner.py`, add `"github",` to the `LOCAL_EXTRACTORS` list (after `"git_repos",` at line 40):

```python
    "git_repos",
    "github",
]
```

- [ ] **Step 3b: Add config block**

In `config.example.yaml`, immediately after the `git_repos:` block (after `author_emails: []` ~line 74), add:

```yaml
  github:
    enabled: false           # network + needs `gh` CLI logged in + account-bound; opt in
    author_logins: []        # empty → gh's currently-authenticated user (@me)
    owned_owners: []         # owners/orgs to treat as "yours" (else PRs count as external/OSS)
    repos_allow: []          # empty → all repos; non-empty → only these owner/repo
    repos_block: []          # owner/repo to exclude
    max_age_days: 1095       # ~3 years
    max_items: 300           # cap PRs+issues (guards search-API rate limit)
    include_issues: true
    fetch_comments: true     # your own review/issue-thread comments
    fetch_files: false       # per-PR changed-file paths (extra API calls)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_github_extractor.py::test_github_registered_and_in_config_example -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/runner.py config.example.yaml tests/test_github_extractor.py
git commit -m "feat(github): register extractor + config.example block (#34)"
```

---

### Task A5: Aggregator basename reconcile pass

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py` (add `_reconcile_github_projects`; call in `aggregate_from_cache` after the load loop, before `buckets` build at line 269)
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_aggregator.py`:

```python
from vibe_resume.core.aggregator import _reconcile_github_projects
from vibe_resume.core.schema import Activity, Source


def _git_act(path):
    return Activity(source=Source.GIT, session_id="x",
                    timestamp_start="2026-01-01T00:00:00+00:00", project=path)


def _gh_act(nwo):
    return Activity(source=Source.GITHUB, session_id=f"{nwo}#1",
                    timestamp_start="2026-01-01T00:00:00+00:00", project=nwo,
                    extra={"repo": nwo})


def test_reconcile_merges_github_into_local_by_basename():
    acts = [_git_act("/Users/me/code/myapp"), _gh_act("acme/myapp")]
    _reconcile_github_projects(acts)
    assert acts[1].project == "/Users/me/code/myapp"   # rewritten to local path


def test_reconcile_keeps_unmatched_github_repo():
    acts = [_git_act("/Users/me/code/other"), _gh_act("facebook/react")]
    _reconcile_github_projects(acts)
    assert acts[1].project == "facebook/react"          # no local match → unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_aggregator.py -k reconcile -v`
Expected: FAIL (`_reconcile_github_projects` undefined).

- [ ] **Step 3: Implement**

Add to `src/vibe_resume/core/aggregator.py` (place above `aggregate_from_cache`, ~line 254):

```python
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
```

Call it in `aggregate_from_cache` right after the activity-loading loop (after line 264 `all_acts.append(pa)` block, before `prior_enrich = _load_prior_enrichment()`):

```python
    _reconcile_github_projects(all_acts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_aggregator.py -k reconcile -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): merge GitHub PRs into local repo group by basename (#34)"
```

---

### Task A6: Noise-filter exemption for external merged PRs

**Files:**
- Modify: `src/vibe_resume/core/aggregator.py:146-159` (`_is_meaningful`)
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_aggregator.py`:

```python
from vibe_resume.core.aggregator import _is_meaningful
from vibe_resume.core.schema import ProjectGroup


def _grp(name, acts):
    return ProjectGroup(
        name=name, first_activity="2026-01-01T00:00:00+00:00",
        last_activity="2026-01-01T00:00:00+00:00",
        total_sessions=len(acts), activities=acts,
    )


def _ext_pr(merged):
    return Activity(source=Source.GITHUB, session_id="facebook/react#1",
                    timestamp_start="2026-01-01T00:00:00+00:00",
                    project="facebook/react",
                    extra={"repo": "facebook/react", "contribution": "external",
                           "merged": merged})


def test_single_external_merged_pr_survives_noise_filter():
    g = _grp("react", [_ext_pr(True)])      # 1 session, breadth 0
    assert _is_meaningful("facebook/react", g, min_sessions=2) is True


def test_single_external_unmerged_pr_still_filtered():
    g = _grp("react", [_ext_pr(False)])
    assert _is_meaningful("facebook/react", g, min_sessions=2) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_aggregator.py -k external -v`
Expected: `test_single_external_merged_pr_survives_noise_filter` FAILS (dropped by session<2).

- [ ] **Step 3: Implement**

In `src/vibe_resume/core/aggregator.py`, edit `_is_meaningful` — add the exemption right after the `leaf in NOISE_LEAFS` check (after current line 152), before the hash-id and session-count checks:

```python
    if leaf in key_lc and leaf in NOISE_LEAFS:
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
```

(`Source` is already imported at `aggregator.py:17`. Keep the existing `leaf in NOISE_LEAFS` line as-is — only the new block is added after it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_aggregator.py -k external -v`
Expected: PASS both.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/aggregator.py tests/test_aggregator.py
git commit -m "feat(aggregator): exempt external merged PRs from noise filter (#34)"
```

---

### Task A7: Enricher "contributed to" framing for external groups

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (`_build_prompt`, ~line 224-283; add a framing block)
- Test: `tests/test_enricher.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_enricher.py`:

```python
from vibe_resume.core.enricher import _build_prompt
from vibe_resume.core.schema import Activity, ProjectGroup, Source


def _ext_group():
    a = Activity(source=Source.GITHUB, session_id="facebook/react#1",
                 timestamp_start="2026-01-01T00:00:00+00:00",
                 project="facebook/react", summary="fixed a reconciler bug",
                 extra={"repo": "facebook/react", "contribution": "external",
                        "merged": True})
    return ProjectGroup(name="react", first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=1, activities=[a])


def _owned_group():
    a = Activity(source=Source.GITHUB, session_id="me/app#1",
                 timestamp_start="2026-01-01T00:00:00+00:00",
                 project="me/app", summary="built dashboard",
                 extra={"repo": "me/app", "contribution": "owned", "merged": True})
    return ProjectGroup(name="app", first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=1, activities=[a])


def test_external_group_prompt_says_contributed_to():
    assert "contributed to" in _build_prompt(_ext_group()).lower()


def test_owned_group_prompt_has_no_contribution_framing():
    assert "contributed to" not in _build_prompt(_owned_group()).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_enricher.py -k contributed -v`
Expected: `test_external_group_prompt_says_contributed_to` FAILS.

- [ ] **Step 3: Implement**

In `src/vibe_resume/core/enricher.py`, add a module constant near the other `*_BLOCK_TEMPLATE` definitions:

```python
CONTRIBUTION_BLOCK = (
    "\n\nNOTE: This work is an EXTERNAL open-source contribution to a "
    "repository the candidate does not own. Frame bullets as "
    "\"contributed to <project>\" / \"submitted <change> to <project>\" — "
    "never imply the candidate built or owns the project.\n"
)
```

In `_build_prompt`, before the final `return body` (after the `company` block, ~line 282), add:

```python
    gh_acts = [a for a in g.activities if a.source == Source.GITHUB]
    if gh_acts and all(
        (a.extra or {}).get("contribution") == "external" for a in gh_acts
    ):
        body += CONTRIBUTION_BLOCK
```

Ensure `Source` is imported in `enricher.py` (it imports from `vibe_resume.core.schema`; add `Source` to that import if absent).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_enricher.py -k contributed -v`
Expected: PASS both.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py tests/test_enricher.py
git commit -m "feat(enricher): frame external OSS groups as 'contributed to' (#34)"
```

---

# Part B — #35 Richer git/session Signal

### Task B1: git_repos captures commit body + filenames

**Files:**
- Modify: `src/vibe_resume/extractors/local/git_repos.py` (`_git_log` rewrite at lines 67-119; `extract` bucket loop at lines 146-171)
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:

```python
import subprocess

import vibe_resume.extractors.local.git_repos as gr


def test_git_log_parses_body_and_files(monkeypatch):
    RS, US = "\x1e", "\x1f"
    out = (
        f"{RS}abc123{US}2026-01-01T00:00:00+00:00{US}Fix bug{US}"
        "Root cause: race in cache.\nWeighed lock vs CAS; chose CAS.\n"
        "12\t3\tsrc/cache.py\n4\t0\ttests/test_cache.py\n"
        f"{RS}def456{US}2026-01-02T00:00:00+00:00{US}Tidy{US}"
        "1\t1\tREADME.md\n"
    )
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=out, stderr=""),
    )
    commits = gr._git_log(gr.Path("/x"), ["me@x.com"])
    assert len(commits) == 2
    c0 = commits[0]
    assert c0.subject == "Fix bug"
    assert "Root cause: race" in c0.body
    assert "chose CAS" in c0.body
    assert c0.insertions == 16 and c0.deletions == 3
    assert c0.files == ["src/cache.py", "tests/test_cache.py"]
    assert commits[1].body == ""        # commit with no body
    assert commits[1].files == ["README.md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extractors.py::test_git_log_parses_body_and_files -v`
Expected: FAIL (`_git_log` returns 5-tuples without `.body`/`.files`; no NamedTuple).

- [ ] **Step 3: Implement**

In `src/vibe_resume/extractors/local/git_repos.py`:

Add imports near the top (after existing imports):

```python
import re
from typing import NamedTuple
```

Add module constants after `SCAN_TIMEOUT_SECONDS` (line 21):

```python
_RS = "\x1e"
_US = "\x1f"
_NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")
_MAX_FILES_PER_MONTH = 20
_MAX_BODIES_PER_MONTH = 5
_BODY_EXCERPT = 500
_SUMMARY_MAX = 4000


class Commit(NamedTuple):
    dt: datetime
    sha: str
    subject: str
    body: str
    insertions: int
    deletions: int
    files: list[str]
```

Replace `_git_log` (lines 67-119) with:

```python
def _git_log(repo: Path, emails: list[str]) -> list[Commit]:
    author_filters: list[str] = []
    for e in emails:
        author_filters += ["--author", e]
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--no-merges",
             f"--pretty=format:{_RS}%H{_US}%aI{_US}%s{_US}%b",
             "--numstat", *author_filters],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []

    commits: list[Commit] = []
    for rec in out.stdout.split(_RS):
        if not rec.strip():
            continue
        parts = rec.split(_US, 3)
        if len(parts) < 4:
            continue
        sha, ts, subject, tail = parts
        lines = tail.split("\n")
        i = len(lines)
        while i > 0 and _NUMSTAT_RE.match(lines[i - 1]):
            i -= 1
        body = "\n".join(lines[:i]).strip()
        ins = dels = 0
        files: list[str] = []
        for nl in lines[i:]:
            m = _NUMSTAT_RE.match(nl)
            if not m:
                continue
            a, d, path = m.group(1), m.group(2), m.group(3)
            if a != "-":
                ins += int(a)
            if d != "-":
                dels += int(d)
            files.append(path)
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        commits.append(Commit(dt, sha, subject, body, ins, dels, files))
    return commits
```

Update the bucket loop in `extract` (lines 146-171). Replace the `for ym, items in buckets.items():` body with:

```python
        for ym, items in buckets.items():
            first = min(c.dt for c in items)
            last = max(c.dt for c in items)
            ins = sum(c.insertions for c in items)
            dels = sum(c.deletions for c in items)
            subjects = [c.subject for c in items][:10]
            bodies = [c.body for c in items if c.body][:_MAX_BODIES_PER_MONTH]
            files: list[str] = []
            for c in items:
                for f in c.files:
                    if f not in files:
                        files.append(f)
                if len(files) >= _MAX_FILES_PER_MONTH:
                    break
            files = files[:_MAX_FILES_PER_MONTH]
            summary = " | ".join(s[:80] for s in subjects[:3])
            if bodies:
                summary = f"{summary} ‖ {bodies[0].replace(chr(10), ' ')}"
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
                    extra={
                        "commits": len(items),
                        "insertions": ins,
                        "deletions": dels,
                        "subjects": subjects,
                        "commit_bodies": [b[:_BODY_EXCERPT] for b in bodies],
                    },
                )
            )
```

Note `c[0]` references elsewhere in `extract` (the bucket key line `key = c[0].strftime(...)`) must become `c.dt.strftime(...)`. Update that line in the bucketing block (currently `git_repos.py:143`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extractors.py::test_git_log_parses_body_and_files tests/test_extractors.py -k git -v`
Expected: PASS (and existing git_repos tests still pass).

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/git_repos.py tests/test_extractors.py
git commit -m "feat(git): capture commit body + touched filenames (#35)"
```

---

### Task B2: `sample_spread` helper + `sessions:` config block

**Files:**
- Modify: `src/vibe_resume/extractors/base.py` (add `sample_spread`)
- Modify: `config.example.yaml` (add top-level `sessions:` block)
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:

```python
from vibe_resume.extractors.base import sample_spread


def test_sample_spread_dedupes_and_picks_endpoints():
    assert sample_spread(["a", "a", "b", "c", "d", "e"], 3) == ["a", "c", "e"]


def test_sample_spread_returns_all_when_under_k():
    assert sample_spread(["a", "b"], 5) == ["a", "b"]


def test_sample_spread_empty():
    assert sample_spread([], 3) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extractors.py -k sample_spread -v`
Expected: FAIL (no `sample_spread`).

- [ ] **Step 3a: Implement helper**

Add to `src/vibe_resume/extractors/base.py`:

```python
def sample_spread(items: list[str], k: int) -> list[str]:
    """Dedupe (keeping first occurrence) then return up to k items spread
    evenly across the list, always including the first and last."""
    seen: set[str] = set()
    uniq: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            uniq.append(it)
    if k <= 0:
        return []
    if len(uniq) <= k:
        return uniq
    if k == 1:
        return uniq[:1]
    last = len(uniq) - 1
    idxs = sorted({round(i * last / (k - 1)) for i in range(k)})
    return [uniq[i] for i in idxs]
```

- [ ] **Step 3b: Add config block**

In `config.example.yaml`, add a top-level block (sibling of `scan:` / `privacy:`, e.g. after the `extractors:` section):

```yaml
# Shared knobs for conversation-style extractors (claude_code, codex, claude_ai).
sessions:
  sample_prompts: 12        # how many user prompts to keep per session (spread across timeline)
  per_prompt_chars: 300     # char budget per kept prompt
  capture_tool_args: false  # also keep a sample of tool-call arguments (redacted)
  keep_assistant: true      # claude.ai export: keep assistant responses too
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extractors.py -k sample_spread -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/base.py config.example.yaml tests/test_extractors.py
git commit -m "feat(extractors): add sample_spread helper + sessions config block (#35)"
```

---

### Task B3: claude_code spread-sampling + optional tool args

**Files:**
- Modify: `src/vibe_resume/extractors/local/claude_code.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py` (uses the project-dir/jsonl layout the extractor expects; write a small session file):

```python
import json as _json

import vibe_resume.extractors.local.claude_code as cc


def _write_session(tmp_path, rows):
    proj = tmp_path / "proj"
    proj.mkdir()
    f = proj / "s.jsonl"
    f.write_text("\n".join(_json.dumps(r) for r in rows))
    return proj


def test_claude_code_samples_more_and_captures_tool_args(tmp_path):
    rows = []
    for i in range(20):
        rows.append({"type": "user", "timestamp": f"2026-01-01T00:{i:02d}:00Z",
                     "message": {"content": f"prompt number {i}"}})
    rows.append({"type": "assistant", "timestamp": "2026-01-01T00:30:00Z",
                 "message": {"content": [{"type": "tool_use", "name": "Bash",
                                          "input": {"command": "rm -rf build"}}]}})
    _write_session(tmp_path, rows)
    cfg = {"extractors": {"claude_code": {"path": str(tmp_path)}},
           "sessions": {"sample_prompts": 5, "per_prompt_chars": 300,
                        "capture_tool_args": True}}
    acts = cc.extract(cfg)
    assert len(acts) == 1
    a = acts[0]
    # spread sampling keeps first + last prompt, not just the first few
    assert "prompt number 0" in a.summary
    assert "prompt number 19" in a.summary
    assert "rm -rf build" in a.extra["tool_args"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extractors.py::test_claude_code_samples_more_and_captures_tool_args -v`
Expected: FAIL (only first ~8 prompts kept; no `tool_args`).

- [ ] **Step 3: Implement**

In `src/vibe_resume/extractors/local/claude_code.py`:

- Add import: `from vibe_resume.extractors.base import iter_jsonl, sample_spread`
- Add constant near top: `_SUMMARY_MAX = 4000`
- Change `extract` to read session cfg and pass to `_process_session`:

```python
def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["claude_code"]["path"])
    if not base.exists():
        return []
    sess = cfg.get("sessions", {})
    sample_n = int(sess.get("sample_prompts", 12))
    per_chars = int(sess.get("per_prompt_chars", 300))
    capture_args = bool(sess.get("capture_tool_args", False))

    activities: list[Activity] = []
    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            if "/subagents/" in str(jsonl_file):
                continue
            act = _process_session(jsonl_file, project_dir.name,
                                   sample_n, per_chars, capture_args)
            if act:
                activities.append(act)
    return activities
```

- Change `_process_session` signature and body. Update the signature to:

```python
def _process_session(path: Path, project_dirname: str,
                     sample_n: int, per_chars: int, capture_args: bool) -> Activity | None:
```

- Add `tool_args: list[str] = []` next to the other accumulators.
- Remove the `if len(user_text_chunks) < 8:` cap — collect every prompt:

```python
            if txt and not txt.startswith("<") and "<system-reminder>" not in txt:
                user_prompt_count += 1
                user_text_chunks.append(txt[:per_chars])
```

- In the `tool_use` branch, after recording the file path, capture args when enabled:

```python
                    if capture_args and len(tool_args) < sample_n:
                        import json as _json
                        try:
                            tool_args.append(_json.dumps(inp)[:per_chars])
                        except (TypeError, ValueError):
                            pass
```

- Replace the summary/extra construction:

```python
    sampled = sample_spread(user_text_chunks, sample_n)
    summary_preview = " | ".join(sampled)[:_SUMMARY_MAX]
    keywords = sorted(tool_names, key=lambda k: -tool_names[k])[:10]
    extra: dict[str, Any] = {"git_branch": git_branch, "tool_histogram": dict(tool_names)}
    if capture_args and tool_args:
        extra["tool_args"] = "\n".join(tool_args)
```

…and pass `summary=summary_preview` (drop the old `[:500]`) and `extra=extra` into the `Activity(...)` call.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extractors.py -k claude_code -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/claude_code.py tests/test_extractors.py
git commit -m "feat(claude_code): spread-sample prompts + optional tool args (#35)"
```

---

### Task B4: codex spread-sampling + optional function_call args

**Files:**
- Modify: `src/vibe_resume/extractors/local/codex.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:

```python
import vibe_resume.extractors.local.codex as cx


def test_codex_samples_more_and_captures_function_args(tmp_path):
    rows = [{"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z",
             "payload": {"cwd": "/proj", "id": "sess1"}}]
    for i in range(20):
        rows.append({"type": "response_item", "timestamp": f"2026-01-01T00:{i:02d}:00Z",
                     "payload": {"type": "message", "role": "user",
                                 "content": f"codex prompt {i}"}})
    rows.append({"type": "response_item", "timestamp": "2026-01-01T00:30:00Z",
                 "payload": {"type": "function_call", "name": "shell",
                             "arguments": '{"command": "pytest -q"}'}})
    f = tmp_path / "rollout-2026-01-01-uuid.jsonl"
    f.write_text("\n".join(_json.dumps(r) for r in rows))
    cfg = {"extractors": {"codex": {"path": str(tmp_path)}},
           "sessions": {"sample_prompts": 5, "per_prompt_chars": 300,
                        "capture_tool_args": True}}
    acts = cx.extract(cfg)
    assert len(acts) == 1
    a = acts[0]
    assert "codex prompt 0" in a.summary
    assert "codex prompt 19" in a.summary
    assert "pytest -q" in a.extra["tool_args"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extractors.py::test_codex_samples_more_and_captures_function_args -v`
Expected: FAIL (first ~8 only; no `tool_args`).

- [ ] **Step 3: Implement**

In `src/vibe_resume/extractors/local/codex.py`:

- Add import: `from vibe_resume.extractors.base import iter_jsonl, sample_spread`
- Add constant: `_SUMMARY_MAX = 4000`
- `extract` reads session cfg and passes to `_process_session`:

```python
def extract(cfg: dict[str, Any]) -> list[Activity]:
    codex_cfg = cfg["extractors"]["codex"]
    sess = cfg.get("sessions", {})
    sample_n = int(sess.get("sample_prompts", 12))
    per_chars = int(sess.get("per_prompt_chars", 300))
    capture_args = bool(sess.get("capture_tool_args", False))
    bases: list[Path] = []
    for key in ("path", "archived_path"):
        raw = codex_cfg.get(key)
        if raw:
            p = Path(raw).expanduser()
            if p.exists():
                bases.append(p)

    activities: list[Activity] = []
    seen_session_ids: set[str] = set()
    for base in bases:
        for rollout_file in base.rglob("rollout-*.jsonl"):
            act = _process_session(rollout_file, sample_n, per_chars, capture_args)
            if not act:
                continue
            if act.session_id in seen_session_ids:
                continue
            seen_session_ids.add(act.session_id)
            activities.append(act)
    return activities
```

- `_process_session` signature → `def _process_session(path, sample_n, per_chars, capture_args):`
- Add `tool_args: list[str] = []` accumulator.
- Remove the `if len(user_text_chunks) < 8:` cap:

```python
            if txt and not txt.startswith("<") and "<system-reminder>" not in txt:
                user_prompts += 1
                user_text_chunks.append(txt[:per_chars])
```

- In the `function_call` branch, capture args:

```python
            if capture_args and len(tool_args) < sample_n:
                raw_args = payload.get("arguments")
                if isinstance(raw_args, str) and raw_args.strip():
                    tool_args.append(raw_args[:per_chars])
```

- Replace summary/extra build:

```python
    summary = " | ".join(sample_spread(user_text_chunks, sample_n))[:_SUMMARY_MAX]
    keywords = sorted(tool_names, key=lambda k: -tool_names[k])[:10]
    extra: dict[str, Any] = {}
    if cli_version:
        extra["cli_version"] = cli_version
    if git_branch:
        extra["git_branch"] = git_branch
    if capture_args and tool_args:
        extra["tool_args"] = "\n".join(tool_args)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extractors.py -k codex -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/local/codex.py tests/test_extractors.py
git commit -m "feat(codex): spread-sample prompts + optional function_call args (#35)"
```

---

### Task B5: claude.ai export keeps assistant responses + more prompts

**Files:**
- Modify: `src/vibe_resume/extractors/cloud_export/claude_ai.py:69-90`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extractors.py`:

```python
import vibe_resume.extractors.cloud_export.claude_ai as cai


def test_claude_ai_keeps_assistant_responses(tmp_path):
    conv = {"uuid": "u1", "name": "chat", "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T01:00:00Z",
            "chat_messages": [
                {"sender": "human", "text": "how do I debounce in react"},
                {"sender": "assistant", "text": "use useEffect with a timer"},
                {"sender": "human", "text": "and cleanup?"},
                {"sender": "assistant", "text": "return a clearTimeout"},
            ]}
    import json as _j
    (tmp_path / "conversations.json").write_text(_j.dumps([conv]))
    cfg = {"extractors": {"cloud_claude_ai": {"import_dir": str(tmp_path)}},
           "sessions": {"sample_prompts": 12, "keep_assistant": True}}
    acts = cai.extract(cfg)
    assert len(acts) == 1
    blob = acts[0].summary + " " + (acts[0].extra.get("assistant", "") if acts[0].extra else "")
    assert "debounce" in blob
    assert "clearTimeout" in blob   # assistant response retained
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extractors.py::test_claude_ai_keeps_assistant_responses -v`
Expected: FAIL (assistant text dropped).

- [ ] **Step 3: Implement**

In `src/vibe_resume/extractors/cloud_export/claude_ai.py`, add import at top:

```python
from vibe_resume.extractors.base import sample_spread
```

Read session cfg in `extract` (after `import_dir` resolution, before the loop):

```python
    sess = cfg.get("sessions", {})
    sample_n = int(sess.get("sample_prompts", 12))
    per_chars = int(sess.get("per_prompt_chars", 300))
    keep_assistant = bool(sess.get("keep_assistant", True))
```

Replace the snippet-building block (lines 69-90) with:

```python
            human_chunks: list[str] = []
            asst_chunks: list[str] = []
            for m in msgs:
                t = (m.get("text") or "")[:per_chars]
                if not t:
                    continue
                if m.get("sender") == "human":
                    human_chunks.append(t)
                elif m.get("sender") == "assistant":
                    asst_chunks.append(t)
            summary = " | ".join(sample_spread(human_chunks, sample_n))[:4000]
            extra: dict[str, Any] = {}
            if keep_assistant and asst_chunks:
                extra["assistant"] = " | ".join(sample_spread(asst_chunks, sample_n))[:4000]
            activities.append(
                Activity(
                    source=Source.CLAUDE_AI,
                    session_id=conv.get("uuid") or "",
                    timestamp_start=start,
                    timestamp_end=end,
                    project=conv.get("name") or None,
                    activity_type=ActivityType.CHAT,
                    user_prompts_count=user_n,
                    tool_calls_count=asst_n,
                    summary=summary,
                    raw_ref=f"{conv_file}#{conv.get('uuid','')}",
                    extra=extra,
                )
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_extractors.py -k claude_ai -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/extractors/cloud_export/claude_ai.py tests/test_extractors.py
git commit -m "feat(claude_ai): retain assistant responses + spread-sample prompts (#35)"
```

---

### Task B6: Configurable enricher input window

**Files:**
- Modify: `src/vibe_resume/core/enricher.py` (`_build_prompt` signature + `g.activities[:12]`/`s[:200]` at lines 233-237; `enrich_groups` call site ~738)
- Modify: `src/vibe_resume/core/enrich_jobs.py` (`emit_jobs` signature + `_build_prompt` call ~128)
- Modify: `src/vibe_resume/cli.py` (enrich command: read cfg, pass to `emit_jobs`)
- Test: `tests/test_enricher.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_enricher.py`:

```python
def _many_act_group(n):
    acts = [Activity(source=Source.GIT, session_id=f"s{i}",
                     timestamp_start="2026-01-01T00:00:00+00:00",
                     summary=f"activity-{i} " + "x" * 400) for i in range(n)]
    return ProjectGroup(name="big", first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=n, activities=acts)


def test_build_prompt_default_window():
    g = _many_act_group(30)
    p = _build_prompt(g)
    assert "activity-11" in p          # first 12 included (0..11)
    assert "activity-12" not in p      # 13th excluded by default cap 12


def test_build_prompt_wider_window():
    g = _many_act_group(30)
    p = _build_prompt(g, max_activities=20, char_budget=500)
    assert "activity-19" in p          # 20 activities now included
    # 500-char budget keeps more of each line than the 200 default
    assert p.count("x" * 300) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_enricher.py -k window -v`
Expected: FAIL (`_build_prompt` has no `max_activities`/`char_budget` params).

- [ ] **Step 3a: Add params to `_build_prompt`**

In `src/vibe_resume/core/enricher.py`, change the signature (line 224) to add two keyword params:

```python
def _build_prompt(
    g: ProjectGroup,
    locale_meta: dict[str, Any] | None = None,
    tailor_keywords: list[str] | None = None,
    persona: Persona | None = None,
    level: LevelArchetype | None = None,
    company: CompanyProfile | None = None,
    max_activities: int = 12,
    char_budget: int = 200,
) -> str:
```

Change the raw-line loop (lines 233-237):

```python
    raw_lines: list[str] = []
    for a in g.activities[:max_activities]:
        s = (a.summary or "").strip().replace("\n", " ")
        if s:
            s = s.replace("</", "< /")
            raw_lines.append(f"- [{a.source.value}] {s[:char_budget]}")
```

- [ ] **Step 3b: Thread from `enrich_groups`**

In `enrich_groups` (`enricher.py`), resolve once before the group loop (near line 717 where `use_llm` is set):

```python
    enr = cfg.get("enrich", {})
    input_activities = int(enr.get("input_activities", 12))
    input_char_budget = int(enr.get("input_char_budget", 200))
```

Pass them in the `_build_prompt(...)` call (~line 738):

```python
                _build_prompt(
                    g,
                    locale_meta,
                    tailor_keywords=tailor_keywords,
                    persona=persona_obj,
                    level=level_obj,
                    company=company_obj,
                    max_activities=input_activities,
                    char_budget=input_char_budget,
                )
```

- [ ] **Step 3c: Thread through `emit_jobs`**

In `src/vibe_resume/core/enrich_jobs.py`, add two keyword params to `emit_jobs` (after `clean: bool = False`):

```python
    input_activities: int = 12,
    input_char_budget: int = 200,
```

Pass them in the `_build_prompt(...)` call (~line 128):

```python
        prompt_body = _build_prompt(
            g, locale_meta,
            tailor_keywords=tailor_keywords,
            persona=persona_obj,
            level=level_obj,
            company=company_obj,
            max_activities=input_activities,
            char_budget=input_char_budget,
        )
```

- [ ] **Step 3d: Pass from cli enrich command**

In `src/vibe_resume/cli.py`, inside the `enrich` command (defined at line 170), where `emit_jobs(...)` is called, read the cfg values and pass them. Add near the top of the command body (after `cfg = ctx.obj["config"]`):

```python
    _enr = cfg.get("enrich", {})
    _in_acts = int(_enr.get("input_activities", 12))
    _in_chars = int(_enr.get("input_char_budget", 200))
```

and add `input_activities=_in_acts, input_char_budget=_in_chars,` to the `emit_jobs(...)` call's keyword arguments.

- [ ] **Step 3e: Document config keys**

In `config.example.yaml`, under the existing `enrich:` block, add:

```yaml
  input_activities: 12      # how many activities per group feed the LLM prompt
  input_char_budget: 200    # per-activity char budget in the prompt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_enricher.py -k window -v && uv run pytest tests/test_enrich_jobs.py -v`
Expected: PASS (and emit-path tests unaffected by the new defaulted params).

- [ ] **Step 5: Commit**

```bash
git add src/vibe_resume/core/enricher.py src/vibe_resume/core/enrich_jobs.py src/vibe_resume/cli.py config.example.yaml tests/test_enricher.py
git commit -m "feat(enricher): configurable input window (activities + char budget) (#35)"
```

---

# Part C — Release 0.7.0

### Task C1: CHANGELOG, version bump, full verification

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml`, `skills/ai-used-resume/SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `uv.lock`
- Test: `tests/test_skill_spec.py`

- [ ] **Step 1: Find every current version string**

Run: `grep -rn "0\.6\.3" pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json`
Expected: shows each version occurrence (pyproject `version`, SKILL.md `metadata.version`, plugin.json `version`, marketplace.json self-version + plugin entry version, codex plugin.json `version`).

- [ ] **Step 2: Bump all to 0.7.0**

Edit each occurrence `0.6.3` → `0.7.0`. Then refresh the lockfile:

Run: `uv lock`
Expected: `uv.lock` updates the `vibe-resume` package version to 0.7.0.

- [ ] **Step 3: Add CHANGELOG entry**

Prepend a `## [0.7.0] - 2026-05-29` section to `CHANGELOG.md` (Keep-a-Changelog format):

```markdown
## [0.7.0] - 2026-05-29

### Added
- **GitHub PR/issue extractor** (`extractors/local/github.py`, #34): pulls the
  author's PRs/issues + own review-thread comments via `gh` CLI (no token
  handling). Detects owned vs external (open-source) contributions; external
  merged PRs are exempt from the noise filter and framed as "contributed to".
  New `github:` config block (disabled by default).
- `sessions:` config block (`sample_prompts`, `per_prompt_chars`,
  `capture_tool_args`, `keep_assistant`) shared by conversation extractors.
- `enrich.input_activities` / `enrich.input_char_budget` config to widen the
  LLM input window (was hard-coded 12 activities / 200 chars).

### Changed
- git extractor now captures commit **bodies** (`%b`) and touched **file
  paths**, not just subjects (#35).
- claude_code / codex extractors spread-sample prompts across the session
  timeline (deduped) instead of keeping only the first ~8, and can keep a
  sample of tool-call arguments (#35).
- claude.ai export retains assistant responses (#35).

### Fixed
- `PrivacyFilter` now redacts string elements inside `list` values in
  `extra` (review comments / tool args), closing a redaction gap.
```

- [ ] **Step 4: Run the full suite + lint**

Run: `uv run pytest tests/ && uv run ruff check .`
Expected: all tests PASS (including `tests/test_skill_spec.py` version-consistency assertions), ruff clean.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml skills/ai-used-resume/SKILL.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json uv.lock
git commit -m "chore(release): bump version 0.6.3 → 0.7.0"
```

---

## Self-Review

**1. Spec coverage** (against `2026-05-29-github-pr-issue-extractor-design.md`):
- gh CLI transport → A2 (`_gh_json`). ✓
- `@me` default + `author_logins` → A2 (`_resolve_logins`). ✓
- PR title+body+own comments → A2/A3. ✓
- issues → A3. ✓
- ownership owned/external + `owned_owners` → A2/A3. ✓
- basename merge → A5. ✓
- noise-filter exemption for external merged PR → A6. ✓
- enricher "contributed to" framing → A7. ✓
- redaction of review comments → A1 (list[str] redaction) + extra carries `body`/`own_comments`. ✓
- config block + defaults (enabled false, fetch_files false) → A4. ✓
- repos_allow/block, max_age, max_items → A3. ✓
- runner registration → A4. ✓
- error handling (gh missing/non-zero → []) → A2/A3 (`_gh_json` returns None). ✓
- #35 git body+files → B1; sessions sampling → B2/B3/B4; claude.ai assistant → B5; configurable enricher window → B6. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. ✓

**3. Type consistency:**
- `_gh_json(args, timeout=30) -> Any` used identically in A2/A3. ✓
- `Commit` NamedTuple fields (`dt, sha, subject, body, insertions, deletions, files`) used in B1 test + `extract`. ✓ (Note: B1 also fixes the pre-existing `c[0]` bucket-key reference → `c.dt`.)
- `sample_spread(items, k)` signature consistent across B2/B3/B4/B5. ✓
- `_build_prompt(..., max_activities, char_budget)` consistent across B6 enricher + enrich_jobs call. ✓
- `extra` keys (`repo`, `repo_owner`, `contribution`, `merged`, `own_comments`) consistent across A2/A3/A5/A6/A7. ✓

**4. Ordering dependency note:** A1 before A2/A3 (list redaction must exist before own_comments are trusted to be scrubbed). B2 before B3/B4/B5 (`sample_spread`). All other tasks independent within their part.
