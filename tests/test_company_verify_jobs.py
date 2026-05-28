"""Tests for `company verify` three-mode flow."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_company_verify_help_lists_emit_ingest_mode():
    r = subprocess.run(
        ["uv", "run", "python", "-m", "vibe_resume", "company", "verify", "--help"],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "--emit" in r.stdout
    assert "--ingest" in r.stdout
    assert "--mode" in r.stdout


def test_company_verify_emit_writes_prompt(tmp_path):
    """--emit dumps prompt.md + manifest.json to data/verification_jobs/<key>_<date>/."""
    from vibe_resume.core.company_profiles import COMPANY_PROFILES
    key = next(iter(COMPANY_PROFILES))

    env = {**os.environ, "VIBE_RESUME_ROOT": str(tmp_path)}
    r = subprocess.run(
        ["uv", "run", "python", "-m", "vibe_resume",
         "company", "verify", "--emit", key],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT, env=env,
    )
    assert r.returncode == 0, r.stderr

    jobs_root = tmp_path / "data" / "verification_jobs"
    assert jobs_root.exists(), f"verification_jobs dir not created; stdout={r.stdout}"
    sub = next(jobs_root.iterdir())
    assert (sub / "prompt.md").exists()
    assert (sub / "manifest.json").exists()
