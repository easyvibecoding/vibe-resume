"""Extract Cursor chat data from globalStorage + workspaceStorage SQLite.

Cursor stores conversations under key `workbench.panel.aichat.view.aichat.chatdata`
as JSON: {"tabs":[{"tabId":..., "bubbles":[...]}]}. Bubbles with type=="user"
are user prompts; type=="assistant" are model responses.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schema import Activity, ActivityType, Source

NAME = "cursor"

CHAT_KEYS = [
    "workbench.panel.aichat.view.aichat.chatdata",
    "composer.composerData",
    "aiService.prompts",
]


def _read_value(db_path: Path, key: str) -> Any | None:
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None
    try:
        row = con.execute("SELECT value FROM ItemTable WHERE key=?", (key,)).fetchone()
    except sqlite3.Error:
        con.close()
        return None
    con.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_tab(tab: dict, src_file: Path) -> Activity | None:
    bubbles = tab.get("bubbles") or []
    if not bubbles:
        return None
    user_count = sum(1 for b in bubbles if b.get("type") == "user")
    assistant_count = sum(1 for b in bubbles if b.get("type") == "assistant")
    if user_count == 0 and assistant_count == 0:
        return None

    # Cursor doesn't reliably store per-bubble timestamps in older schemas.
    # Fall back to file mtime.
    ts_fallback = datetime.fromtimestamp(src_file.stat().st_mtime, tz=timezone.utc)

    texts = []
    for b in bubbles[:8]:
        if b.get("type") == "user":
            t = b.get("text") or b.get("content") or ""
            if isinstance(t, str) and t.strip():
                texts.append(t.strip()[:200])

    return Activity(
        source=Source.CURSOR,
        session_id=tab.get("tabId") or src_file.stem,
        timestamp_start=ts_fallback,
        timestamp_end=ts_fallback,
        project=tab.get("chatTitle") or None,
        activity_type=ActivityType.CODING,
        summary=" | ".join(texts)[:500],
        user_prompts_count=user_count,
        tool_calls_count=assistant_count,
        raw_ref=str(src_file),
    )


def _extract_chatdata(chatdata: Any, src_file: Path) -> list[Activity]:
    if not isinstance(chatdata, dict):
        return []
    tabs = chatdata.get("tabs") or []
    out: list[Activity] = []
    for tab in tabs:
        a = _parse_tab(tab, src_file)
        if a:
            out.append(a)
    return out


def extract(cfg: dict[str, Any]) -> list[Activity]:
    base = Path(cfg["extractors"]["cursor"]["path"])
    if not base.exists():
        return []

    dbs: list[Path] = []
    g = base / "globalStorage" / "state.vscdb"
    if g.exists():
        dbs.append(g)
    ws_root = base / "workspaceStorage"
    if ws_root.exists():
        dbs.extend(ws_root.glob("*/state.vscdb"))

    activities: list[Activity] = []
    for db in dbs:
        for key in CHAT_KEYS:
            val = _read_value(db, key)
            if not val:
                continue
            if key.endswith("chatdata"):
                activities.extend(_extract_chatdata(val, db))
            elif key == "composer.composerData":
                # newer composer data: {"composers":[{"id":..,"name":..,"messages":[...]}]}
                composers = val.get("composers") if isinstance(val, dict) else None
                if not composers:
                    continue
                for c in composers:
                    msgs = c.get("messages") or []
                    if not msgs:
                        continue
                    ts_fallback = datetime.fromtimestamp(db.stat().st_mtime, tz=timezone.utc)
                    user_n = sum(1 for m in msgs if m.get("role") == "user")
                    asst_n = sum(1 for m in msgs if m.get("role") == "assistant")
                    if user_n + asst_n == 0:
                        continue
                    activities.append(
                        Activity(
                            source=Source.CURSOR,
                            session_id=c.get("id") or db.parent.name,
                            timestamp_start=ts_fallback,
                            timestamp_end=ts_fallback,
                            project=c.get("name"),
                            activity_type=ActivityType.CODING,
                            user_prompts_count=user_n,
                            tool_calls_count=asst_n,
                            summary=(c.get("name") or "")[:200],
                            raw_ref=f"{db}#composers/{c.get('id','')}",
                        )
                    )
    return activities
