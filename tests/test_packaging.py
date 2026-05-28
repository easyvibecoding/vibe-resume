"""Guard the wheel-packaging contract: single top-level package (#18)."""
from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_single_top_level_package():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    pkgs = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert pkgs == ["src/vibe_resume"], \
        "wheel must ship exactly one top-level package (src/vibe_resume) to avoid namespace pollution (#18)"


def test_no_force_include_hack():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "force-include" not in wheel, \
        "the 0.5.0 force-include cli.py hack should be gone after the src/ refactor"


def test_entry_point_targets_package():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert data["project"]["scripts"]["vibe-resume"] == "vibe_resume.cli:cli"
