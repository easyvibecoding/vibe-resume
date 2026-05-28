"""Guard the wheel-packaging contract so `uv tool install` keeps working (#18)."""
from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_module_is_force_included_in_wheel():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    force = wheel.get("force-include", {})
    assert force.get("cli.py") == "cli.py", \
        "cli.py must be force-included in the wheel or `uv tool install` breaks (#18)"


def test_entry_point_targets_cli():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert data["project"]["scripts"]["vibe-resume"] == "cli:cli"
