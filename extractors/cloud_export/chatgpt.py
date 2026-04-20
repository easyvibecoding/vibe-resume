"""ChatGPT export ZIP importer.

Drop the extracted folder (or the .zip) into data/imports/chatgpt/.
We read conversations.json: an array of records with `mapping` (tree of nodes
with {parent, children, message:{author.role, content.parts, create_time}}).
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from core.schema import Activity, ActivityType, Source

NAME = "chatgpt"


def _find_conversations_json(root: Path) -> Iterator[Path]:
    for p in root.rglob("conversations.json"):
        yield p
    for z in root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(z) as zf:
                if any(n.endswith("conversations.json") for n in zf.namelist()):
                    extract_to = z.parent / z.stem
                    extract_to.mkdir(exist_ok=True)
                    zf.extractall(extract_to)
                    for p in extract_to.rglob("conversations.json"):
                        yield p
        except (zipfile.BadZipFile, OSError):
            continue


def _linearize(mapping: dict) -> list[dict]:
    nodes = []
    for node_id, node in mapping.items():
        msg = node.get("message")
        if not msg:
            continue
        ct = msg.get("create_time")
        if ct is None:
            continue
        role = (msg.get("author") or {}).get("role")
        parts = (msg.get("content") or {}).get("parts") or []
        text = " ".join(str(p) for p in parts if isinstance(p, str))
        nodes.append({"time": ct, "role": role, "text": text})
    nodes.sort(key=lambda n: n["time"])
    return nodes


def _parse_conversation(conv: dict, src_file: Path) -> Activity | None:
    mapping = conv.get("mapping") or {}
    nodes = _linearize(mapping)
    if not nodes:
        return None
    user_nodes = [n for n in nodes if n["role"] == "user"]
    asst_nodes = [n for n in nodes if n["role"] == "assistant"]
    if not user_nodes:
        return None
    start = datetime.fromtimestamp(nodes[0]["time"], tz=timezone.utc)
    end = datetime.fromtimestamp(nodes[-1]["time"], tz=timezone.utc)
    snippet = " | ".join(n["text"][:200] for n in user_nodes[:3])
    return Activity(
        source=Source.CHATGPT,
        session_id=conv.get("conversation_id") or conv.get("id") or src_file.stem,
        timestamp_start=start,
        timestamp_end=end,
        project=conv.get("title") or None,
        activity_type=ActivityType.CHAT,
        user_prompts_count=len(user_nodes),
        tool_calls_count=len(asst_nodes),
        summary=snippet[:500],
        raw_ref=f"{src_file}#{conv.get('conversation_id','')}",
    )


def extract(cfg: dict[str, Any]) -> list[Activity]:
    import_dir = Path(cfg["extractors"]["cloud_chatgpt"]["import_dir"])
    if not import_dir.exists():
        return []
    activities: list[Activity] = []
    for conv_file in _find_conversations_json(import_dir):
        try:
            data = json.loads(conv_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, list):
            continue
        for conv in data:
            if not isinstance(conv, dict):
                continue
            a = _parse_conversation(conv, conv_file)
            if a:
                activities.append(a)
    return activities
