"""Per-locale template capability disclosure (#65).

Locale templates differ in what they render — notably, only the base
(`resume.md.j2`, en_US family) renders a `g.metrics` / Impact line. Setting
`profile.project_metrics` for a locale whose template doesn't render them is a
silent no-op. This module discloses the capability matrix (surfaced by `doctor`)
and lets `render` warn on a no-op `project_metrics` config.
"""
from __future__ import annotations

from pathlib import Path

from vibe_resume.render.i18n import LOCALES

_TEMPLATES = Path(__file__).parent / "templates"

# capability -> a marker substring that, if present in the template, means the
# template renders that capability.
_MARKERS = {
    "metrics": "g.metrics",
    "photo": "photo_path",
}


def template_for(locale_key: str) -> Path:
    """Mirror renderer._pick_template: prefer resume.<locale>.md.j2, else the base."""
    specific = _TEMPLATES / f"resume.{locale_key}.md.j2"
    return specific if specific.exists() else _TEMPLATES / "resume.md.j2"


def capabilities(locale_key: str) -> set[str]:
    try:
        text = template_for(locale_key).read_text(encoding="utf-8")
    except OSError:
        return set()
    return {cap for cap, marker in _MARKERS.items() if marker in text}


def renders_metrics(locale_key: str) -> bool:
    return "metrics" in capabilities(locale_key)


def capability_matrix(locales: list[str] | None = None) -> dict[str, set[str]]:
    keys = locales if locales is not None else list(LOCALES)
    return {k: capabilities(k) for k in keys}
