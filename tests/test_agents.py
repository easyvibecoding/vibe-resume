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


# --- #61 rate-limit backoff/retry in the subprocess fan-out path -------------

def _fake_run_factory(seq):
    """Return a subprocess.run stub yielding the given (returncode, stdout, stderr) sequence."""
    calls = {"n": 0}

    class _R:
        def __init__(self, rc, out, err):
            self.returncode = rc
            self.stdout = out
            self.stderr = err

    def _run(cmd, **k):
        rc, out, err = seq[min(calls["n"], len(seq) - 1)]
        calls["n"] += 1
        return _R(rc, out, err)

    return _run, calls


def test_call_claude_retries_on_429_then_succeeds(monkeypatch):
    import vibe_resume.core.enricher as en
    monkeypatch.setattr(en.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(en.time, "sleep", lambda *_: None)  # no real waiting
    run, calls = _fake_run_factory([
        (1, "", "Error: 429 rate_limit; retry-after: 1"),
        (1, "", "rate limit exceeded"),
        (0, "done", ""),
    ])
    monkeypatch.setattr(en.subprocess, "run", run)
    assert en._call_claude("p", retries=4) == "done"
    assert calls["n"] == 3   # two 429 retries, then success


def test_call_claude_no_retry_on_non_rate_error(monkeypatch):
    import vibe_resume.core.enricher as en
    monkeypatch.setattr(en.shutil, "which", lambda _: "/usr/bin/claude")
    slept = {"n": 0}
    monkeypatch.setattr(en.time, "sleep", lambda *_: slept.__setitem__("n", slept["n"] + 1))
    run, calls = _fake_run_factory([(1, "", "Error: invalid prompt")])
    monkeypatch.setattr(en.subprocess, "run", run)
    assert en._call_claude("p", retries=4) is None
    assert calls["n"] == 1 and slept["n"] == 0   # no retry, no backoff


def test_fanout_concurrency_constant():
    from vibe_resume.core.agents import FANOUT_CONCURRENCY
    assert 1 <= FANOUT_CONCURRENCY <= 8
