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
    # "@me" is gh's literal "current authenticated user" alias, not a real
    # owner slug — exclude it from owned_set (we can't verify ownership of a
    # placeholder), so when the login can't be resolved every PR stays external.
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
