"""Validate SKILL.md files against the agentskills.io open standard.

Spec: https://agentskills.io/specification
Prevents accidentally breaking frontmatter in a way that would fail
`skills-ref validate` across the 35+ compatible agent products.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

CANONICAL_SKILL_DIR = REPO_ROOT / "skills" / "ai-used-resume"

# All host-discovery paths that should resolve to the same canonical SKILL.md.
# Claude Code / Gemini CLI / OpenAI Codex (.agents/) / OpenCode all read from
# their own subdirectory; each is a symlink to `skills/<name>/` per the
# canonical-with-symlinks pattern endorsed by Vercel's `npx skills`, 803's
# skills-supply, and the wider agentskills.io ecosystem.
SKILL_DISCOVERY_PATHS = [
    CANONICAL_SKILL_DIR,
    REPO_ROOT / ".claude" / "skills" / "ai-used-resume",
    REPO_ROOT / ".gemini" / "skills" / "ai-used-resume",
    REPO_ROOT / ".agents" / "skills" / "ai-used-resume",
    REPO_ROOT / ".opencode" / "skills" / "ai-used-resume",
]

SKILL_PATHS = [CANONICAL_SKILL_DIR / "SKILL.md"]

PLUGIN_MANIFESTS = [
    REPO_ROOT / ".claude-plugin" / "plugin.json",
    REPO_ROOT / ".codex-plugin" / "plugin.json",
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


@pytest.mark.parametrize(
    "manifest_path",
    PLUGIN_MANIFESTS,
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_plugin_manifest_has_required_fields(manifest_path: Path) -> None:
    """Claude Code and Codex both require `name`, `version`, `description` in
    their plugin manifest. Keep the two manifests in sync on these fields so
    the plugin identity doesn't fork across ecosystems.
    """
    assert manifest_path.exists(), f"Plugin manifest missing: {manifest_path.relative_to(REPO_ROOT)}"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("name", "version", "description"):
        assert field in data and data[field], (
            f"{manifest_path.relative_to(REPO_ROOT)} missing required field `{field}`"
        )
    assert re.match(r"^\d+\.\d+\.\d+", data["version"]), (
        f"{manifest_path.relative_to(REPO_ROOT)} `version` must be semver: {data['version']!r}"
    )


def test_plugin_manifests_agree_on_identity() -> None:
    """Claude Code and Codex plugin manifests must declare the same plugin
    identity (name + version). Prevents silent drift when bumping one but
    forgetting the other.
    """
    claude = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    codex = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    for field in ("name", "version"):
        assert claude[field] == codex[field], (
            f"Plugin manifests disagree on `{field}`: "
            f"Claude={claude[field]!r} vs Codex={codex[field]!r}"
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


@pytest.mark.parametrize(
    "discovery_path",
    [p for p in SKILL_DISCOVERY_PATHS if p != CANONICAL_SKILL_DIR],
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_host_discovery_paths_resolve_to_canonical(discovery_path: Path) -> None:
    """Every agent-host discovery path (.claude/, .gemini/, .agents/, .opencode/)
    must be a symlink that resolves to the canonical skills/<name>/ directory.
    Prevents accidental directory forks — if someone copies rather than
    symlinks, the content will drift silently.
    """
    assert discovery_path.is_symlink(), (
        f"{discovery_path.relative_to(REPO_ROOT)} must be a symlink to the "
        f"canonical skills/ai-used-resume/ (found a real directory/file)"
    )
    assert discovery_path.resolve() == CANONICAL_SKILL_DIR.resolve(), (
        f"{discovery_path.relative_to(REPO_ROOT)} resolves to "
        f"{discovery_path.resolve()}, expected {CANONICAL_SKILL_DIR.resolve()}"
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
