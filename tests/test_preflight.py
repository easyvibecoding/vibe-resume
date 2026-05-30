"""#64 PDF-engine preflight + per-stage freshness disclosure."""
from datetime import UTC, datetime, timedelta

import vibe_resume.core.preflight as pf
from vibe_resume.core.preflight import freshness_verdict, pdf_engine_status, stage_freshness


def test_pdf_engine_on_path(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: f"/usr/bin/{n}")
    ok, msg = pdf_engine_status()
    assert ok and "on PATH" in msg


def test_pdf_engine_no_pandoc(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: None)
    monkeypatch.setattr(pf, "_find_xelatex_offpath", lambda: None)
    ok, msg = pdf_engine_status()
    assert not ok and "pandoc not found" in msg


def test_pdf_engine_offpath_discloses_fix(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: "/usr/bin/pandoc" if n == "pandoc" else None)
    monkeypatch.setattr(pf, "_find_xelatex_offpath", lambda: "/Library/TeX/texbin")
    ok, msg = pdf_engine_status()
    assert not ok
    assert "/Library/TeX/texbin" in msg and "PATH=" in msg  # exact fix disclosed


def test_stage_freshness_and_verdict(tmp_path):
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    hist = tmp_path / "data" / "resume_history"
    hist.mkdir(parents=True)
    (cache / "claude_code.json").write_text("[]", encoding="utf-8")
    (cache / "_project_groups.json").write_text("[]", encoding="utf-8")
    (cache / "_project_groups.default.en_US.json").write_text("[]", encoding="utf-8")
    (hist / "resume_v001_en_US.md").write_text("# x", encoding="utf-8")
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
    stages = stage_freshness(tmp_path, now=now)
    names = [s["stage"] for s in stages]
    assert names == ["extract", "aggregate", "enrich", "render"]
    assert all(s["mtime"] is not None for s in stages)  # all four present
    # enrich newer-or-equal to aggregate → reuse verdict
    assert "reuse" in freshness_verdict(stages) or "newer" in freshness_verdict(stages)


def test_freshness_verdict_stale_enrich():
    now = datetime(2026, 5, 30, tzinfo=UTC)
    stages = [
        {"stage": "aggregate", "mtime": now, "age": "now", "file": "a"},
        {"stage": "enrich", "mtime": now - timedelta(hours=2), "age": "2h", "file": "e"},
    ]
    assert "OLDER" in freshness_verdict(stages)
