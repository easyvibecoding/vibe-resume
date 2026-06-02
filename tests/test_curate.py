import yaml as _yaml

from vibe_resume.core.curate import (
    DEFAULT_NOISE_GLOBS,
    CurationEntry,
    CurationRecord,
    classify,
    emit_curation,
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


def test_emit_writes_yaml_and_carries_forward_human_action(tmp_path):
    groups = [
        _g("CRM", path="/work/CRM", sessions=10),
        _g("CRM-copy", path="/test/CRM", sessions=3),
    ]
    out = tmp_path / "_curation.yaml"
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


def test_apply_drop_merge_keep():
    from vibe_resume.core.curate import apply_curation

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
    from vibe_resume.core.curate import apply_curation, headless_record

    crm = _g("CRM", path="/work/CRM", sessions=10)
    tmp = _g("scratch", path="/Users/me/tmp/scratch", sessions=1)
    record = headless_record([crm, tmp], DEFAULT_NOISE_GLOBS)
    out = apply_curation([crm, tmp], record)
    assert {g.name for g in out} == {"CRM"}       # noise auto-dropped, no merge_into


def test_classify_needs_decision_same_name_no_remote_twin():
    # #40: a no-remote copy that shares its NAME with a keyed twin must still
    # surface as needs_decision → merge_into the keyed twin (self-exclude by
    # identity, not name).
    keyed = _g("X", path="/work/X", sessions=10, canonical_key="remote:github.com/acme/x",
               merged_from=["/work/X"])
    nokey = _g("X", path="/notes/X", sessions=3)   # same name, no remote
    entries = classify([keyed, nokey], DEFAULT_NOISE_GLOBS)
    nokey_entry = next(e for e in entries if e.sessions == 3)
    keyed_entry = next(e for e in entries if e.sessions == 10)
    assert nokey_entry.tier == "needs_decision"
    assert nokey_entry.action == "merge_into"
    assert nokey_entry.target == "X"             # folds into the keyed twin
    assert keyed_entry.tier in ("keep", "auto_merge")   # keyed anchor is NOT flagged


def _g_acts(name, path, sessions, canonical_key=None):
    from vibe_resume.core.schema import Activity, Source
    acts = [Activity(source=Source.GIT, session_id=f"{name}-{i}",
                     timestamp_start="2026-01-01T00:00:00+00:00", project=path)
            for i in range(sessions)]
    return ProjectGroup(name=name, path=path,
                        first_activity="2026-01-01T00:00:00+00:00",
                        last_activity="2026-01-01T00:00:00+00:00",
                        total_sessions=sessions, canonical_key=canonical_key,
                        activities=acts)


def test_apply_same_name_merge_keeps_one_no_data_loss():
    # #41: applying a needs_decision merge of a same-named twin must keep the
    # canonical group (carrying both groups' activities), not drop both.
    from vibe_resume.core.curate import apply_curation

    keyed = _g_acts("X", "/work/X", 10, canonical_key="remote:github.com/acme/x")
    nokey = _g_acts("X", "/notes/X", 3)
    groups = [keyed, nokey]
    record = CurationRecord(version=1, generated_at="t", groups=[
        CurationEntry(name="X", canonical_key="remote:github.com/acme/x", sessions=10,
                      tier="keep", action="keep"),
        CurationEntry(name="X", sessions=3, tier="needs_decision",
                      action="merge_into", target="X"),
    ])
    out = apply_curation(groups, record)
    assert len(out) == 1                       # exactly one X survives (no data loss)
    assert out[0].canonical_key == "remote:github.com/acme/x"   # the keyed twin is the anchor
    assert out[0].total_sessions == 13         # both groups' activities unioned


# ---- #87: honor `action` (not tier); add agent-friendly CLI verbs -----------


def test_load_prior_survives_custom_tier_and_honors_action(tmp_path):
    """#87: a human edit setting `action: drop` with a non-standard `tier`
    (e.g. manual_drop) must NOT fail validation and silently fall back to the
    auto-only record — the action is the operative field."""
    from vibe_resume.core.curate import _load_prior
    y = tmp_path / "_curation.yaml"
    y.write_text(
        "version: 1\ngenerated_at: t\ngroups:\n"
        "- {name: noise, sessions: 1, tier: manual_drop, action: drop}\n"
        "- {name: keepme, sessions: 9, tier: keep, action: keep}\n"
    )
    rec = _load_prior(y)
    assert rec is not None, "custom tier must not nuke the whole load"
    by_name = {e.name: e for e in rec.groups}
    assert by_name["noise"].action == "drop"      # honored, not downgraded


def test_set_action_helper_drop_merge_keep():
    """#87: programmatic verbs so agents don't hand-edit YAML."""
    from vibe_resume.core.curate import set_action
    rec = CurationRecord(version=1, generated_at="t", groups=[
        CurationEntry(name="A", sessions=5, tier="needs_decision", action="keep"),
        CurationEntry(name="B", sessions=3, tier="keep", action="keep"),
    ])
    assert set_action(rec, "A", "drop") is True
    assert next(e for e in rec.groups if e.name == "A").action == "drop"
    assert set_action(rec, "B", "merge_into", target="A") is True
    eb = next(e for e in rec.groups if e.name == "B")
    assert eb.action == "merge_into" and eb.target == "A"
    assert set_action(rec, "ghost", "drop") is False   # unknown name → no-op, reported
