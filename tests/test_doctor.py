"""`vibe-resume doctor` diagnostic command (#19)."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_doctor_runs_and_reports_cli_version():
    r = subprocess.run(
        ["uv", "run", "python", "-m", "vibe_resume", "doctor"],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "CLI version" in r.stdout
    assert "plugin version" in r.stdout.lower() or "plugin.json" in r.stdout.lower()


def test_doctor_in_help():
    r = subprocess.run(
        ["uv", "run", "python", "-m", "vibe_resume", "--help"],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert "doctor" in r.stdout
