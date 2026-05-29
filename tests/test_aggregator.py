from vibe_resume.core.aggregator import (
    _agentic_signals,
    _canonical_key,
    _is_meaningful,
    _mcp_server,
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


def test_reconcile_rep_prefers_meaningful_leaf_over_version_folder():
    # #39: a plugin-cache copy whose leaf is a version folder must NOT become
    # the representative (and thus the display name) over a real working dir.
    acts = [
        _act(Source.GIT, "/Users/me/dev/foo", remote="github.com/acme/foo",
             toplevel="/Users/me/dev/foo", sid="a"),
        # cache copy with MORE sessions but a version-like leaf under /.cache/
        _act(Source.CODEX, "/Users/me/.cache/tool/foo/0.2.0", remote="github.com/acme/foo",
             toplevel="/Users/me/.cache/tool/foo/0.2.0", sid="b"),
        _act(Source.CODEX, "/Users/me/.cache/tool/foo/0.2.0", remote="github.com/acme/foo",
             toplevel="/Users/me/.cache/tool/foo/0.2.0", sid="c"),
    ]
    prov = _reconcile_local_projects(acts)
    rep = acts[0].project
    assert rep.rstrip("/").split("/")[-1] == "foo"   # meaningful leaf wins over "0.2.0"
    assert prov[rep]["name_hint"] is None             # rep already meaningful


def test_reconcile_name_hint_from_remote_when_all_leaves_bad():
    acts = [
        _act(Source.GIT, "/a/0.2.0", remote="github.com/acme/foo", toplevel="/a/0.2.0", sid="a"),
        _act(Source.CODEX, "/b/0.3.0", remote="github.com/acme/foo", toplevel="/b/0.3.0", sid="b"),
    ]
    prov = _reconcile_local_projects(acts)
    rep = acts[0].project
    assert prov[rep]["name_hint"] == "foo"            # derived from remote basename


def test_mcp_server_extraction():
    assert _mcp_server("mcp__browser__click") == "browser"
    assert _mcp_server("mcp__db__query") == "db"
    assert _mcp_server("Edit") is None
    assert _mcp_server("mcp__only") is None


def _act_sig(files=None, tool_hist=None, keywords=None, skills_used=None):
    extra = {}
    if tool_hist is not None:
        extra["tool_histogram"] = tool_hist
    if skills_used is not None:
        extra["skills_used"] = skills_used
    return Activity(source=Source.CLAUDE_CODE, session_id="s",
                    timestamp_start="2026-01-01T00:00:00+00:00",
                    files_touched=files or [], keywords=keywords or [], extra=extra)


def test_agentic_signals_authored_published_and_mcp_used():
    acts = [_act_sig(files=["skills/foo/SKILL.md", ".claude-plugin/plugin.json"],
                     tool_hist={"mcp__browser__click": 3, "mcp__db__query": 1, "Edit": 5})]
    sig = _agentic_signals(acts, "myrepo")
    assert sig.skills_authored == ["foo"]
    assert sig.skills_published is True
    assert sig.mcp_servers_used == ["browser", "db"]


def test_agentic_signals_skills_used_union_and_mcp_authored():
    acts = [_act_sig(skills_used=["a"]),
            _act_sig(skills_used=["b", "a"], files=["src/foo_mcp_server.py"])]
    sig = _agentic_signals(acts, "r")
    assert sig.skills_used == ["a", "b"]
    assert sig.mcp_authored is True


def test_agentic_signals_none_when_empty():
    assert _agentic_signals([_act_sig(files=["src/main.py"])], "r") is None


def _act_blob(summary="", files=None):
    return Activity(source=Source.CLAUDE_CODE, session_id="s",
                    timestamp_start="2026-01-01T00:00:00+00:00",
                    summary=summary, files_touched=files or [], extra={})


def test_agentic_signals_sdd_from_keyword_and_artifact():
    assert _agentic_signals([_act_blob(summary="drove this with OpenSpec")], "r").sdd is True
    assert _agentic_signals([_act_blob(files=["specs/auth/spec.md"])], "r").sdd is True
    assert _agentic_signals([_act_blob(summary="規格驅動")], "r").sdd is True


def test_agentic_signals_tdd_from_keyword():
    assert _agentic_signals([_act_blob(summary="strict test-driven, failing test first")], "r").tdd is True
    assert _agentic_signals([_act_blob(summary="red-green-refactor loop")], "r").tdd is True


def test_agentic_signals_sdd_tdd_false_for_plain_group():
    sig = _agentic_signals([_act_blob(summary="added a fastapi endpoint", files=["src/api.py"])], "r")
    assert sig is None   # no agentic signal at all → None


def test_agentic_signals_only_sdd_still_builds():
    sig = _agentic_signals([_act_blob(summary="openspec planning")], "r")
    assert sig is not None and sig.sdd is True and sig.tdd is False


def test_orchestration_from_blob_and_skills():
    assert _agentic_signals([_act_blob(summary="used a sub-agent for X")], "r").orchestration == ["subagents"]
    assert _agentic_signals([_act_sig(skills_used=["dispatching-parallel-agents"])], "r").orchestration == ["fan-out"]
    assert _agentic_signals([_act_blob(summary="adversarial verify with a judge panel")], "r").orchestration == ["verify-pipeline"]
    assert _agentic_signals([_act_blob(summary="built a workflow script, self-pacing")], "r").orchestration == ["workflow-script"]
    assert _agentic_signals([_act_blob(summary="used the Agent SDK")], "r").orchestration == ["agent-sdk"]


def test_orchestration_stable_order_and_distinct():
    sig = _agentic_signals(
        [_act_blob(summary="agent sdk fan-out supervisor worker; adversarial verify; sub-agent")], "r")
    assert sig.orchestration == ["subagents", "fan-out", "supervisor-worker", "verify-pipeline", "agent-sdk"]


def test_orchestration_absent_for_single_agent():
    assert _agentic_signals([_act_blob(summary="prompted the model to write code", files=["a.py"])], "r") is None


def test_installed_env_group_survives_noise_filter():
    act = Activity(source=Source.INSTALLED_ENV, session_id="installed-toolkit",
                   timestamp_start="2026-01-01T00:00:00+00:00", project="Agentic Toolkit")
    g = _grp("Agentic Toolkit", [act])   # 1 session, breadth 0
    assert _is_meaningful("agentic toolkit", g, min_sessions=2) is True
