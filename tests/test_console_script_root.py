"""Regression guard for #27 — ROOT must follow CWD, proven by running the CLI
from a working directory that is NOT the repo root."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _seed_config(tmp_path: Path) -> None:
    """Copy config.example.yaml → config.yaml in tmp_path so load_config can start."""
    shutil.copy(REPO_ROOT / "config.example.yaml", tmp_path / "config.yaml")


def test_doctor_reports_cwd_profile_not_repo(tmp_path):
    """Run `doctor` from a tmp cwd containing config.yaml but NO profile.yaml
    (VIBE_RESUME_ROOT unset).

    doctor should report profile.yaml MISSING (tmp_path has none), proving it
    looks in CWD — not in the repo (where profile.yaml may exist),
    and not in site-packages.
    """
    _seed_config(tmp_path)
    env = {k: v for k, v in os.environ.items() if k != "VIBE_RESUME_ROOT"}
    r = subprocess.run(
        ["uv", "run", "python", str(REPO_ROOT / "cli.py"), "doctor"],
        capture_output=True, text=True, timeout=60, cwd=tmp_path, env=env,
    )
    assert r.returncode == 0, r.stderr
    # tmp_path has no profile.yaml → doctor must say so (proves CWD resolution)
    assert "profile.yaml" in r.stdout
    assert "missing" in r.stdout
    # version still readable via importlib.metadata regardless of cwd
    assert "CLI version" in r.stdout or "running from source" in r.stdout


def test_review_diff_uses_cwd_data_dir(tmp_path):
    """review-diff from a cwd with a data/resume_history should look THERE."""
    _seed_config(tmp_path)
    hist = tmp_path / "data" / "resume_history"
    hist.mkdir(parents=True)
    (hist / "resume_v001_en_US.md").write_text(
        "# A\n\n## Summary\nX.\n\n## Experience\n- did things with 30% gain\n"
    )
    (hist / "resume_v002_en_US.md").write_text(
        "# B\n\n## Summary\nY.\n\n## Experience\n- did more with 40% gain\n"
    )

    env = {k: v for k, v in os.environ.items() if k != "VIBE_RESUME_ROOT"}
    r = subprocess.run(
        ["uv", "run", "python", str(REPO_ROOT / "cli.py"), "review-diff", "1", "2"],
        capture_output=True, text=True, timeout=60, cwd=tmp_path, env=env,
    )
    # Should resolve files from tmp_path/data/resume_history, not error out
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "Review diff" in r.stdout or "TOTAL" in r.stdout
