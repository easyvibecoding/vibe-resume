from vibe_resume.core.aggregator import _is_meaningful, _reconcile_github_projects
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
