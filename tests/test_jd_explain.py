"""Tests for `jd-check --explain` gap classification (#80)."""
from datetime import UTC, datetime

from vibe_resume.core.jd_explain import (
    GroundingSnippet,
    KeywordExplanation,
    explain_jd_gaps,
)
from vibe_resume.core.schema import Activity, ProjectGroup, Source


def _act(summary, ref="r1", tech=None, kw=None, source=Source.CLAUDE_CODE):
    return Activity(
        source=source,
        session_id="s1",
        timestamp_start=datetime(2026, 1, 1, tzinfo=UTC),
        summary=summary,
        raw_ref=ref,
        tech_stack=tech or [],
        keywords=kw or [],
    )


def _group(acts, name="proj", tech=None):
    return ProjectGroup(
        name=name,
        first_activity=datetime(2026, 1, 1, tzinfo=UTC),
        last_activity=datetime(2026, 2, 1, tzinfo=UTC),
        total_sessions=len(acts),
        activities=acts,
        tech_stack=tech or [],
    )


def test_surfaced_keyword_has_no_matches():
    g = _group([_act("Built a RAG pipeline", tech=["LlamaIndex"])])
    out = explain_jd_gaps(["LlamaIndex"], [g], surfaced_text="orchestrated a LlamaIndex RAG pipeline")
    assert len(out) == 1
    e = out[0]
    assert e.keyword == "LlamaIndex"
    assert e.status == "surfaced"
    assert e.matches == []


def test_groundable_keyword_has_snippet_and_ref():
    g = _group([
        _act("Deployed the service to Kubernetes with rolling updates", ref="commit:abc",
             source=Source.GIT),
    ])
    out = explain_jd_gaps(["Kubernetes"], [g], surfaced_text="shipped the backend service")
    assert len(out) == 1
    e = out[0]
    assert e.status == "groundable"
    assert e.matches, "expected at least one grounding snippet"
    snip = e.matches[0]
    assert isinstance(snip, GroundingSnippet)
    assert "Kubernetes" in snip.snippet
    assert snip.ref == "commit:abc"
    assert snip.source == Source.GIT.value
    assert len(snip.snippet) <= 90


def test_groundable_via_tech_stack_and_keywords():
    g = _group([_act("Built data layer", tech=["pgvector"], kw=["embeddings"])])
    out = explain_jd_gaps(["pgvector", "embeddings"], [g], surfaced_text="built the data layer")
    by_kw = {e.keyword: e for e in out}
    assert by_kw["pgvector"].status == "groundable"
    assert by_kw["embeddings"].status == "groundable"
    assert all(e.matches for e in out)


def test_absent_keyword_is_honestly_absent():
    g = _group([_act("Built a RAG pipeline", tech=["LlamaIndex"])])
    out = explain_jd_gaps(["Rust"], [g], surfaced_text="built a RAG pipeline")
    assert len(out) == 1
    e = out[0]
    assert e.status == "absent"
    assert e.matches == []


def test_case_insensitive_matching():
    g = _group([_act("Optimized FASTAPI endpoints")])
    out = explain_jd_gaps(["fastapi"], [g], surfaced_text="")
    assert out[0].status == "groundable"


def test_matches_capped_at_three():
    acts = [_act(f"Used Docker in step {i}", ref=f"r{i}") for i in range(6)]
    g = _group(acts)
    out = explain_jd_gaps(["Docker"], [g], surfaced_text="")
    assert out[0].status == "groundable"
    assert len(out[0].matches) == 3


def test_as_dict_shape():
    g = _group([_act("Used Terraform for IaC", ref="commit:z", source=Source.GIT)])
    out = explain_jd_gaps(["Terraform", "Pulumi"], [g], surfaced_text="")
    d = {e.keyword: e.as_dict() for e in out}
    assert d["Terraform"]["status"] == "groundable"
    assert d["Terraform"]["matches"][0]["ref"] == "commit:z"
    assert d["Terraform"]["matches"][0]["source"] == "git"
    assert "snippet" in d["Terraform"]["matches"][0]
    assert d["Pulumi"]["status"] == "absent"
    assert d["Pulumi"]["matches"] == []


def test_explanation_is_dataclass_instance():
    g = _group([_act("hello")])
    out = explain_jd_gaps(["x"], [g], surfaced_text="")
    assert isinstance(out[0], KeywordExplanation)
