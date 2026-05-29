from vibe_resume.core.aggregator import (
    _canonical_key,
    _is_meaningful,
    _reconcile_github_projects,
    _reconcile_local_projects,
)
from vibe_resume.core.schema import Activity, ProjectGroup, Source


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
