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


def test_resolves_login_from_gh_api_when_unconfigured(monkeypatch):
    """No author_logins in config → resolve via `gh api user`; that real
    login then drives ownership (PR to own repo tagged owned)."""
    def fake_gh(args, timeout=30):
        if args[:2] == ["api", "user"]:
            return "alice"
        if args[:2] == ["search", "prs"]:
            return [_pr(1, "alice", "myapp")]
        return None
    monkeypatch.setattr(gh, "_gh_json", fake_gh)
    acts = gh.extract(_cfg(author_logins=[]))
    assert len(acts) == 1
    assert acts[0].extra["contribution"] == "owned"


def test_unresolvable_login_tags_everything_external(monkeypatch):
    """gh api user fails but search works → fall back to @me, owned_set empty,
    so every PR is conservatively tagged external (ownership unverifiable)."""
    def fake_gh(args, timeout=30):
        if args[:2] == ["api", "user"]:
            return None
        if args[:2] == ["search", "prs"]:
            return [_pr(1, "alice", "myapp")]
        return None
    monkeypatch.setattr(gh, "_gh_json", fake_gh)
    acts = gh.extract(_cfg(author_logins=[]))
    assert len(acts) == 1
    assert acts[0].extra["contribution"] == "external"
