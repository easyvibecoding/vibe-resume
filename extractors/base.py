"""Common extractor helpers."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import orjson

from core.schema import Activity


class ExtractorError(Exception):
    pass


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield parsed JSON objects from a .jsonl file; skip malformed lines."""
    try:
        with open(path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield orjson.loads(line)
                except (orjson.JSONDecodeError, ValueError):
                    try:
                        yield json.loads(line.decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
    except FileNotFoundError:
        return


def save_activities(activities: list[Activity], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = [a.model_dump(mode="json") for a in activities]
    out_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))


def load_activities(path: Path) -> list[Activity]:
    if not path.exists():
        return []
    raw = orjson.loads(path.read_bytes())
    return [Activity(**item) for item in raw]
