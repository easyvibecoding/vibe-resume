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
