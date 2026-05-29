from vibe_resume.core.curate import (
    DEFAULT_NOISE_GLOBS,
    CurationEntry,
    CurationRecord,
    classify,
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
