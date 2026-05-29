from click.testing import CliRunner

from vibe_resume.cli import cli
from vibe_resume.core import emphasis as em


def test_emphasis_set_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    runner = CliRunner()
    r = runner.invoke(cli, ["emphasis", "foreground security work"])
    assert r.exit_code == 0, r.output
    assert em.EMPHASIS_PATH.exists()
    assert em.load_emphasis({}).intent == "foreground security work"

    r2 = runner.invoke(cli, ["emphasis", "--clear"])
    assert r2.exit_code == 0, r2.output
    assert not em.EMPHASIS_PATH.exists()


def test_emphasis_show_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "EMPHASIS_PATH", tmp_path / "_emphasis.yaml")
    runner = CliRunner()
    r = runner.invoke(cli, ["emphasis"])
    assert r.exit_code == 0
    assert "no emphasis" in r.output.lower()
