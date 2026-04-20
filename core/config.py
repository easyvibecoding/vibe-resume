"""Config loader with path expansion and example-file bootstrap."""
from __future__ import annotations

import os
import shutil
import sys
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


def _bootstrap_from_example(path: Path) -> None:
    """If `path` is missing but `<path>.example` exists, copy it and notify the user.

    The canonical live config is gitignored; the example is the committed template.
    """
    example = path.with_suffix(f".example{path.suffix}")
    if not example.exists():
        raise FileNotFoundError(
            f"Missing {path} and no {example} to bootstrap from. "
            "Clone the repo or see README for the expected layout."
        )
    shutil.copy(example, path)
    print(
        f"[config] bootstrapped {path.name} from {example.name} — "
        f"edit it to tune scan.roots / extractors for your setup",
        file=sys.stderr,
    )


def load_config(path: Path | str = "config.yaml") -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        _bootstrap_from_example(path)
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return _expand(data)
