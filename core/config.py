"""Config loader with path expansion."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _expand(obj: Any) -> Any:
    if isinstance(obj, str):
        if obj.startswith("~") or "$" in obj:
            return os.path.expandvars(os.path.expanduser(obj))
        return obj
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    return obj


def load_config(path: Path | str = "config.yaml") -> dict[str, Any]:
    path = Path(path)
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return _expand(data)
