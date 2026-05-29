"""#59 codebase scan — deterministic gather/slice/grounding (model step delegated)."""
import re

from vibe_resume.core.codebase_scan import (
    CodebaseGrounding,
    coerce_grounding,
    gather_slice,
    load_scan,
    render_scan_prompt,
    save_scan,
)


def _repo(tmp_path):
    (tmp_path / "README.md").write_text(
        "MyApp does X.\nAPI_KEY=sk-supersecret123\nBuilt by Jeff Hsu.\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"myapp","dependencies":{"react":"19"}}', encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("noise" * 5000, encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pyproject.toml").write_text("[project]\nname='x'", encoding="utf-8")
    return tmp_path


def test_gather_collects_readme_manifests_skips_vendored(tmp_path):
    sl = gather_slice(_repo(tmp_path), group="myapp")
    names = {f["name"] for f in sl.files}
    assert "README.md" in names and "package.json" in names
    assert "pyproject.toml" in names           # one level down
    assert "node_modules/" not in sl.tree and ".git/" not in sl.tree  # vendored/hidden skipped


def test_gather_scrubs_secrets_and_redacts(tmp_path):
    rx = [re.compile(r"Jeff Hsu")]
    sl = gather_slice(_repo(tmp_path), redactors=rx, group="myapp")
    readme = next(f["text"] for f in sl.files if f["name"] == "README.md")
    assert "sk-supersecret123" not in readme
    assert "[REDACTED-SECRET]" in readme
    assert "Jeff Hsu" not in readme and "[REDACTED]" in readme
    assert "MyApp does X." in readme           # real content kept


def test_gather_missing_path_returns_none(tmp_path):
    assert gather_slice(tmp_path / "nope", group="x") is None


def test_render_prompt_has_schema_and_truth_rule(tmp_path):
    p = render_scan_prompt(gather_slice(_repo(tmp_path), group="myapp"))
    assert "concrete_features" in p and "confirmed_tech" in p and "entrypoints" in p
    assert "only what" in p.lower() and "couldn't determine" in p.lower()


def test_grounding_roundtrip(tmp_path):
    g = coerce_grounding("myapp", {"purpose": "does X", "concrete_features": ["a", "b"],
                                   "confirmed_tech": ["React"], "entrypoints": ["cli"]})
    cache = tmp_path / "scan.json"
    save_scan({"myapp": g}, cache)
    loaded = load_scan(cache)
    assert loaded["myapp"].purpose == "does X"
    assert loaded["myapp"].concrete_features == ["a", "b"]


def test_coerce_drops_bad_types():
    g = coerce_grounding("x", {"purpose": 123, "concrete_features": "notalist"})
    assert g.purpose == "123" and g.concrete_features == []


def _grp(name, path=None):
    from datetime import UTC, datetime

    from vibe_resume.core.schema import ProjectGroup
    return ProjectGroup(name=name, path=str(path) if path else None,
                        first_activity=datetime(2026, 1, 1, tzinfo=UTC),
                        last_activity=datetime(2026, 2, 1, tzinfo=UTC), total_sessions=3)


def test_emit_skips_pathless_then_ingest_roundtrip(tmp_path, monkeypatch):
    from vibe_resume.core import codebase_scan as cs
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("Does X.", encoding="utf-8")
    jobs = tmp_path / "scan_jobs"
    groups = [_grp("withpath", repo), _grp("nopath", None)]
    _d, emitted, skipped = cs.emit_scan_jobs(groups, jobs)
    assert emitted == 1 and skipped == 1
    prompt = next(jobs.glob("*.scan.prompt.md"))
    prompt.with_name(prompt.name.replace(".prompt.md", ".yaml")).write_text(
        "purpose: does X\nconcrete_features: [a]\nconfirmed_tech: [Python]\nentrypoints: []\n",
        encoding="utf-8")
    captured = {}
    monkeypatch.setattr(cs, "save_scan", lambda g, *a, **k: captured.update(g))
    n, warnings = cs.ingest_scan(jobs)
    assert n == 1 and not warnings
    assert captured["withpath"].purpose == "does X"
    assert captured["withpath"].confirmed_tech == ["Python"]


def test_enrich_injects_codebase_grounding(monkeypatch):
    from vibe_resume.core import codebase_scan as cs
    from vibe_resume.core.enricher import _build_prompt
    monkeypatch.setattr(cs, "load_scan", lambda *a, **k: {
        "myapp": CodebaseGrounding(group="myapp", purpose="runs X",
                                   concrete_features=["feat A"], confirmed_tech=["FastAPI"])
    })
    p = _build_prompt(_grp("myapp"))
    assert "CODEBASE GROUNDING" in p
    assert "runs X" in p and "feat A" in p and "FastAPI" in p


def test_enrich_no_grounding_no_block(monkeypatch):
    from vibe_resume.core import codebase_scan as cs
    from vibe_resume.core.enricher import _build_prompt
    monkeypatch.setattr(cs, "load_scan", lambda *a, **k: {})
    assert "CODEBASE GROUNDING" not in _build_prompt(_grp("other"))
