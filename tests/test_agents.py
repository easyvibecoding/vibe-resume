"""#60 subagent model-tier policy."""
from vibe_resume.core.agents import DEFAULT_SUBAGENT_MODEL, resolve_subagent_model


def test_default_is_sonnet():
    assert resolve_subagent_model({}) == "sonnet" == DEFAULT_SUBAGENT_MODEL
    assert resolve_subagent_model(None) == "sonnet"


def test_precedence_explicit_over_command_over_global():
    cfg = {"agents": {"subagent_model": "haiku"}, "scan": {"subagent_model": "opus"}}
    assert resolve_subagent_model(cfg, command="scan") == "opus"          # per-command wins over global
    assert resolve_subagent_model(cfg, command="enrich") == "haiku"        # falls back to global
    assert resolve_subagent_model(cfg, command="scan", explicit="sonnet") == "sonnet"  # explicit wins


def test_global_only():
    assert resolve_subagent_model({"agents": {"subagent_model": "haiku"}}) == "haiku"


def test_call_claude_passes_model(monkeypatch):
    import vibe_resume.core.enricher as en
    captured = {}
    monkeypatch.setattr(en.shutil, "which", lambda _: "/usr/bin/claude")

    class _R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _R()

    monkeypatch.setattr(en.subprocess, "run", _run)
    en._call_claude("hi", model="sonnet")
    assert "--model" in captured["cmd"] and "sonnet" in captured["cmd"]
    # no model → no --model flag
    en._call_claude("hi")
    assert "--model" not in captured["cmd"]
