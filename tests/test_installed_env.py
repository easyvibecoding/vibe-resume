import json

import vibe_resume.extractors.local.installed_env as ie


def test_read_plugins(tmp_path, monkeypatch):
    p = tmp_path / "installed_plugins.json"
    p.write_text(json.dumps({"market-a": {"pr-toolkit": {}, "commit": {}},
                             "market-b": {"superpowers": {}}}))
    monkeypatch.setattr(ie, "_PLUGINS_JSON", p)
    assert ie._read_plugins() == ["pr-toolkit", "commit", "superpowers"]


def test_read_plugins_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ie, "_PLUGINS_JSON", tmp_path / "nope.json")
    assert ie._read_plugins() == []


def test_read_skills(tmp_path, monkeypatch):
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "SKILL.md").write_text("x")
    (tmp_path / "bar").mkdir()
    (tmp_path / "bar" / "SKILL.md").write_text("x")
    monkeypatch.setattr(ie, "_SKILLS_DIR", tmp_path)
    assert ie._read_skills() == ["bar", "foo"]


def test_transport_detection():
    assert ie._transport({"command": "npx", "args": ["-y", "x"]}) == "npx"
    assert ie._transport({"command": "/usr/bin/uvx"}) == "uvx"
    assert ie._transport({"url": "http://localhost:1234"}) == "http"
    assert ie._transport({"command": "/opt/bin/myserver"}) == "binary"


def test_read_mcp_servers_names_and_transport_only_no_secrets(tmp_path, monkeypatch):
    cfg = tmp_path / ".claude.json"
    cfg.write_text(json.dumps({"mcpServers": {
        "browser": {"command": "npx", "args": ["-y", "browser-mcp"], "env": {"TOKEN": "sk-secret-xyz"}},
        "db": {"url": "http://localhost:5432/x?password=hunter2"},
    }}))
    monkeypatch.setattr(ie, "_MCP_CONFIG_PATHS", [cfg])
    servers = ie._read_mcp_servers()
    assert servers == [{"name": "browser", "transport": "npx"},
                       {"name": "db", "transport": "http"}]
    blob = json.dumps(servers)
    assert "sk-secret-xyz" not in blob and "hunter2" not in blob
    assert "browser-mcp" not in blob and "args" not in blob and "env" not in blob


def test_extract_builds_one_toolkit_activity(tmp_path, monkeypatch):
    from vibe_resume.core.schema import Source

    plugins = tmp_path / "installed_plugins.json"
    plugins.write_text(json.dumps({"m": {"pr-toolkit": {}}}))
    skills_dir = tmp_path / "skills"
    (skills_dir / "vibe").mkdir(parents=True)
    (skills_dir / "vibe" / "SKILL.md").write_text("x")
    mcp = tmp_path / ".claude.json"
    mcp.write_text(json.dumps({"mcpServers": {"browser": {"command": "npx", "env": {"K": "sk-zzz"}}}}))
    monkeypatch.setattr(ie, "_PLUGINS_JSON", plugins)
    monkeypatch.setattr(ie, "_SKILLS_DIR", skills_dir)
    monkeypatch.setattr(ie, "_MCP_CONFIG_PATHS", [mcp])

    acts = ie.extract({"privacy": {"redact_patterns": ["sk-[A-Za-z0-9]{2,}"]}})
    assert len(acts) == 1
    a = acts[0]
    assert a.source == Source.INSTALLED_ENV
    assert a.project == "Agentic Toolkit"
    assert a.extra["counts"] == {"plugins": 1, "skills": 1, "mcp_servers": 1}
    assert a.extra["plugins"] == ["pr-toolkit"]
    assert a.extra["skills"] == ["vibe"]
    assert a.extra["mcp_servers"] == [{"name": "browser", "transport": "npx"}]
    assert "sk-zzz" not in json.dumps(a.model_dump(mode="json"))


def test_extract_empty_when_nothing_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(ie, "_PLUGINS_JSON", tmp_path / "no.json")
    monkeypatch.setattr(ie, "_SKILLS_DIR", tmp_path / "noskills")
    monkeypatch.setattr(ie, "_MCP_CONFIG_PATHS", [tmp_path / "no.claude.json"])
    assert ie.extract({}) == []
