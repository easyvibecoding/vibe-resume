"""Validate SKILL.md files against the agentskills.io open standard.

Spec: https://agentskills.io/specification
Prevents accidentally breaking frontmatter in a way that would fail
`skills-ref validate` across the 35+ compatible agent products.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_PATHS = [
    REPO_ROOT / ".claude" / "skills" / "ai-used-resume" / "SKILL.md",
    REPO_ROOT / "skills" / "ai-used-resume" / "SKILL.md",
]

ALLOWED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---\n"):
        raise AssertionError("SKILL.md must start with YAML frontmatter delimiter '---'")
    _, fm, body = raw.split("---\n", 2)
    return yaml.safe_load(fm), body


@pytest.mark.parametrize("path", SKILL_PATHS, ids=[p.parent.name + "/" + p.parent.parent.name for p in SKILL_PATHS])
def test_skill_md_frontmatter_is_spec_compliant(path: Path) -> None:
    assert path.exists(), f"SKILL.md not found at {path}"

    fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert isinstance(fm, dict), "Frontmatter must be a YAML mapping"

    # Only spec-defined top-level keys are allowed; everything else goes under `metadata`.
    unexpected = set(fm.keys()) - ALLOWED_FRONTMATTER_KEYS
    assert not unexpected, (
        f"Non-standard top-level frontmatter keys {sorted(unexpected)} — "
        f"move them under `metadata:` per agentskills.io spec"
    )

    # name: required, ≤64 chars, lowercase + digits + hyphens, no leading/trailing/consecutive hyphens, matches parent dir.
    name = fm.get("name")
    assert isinstance(name, str) and name, "`name` is required and must be a non-empty string"
    assert len(name) <= 64, f"`name` exceeds 64 chars: {len(name)}"
    assert NAME_RE.match(name), f"`name` must match [a-z0-9-] (no leading/trailing hyphen): {name!r}"
    assert "--" not in name, f"`name` must not contain consecutive hyphens: {name!r}"
    assert name == path.parent.name, (
        f"`name` ({name!r}) must match parent directory name ({path.parent.name!r})"
    )

    # description: required, 1–1024 chars.
    description = fm.get("description")
    assert isinstance(description, str) and description, "`description` is required and must be non-empty"
    assert len(description) <= 1024, f"`description` exceeds 1024 chars: {len(description)}"

    # compatibility: optional, ≤500 chars if present.
    compatibility = fm.get("compatibility")
    if compatibility is not None:
        assert isinstance(compatibility, str), "`compatibility` must be a string"
        assert 1 <= len(compatibility) <= 500, f"`compatibility` must be 1–500 chars: {len(compatibility)}"

    # metadata: optional, must be a mapping.
    metadata = fm.get("metadata")
    if metadata is not None:
        assert isinstance(metadata, dict), "`metadata` must be a YAML mapping"

    # Body must be non-empty markdown.
    assert body.strip(), "SKILL.md body must not be empty after frontmatter"


@pytest.mark.parametrize("path", SKILL_PATHS, ids=[p.parent.name + "/" + p.parent.parent.name for p in SKILL_PATHS])
def test_skill_md_body_under_500_lines(path: Path) -> None:
    """Spec recommends main SKILL.md stays under 500 lines; split to references/ beyond that."""
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    line_count = len(body.splitlines())
    assert line_count <= 500, (
        f"{path.relative_to(REPO_ROOT)} body is {line_count} lines — "
        f"split advanced sections into references/ per agentskills.io spec"
    )


@pytest.mark.parametrize("path", SKILL_PATHS, ids=[p.parent.name + "/" + p.parent.parent.name for p in SKILL_PATHS])
def test_references_dir_follows_spec(path: Path) -> None:
    """If references/ exists, it must be spelled plural (not `reference/`) per spec."""
    skill_dir = path.parent
    singular = skill_dir / "reference"
    plural = skill_dir / "references"
    assert not singular.is_dir() or plural.is_dir(), (
        f"{skill_dir.relative_to(REPO_ROOT)} uses singular `reference/` — "
        f"rename to `references/` per agentskills.io spec"
    )


# Markdown inline link: [text](target) — captures the target in group 1.
# Excludes targets starting with http(s):// or #.
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(((?!https?://|#)[^)]+)\)")


def _skill_markdown_files() -> list[Path]:
    """All markdown files inside each skill directory: SKILL.md + references/*.md."""
    files: list[Path] = []
    for skill_path in SKILL_PATHS:
        skill_dir = skill_path.parent
        files.append(skill_path)
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            files.extend(sorted(refs_dir.glob("*.md")))
    return files


def test_skill_variants_agree_on_identity() -> None:
    """Both SKILL.md variants (.claude/ and skills/) must declare the same
    `name`, `license`, and `compatibility` — these identify the skill to
    downstream marketplaces and host environments. Description may diverge
    (different phrasing for different audiences), but identity must not.
    """
    frontmatters = {p: _split_frontmatter(p.read_text(encoding="utf-8"))[0] for p in SKILL_PATHS}

    for field in ("name", "license", "compatibility"):
        values = {str(path.relative_to(REPO_ROOT)): fm.get(field) for path, fm in frontmatters.items()}
        declared = {v for v in values.values() if v is not None}
        if len(declared) > 1:
            pytest.fail(
                f"SKILL.md variants disagree on `{field}`: {values}. "
                f"Keep identity fields aligned across variants."
            )


@pytest.mark.parametrize(
    "md_path",
    _skill_markdown_files(),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_skill_internal_links_resolve(md_path: Path) -> None:
    """Relative markdown links inside skill docs must resolve to existing files.

    Catches refactors that rename a `references/*.md` file without updating the
    pointer in SKILL.md, or docs that link to a file that never shipped.
    """
    text = md_path.read_text(encoding="utf-8")
    unresolved: list[str] = []
    for target in _MD_LINK_RE.findall(text):
        # Strip any anchor fragment: `references/foo.md#bar` -> `references/foo.md`.
        target_path = target.split("#", 1)[0]
        if not target_path:
            continue
        resolved = (md_path.parent / target_path).resolve()
        if not resolved.exists():
            unresolved.append(target)

    assert not unresolved, (
        f"{md_path.relative_to(REPO_ROOT)} has broken relative link(s): {unresolved}"
    )
