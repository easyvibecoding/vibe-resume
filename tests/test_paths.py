"""core.paths — user-data vs package-resource separation (#27 regression guard)."""
from __future__ import annotations

from pathlib import Path


def test_user_root_follows_cwd_when_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VIBE_RESUME_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    from core.paths import user_root
    assert user_root() == tmp_path


def test_user_root_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBE_RESUME_ROOT", str(tmp_path))
    from core.paths import user_root
    assert user_root() == tmp_path


def test_user_root_not_derived_from_file(tmp_path, monkeypatch):
    """The whole point of #27: user_root must NOT be the install dir."""
    import core.paths as paths
    monkeypatch.delenv("VIBE_RESUME_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    # user_root is tmp_path (cwd), definitely not the dir containing paths.py
    assert paths.user_root() != Path(paths.__file__).parent
    assert paths.user_root() == tmp_path
