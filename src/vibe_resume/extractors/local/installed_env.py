"""Inventory the installed/configured agentic toolkit (Claude Code plugins,
standalone Agent Skills, configured MCP servers). Privacy-critical: only
names + coarse transport are captured — never MCP env/args/url values."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vibe_resume.core.privacy import PrivacyFilter
from vibe_resume.core.schema import Activity, ActivityType, Source

NAME = "installed_env"

_CLAUDE_DIR = Path.home() / ".claude"
_PLUGINS_JSON = _CLAUDE_DIR / "plugins" / "installed_plugins.json"
_SKILLS_DIR = _CLAUDE_DIR / "skills"
_MCP_CONFIG_PATHS = [
    Path.home() / ".claude.json",
    _CLAUDE_DIR / "settings.json",
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _read_plugins() -> list[str]:
    data = _load_json(_PLUGINS_JSON)
    names: list[str] = []
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, dict):
                for name in v:
                    if name not in names:
                        names.append(name)
    return names


def _read_skills() -> list[str]:
    if not _SKILLS_DIR.exists():
        return []
    return sorted({p.parent.name for p in _SKILLS_DIR.glob("*/SKILL.md")})


def _transport(server_cfg: dict) -> str:
    if server_cfg.get("url") or server_cfg.get("type") == "http":
        return "http"
    cmd = (server_cfg.get("command") or "").rsplit("/", 1)[-1]
    if cmd == "npx":
        return "npx"
    if cmd == "uvx":
        return "uvx"
    return "binary"


def _read_mcp_servers() -> list[dict]:
    out: dict[str, str] = {}
    for path in _MCP_CONFIG_PATHS:
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            continue
        for name, scfg in servers.items():
            if name not in out and isinstance(scfg, dict):
                out[name] = _transport(scfg)
    return [{"name": n, "transport": t} for n, t in out.items()]
