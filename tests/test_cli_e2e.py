"""End-to-end smoke tests for the vibe-resume CLI.

Run real subcommands in a temp directory with a minimal fixture
profile + pre-seeded project-groups cache. Catches bugs that unit
tests miss: template rendering regressions, locale script-leak,
review-scorer output shape, CLI wiring, subcommand registration, etc.

Isolation strategy:
- tmp_path is both the working directory AND the CLI's resolved ROOT.
- ROOT resolution: every module reads `VIBE_RESUME_ROOT` env var first,
  falling back to its own `__file__.parent[.parent]` if unset. Tests
  set this env var to tmp_path so all reads/writes stay in the sandbox
  without any pollution of the real repo's data/ directories.
- profile.yaml / config.yaml are fake (Test User, empty scan.roots).
- data/cache/_project_groups.json is pre-seeded so `render` / `review`
  / `trend` work without running extract/aggregate/enrich (which would
  hit $HOME and/or `claude -p`).

Test cost: ~5-15 seconds per test; zero LLM tokens; CI-safe.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
VENV_VIBE_RESUME = REPO_ROOT / ".venv" / "bin" / "vibe-resume"


pytestmark = pytest.mark.skipif(
    not VENV_VIBE_RESUME.exists(),
    reason="Project venv not set up — run `uv venv && uv pip install -e '.[dev]'` first",
)


FIXTURE_PROFILE = {
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+1-555-0100",
    "location": "Remote",
    "target_role": "Software Engineer",
    "summary": (
        "Ships production software using AI-augmented workflows — Claude Code, "
        "Cursor, Copilot — to compress design-to-deploy cycles."
    ),
    "preferred_locale": "en_US",
}

FIXTURE_CONFIG = {
    "scan": {"mode": "whitelist", "roots": []},
    "privacy": {"blocklist": [], "abstract_tech": False},
    "render": {"locale": "en_US", "all_locales_formats": ["md"]},
    "window": {"days": 120},
    "extractors": {},
}

# Real shape: top-level is a LIST of ProjectGroup dicts (core/schema.py:79).
FIXTURE_PROJECT_GROUPS = [
    {
        "name": "sample-project",
        "path": "~/sample",
        "first_activity": "2026-01-01T09:00:00",
        "last_activity": "2026-04-01T18:00:00",
        "total_sessions": 42,
        "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        "sources": ["claude-code", "cursor", "git"],
        "summary": "Shipped a production API with 99.9% uptime.",
        "achievements": [
            "Built REST API serving 10k req/s with FastAPI + PostgreSQL, "
            "cutting p99 latency from 800ms to 120ms.",
            "Instrumented the service with structured logging + distributed "
            "tracing, catching 3 production bugs before users noticed.",
            "Reduced CI time 40% by parallelizing the pytest suite.",
        ],
        "activities": [],
        "category_counts": {"backend": 30, "devops": 8, "bug-fix": 4},
        "capability_breadth": 3,
        "headline": "Backend: 71% backend / 19% DevOps / 10% bug-fix",
        "domain_tags": ["API", "Testing"],
        "metrics": ["p99 latency 800ms → 120ms", "CI time −40%"],
    }
]

# Real shape: dict with window keys (last_30d, last_7d).
FIXTURE_WINDOW_STATS = {
    "last_30d": {
        "window_days": 30,
        "sessions": 20,
        "active_days": 12,
        "active_day_ratio_pct": 40,
        "daily_avg": 0.67,
        "per_active_day_avg": 1.7,
        "peak_day": "2026-04-01",
        "peak_day_sessions": 4,
        "longest_streak_days": 5,
        "projects_touched": 1,
        "top_projects": [{"name": "sample-project", "sessions": 20}],
    },
    "last_7d": {
        "window_days": 7,
        "sessions": 4,
        "active_days": 3,
        "active_day_ratio_pct": 43,
        "daily_avg": 0.57,
        "per_active_day_avg": 1.3,
        "peak_day": "2026-04-01",
        "peak_day_sessions": 2,
        "longest_streak_days": 2,
        "projects_touched": 1,
        "top_projects": [{"name": "sample-project", "sessions": 4}],
    },
}


@pytest.fixture
def vibe_env(tmp_path: Path) -> Path:
    """Minimal vibe-resume project tree inside tmp_path.

    We don't symlink source here — tests run the CLI from the real repo
    path and set VIBE_RESUME_ROOT=tmp_path so all module-level ROOT
    references resolve to the sandbox. Profile, config, and cache go in
    tmp_path at the layout the CLI expects.

    The one piece of the real repo we still need: the jinja2 templates
    under render/templates/. We inject their absolute path into the
    fixture config via `render.templates_dir` so renderer can find them
    without depending on tmp_path having its own copy.
    """
    config = dict(FIXTURE_CONFIG)
    config["render"] = {
        **FIXTURE_CONFIG["render"],
        "templates_dir": str(REPO_ROOT / "render" / "templates"),
    }
    (tmp_path / "profile.yaml").write_text(yaml.dump(FIXTURE_PROFILE))
    (tmp_path / "config.yaml").write_text(yaml.dump(config))

    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    (cache / "_project_groups.json").write_text(json.dumps(FIXTURE_PROJECT_GROUPS))
    (cache / "_window_stats.json").write_text(json.dumps(FIXTURE_WINDOW_STATS))

    (tmp_path / "data" / "resume_history").mkdir(parents=True)
    (tmp_path / "data" / "reviews").mkdir(parents=True)
    (tmp_path / "data" / "imports").mkdir(parents=True)

    return tmp_path


def _run_cli(
    *args: str, cwd: Path, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    """Invoke the CLI with VIBE_RESUME_ROOT pointing at the sandbox.

    cwd is the tmp project dir (so CLI can find profile.yaml/config.yaml
    by relative path), and VIBE_RESUME_ROOT overrides every ROOT-derived
    path inside the CLI (data/resume_history, data/reviews, data/cache)
    so nothing leaks into the real repo.
    """
    env = os.environ.copy()
    env["VIBE_RESUME_ROOT"] = str(cwd)
    return subprocess.run(
        [str(VENV_VIBE_RESUME), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_help_lists_core_subcommands(vibe_env: Path) -> None:
    """Top-level --help lists every pipeline stage."""
    result = _run_cli("--help", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    for sub in ("extract", "aggregate", "enrich", "render", "review", "trend"):
        assert sub in result.stdout, f"--help output missing `{sub}`"


def test_company_list_frontier_ai_tier(vibe_env: Path) -> None:
    """`company list --tier frontier_ai` returns the 10 frontier AI profiles."""
    result = _run_cli("company", "list", "--tier", "frontier_ai", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    for key in ("anthropic", "openai", "google_deepmind", "meta_fair", "nvidia"):
        assert key in result.stdout, f"frontier_ai tier missing `{key}`"
    assert "frontier_ai" in result.stdout
    assert "total profiles" in result.stdout.lower()


def test_company_show_anthropic(vibe_env: Path) -> None:
    """`company show anthropic` prints the profile's keyword_anchors and review_tips."""
    result = _run_cli("company", "show", "anthropic", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    stdout_lower = result.stdout.lower()
    # Profile should carry these fields (from core/profiles/anthropic.yaml)
    assert "anthropic" in stdout_lower
    assert any(k in stdout_lower for k in ("must-have", "must_have", "keyword", "review_tip", "review tip"))


def test_render_en_us_produces_markdown(vibe_env: Path) -> None:
    """`render -f md --locale en_US` writes a non-empty file containing the profile name."""
    result = _run_cli("render", "-f", "md", "--locale", "en_US", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    # en_US is the default — file name has no locale suffix
    rendered = sorted((vibe_env / "data" / "resume_history").glob("resume_v*.md"))
    assert rendered, f"no resume_v*.md produced; stdout:\n{result.stdout}"
    content = rendered[-1].read_text(encoding="utf-8")
    assert "Test User" in content
    assert "sample-project" in content or "Backend Engineer" in content


def test_render_zh_tw_no_simplified_leak(vibe_env: Path) -> None:
    """`render --locale zh_TW` must not emit Simplified-only characters."""
    result = _run_cli("render", "-f", "md", "--locale", "zh_TW", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    rendered = sorted((vibe_env / "data" / "resume_history").glob("resume_v*_zh_TW.md"))
    assert rendered, "no zh_TW resume file produced"
    content = rendered[-1].read_text(encoding="utf-8")

    # Strong Simplified-only characters that zh_TW should never carry
    simplified_only = ["设计", "处理", "实现", "业务", "软件"]
    leaks = [m for m in simplified_only if m in content]
    assert not leaks, f"zh_TW leaked Simplified characters: {leaks}"


def test_render_ja_jp_uses_japan_renderer(vibe_env: Path) -> None:
    """`render -f md --locale ja_JP` succeeds and emits a Japanese file."""
    result = _run_cli("render", "-f", "md", "--locale", "ja_JP", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    rendered = sorted((vibe_env / "data" / "resume_history").glob("resume_v*_ja_JP.md"))
    assert rendered, "no ja_JP resume file produced"
    content = rendered[-1].read_text(encoding="utf-8")
    assert "Test User" in content


def test_review_produces_scorecard(vibe_env: Path) -> None:
    """`review --locale en_US` after render writes a reviews JSON with grade + score."""
    _run_cli("render", "-f", "md", "--locale", "en_US", cwd=vibe_env)

    result = _run_cli("review", "--locale", "en_US", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    # JSON sidecar lets us assert structure
    review_json_files = list((vibe_env / "data" / "reviews").glob("*.json"))
    assert review_json_files, f"review did not write a JSON; stdout:\n{result.stdout}"

    review = json.loads(review_json_files[-1].read_text(encoding="utf-8"))
    assert "grade" in review or "score" in review, f"review JSON missing grade/score: {list(review.keys())}"


def test_list_versions_after_render(vibe_env: Path) -> None:
    """`list-versions` reads the internal git repo and shows the commit made by render."""
    _run_cli("render", "-f", "md", "--locale", "en_US", cwd=vibe_env)

    result = _run_cli("list-versions", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    # Should contain "resume v" and "en_US"
    assert "resume v" in result.stdout
    assert "en_US" in result.stdout


def test_trend_reads_review_history(vibe_env: Path) -> None:
    """`trend` after a render+review cycle prints something about en_US."""
    _run_cli("render", "-f", "md", "--locale", "en_US", cwd=vibe_env)
    _run_cli("review", "--locale", "en_US", cwd=vibe_env)

    result = _run_cli("trend", cwd=vibe_env)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    # Trend may show locales, sparklines, or grades
    sparkline_chars = "▁▂▃▄▅▆▇█"
    assert (
        "en_US" in result.stdout
        or any(c in result.stdout for c in sparkline_chars)
        or any(g in result.stdout for g in ("Grade", "grade", "score"))
    ), f"trend output unexpected:\n{result.stdout}"
