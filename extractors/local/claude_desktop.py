"""Claude Desktop: surface MCP config + extension usage; conversations are encrypted."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "claude_desktop"


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["claude_desktop"]["path"])
    if not base.exists():
        return []
    activities: list[Activity] = []

    mcp_cfg = base / "claude_desktop_config.json"
    if mcp_cfg.exists():
        try:
            data = json.loads(mcp_cfg.read_text())
            servers = list((data.get("mcpServers") or {}).keys())
            if servers:
                mtime = datetime.fromtimestamp(mcp_cfg.stat().st_mtime, tz=UTC)
                activities.append(
                    Activity(
                        source=Source.CLAUDE_DESKTOP,
                        session_id="mcp-config",
                        timestamp_start=mtime,
                        timestamp_end=mtime,
                        activity_type=ActivityType.CHAT,
                        keywords=servers,
                        summary=f"Configured {len(servers)} MCP servers: {', '.join(servers[:6])}",
                        raw_ref=str(mcp_cfg),
                        extra={"mcp_servers": servers},
                    )
                )
        except (OSError, json.JSONDecodeError):
            pass

    ext_dir = base / "Claude Extensions"
    if ext_dir.exists():
        exts = [p.name for p in ext_dir.iterdir() if p.is_dir()]
        if exts:
            mtime = datetime.fromtimestamp(ext_dir.stat().st_mtime, tz=UTC)
            activities.append(
                Activity(
                    source=Source.CLAUDE_DESKTOP,
                    session_id="extensions",
                    timestamp_start=mtime,
                    timestamp_end=mtime,
                    activity_type=ActivityType.CHAT,
                    keywords=exts,
                    summary=f"Installed {len(exts)} extensions",
                    raw_ref=str(ext_dir),
                    extra={"extensions": exts},
                )
            )
    return activities
