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
from datetime import UTC, datetime, timedelta
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
    seen: set[str] = set()
    out: list[str] = []
    for ep in endpoints:
        data = _gh_json(["api", ep])
        for c in data or []:
            user = (c.get("user") or {}).get("login")
            body = c.get("body")
            if user in logins and isinstance(body, str) and body.strip():
                if body not in seen:
                    seen.add(body)
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


def extract(cfg: dict[str, Any]) -> list[Activity]:
    sub = cfg["extractors"]["github"]
    logins = _resolve_logins(sub)
    # "@me" is gh's literal "current authenticated user" alias, not a real
    # owner slug — exclude it from owned_set (we can't verify ownership of a
    # placeholder), so when the login can't be resolved every PR stays external.
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
