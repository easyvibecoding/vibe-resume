"""Opt-in codebase scan per project (#59) — ground bullets in what the code does.

Activity signals say *what the user did*; the codebase says *what the project
is*. This gathers a **bounded, redacted** slice of each group's real repo
(README, manifests, entry points, top-level tree), emits a per-project prompt
for a cheaper-model subagent in the session to summarize, and ingests structured
`{purpose, concrete_features[], confirmed_tech[], entrypoints[]}` grounding that
enrich consumes.

The CLI does the deterministic, testable part (file gathering + secret/vendor
filtering + redaction). The model step is delegated to the session (emit →
process → ingest), mirroring enrich — so it's host-portable and naturally runs
on a cheap model / parallel subagents.

Truth + privacy (P1/#51): describe ONLY what the code shows ("couldn't
determine" is valid); summarize locally, never upload; drop secret-bearing lines;
run through profile redactors; honor `privacy.blocklist`; skip vendored/build/
generated dirs; a missing/unreadable path silently yields no scan.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import orjson

from vibe_resume.core.paths import user_root

_ROOT = user_root()
SCAN_CACHE = _ROOT / "data" / "cache" / "_codebase_scan.json"

SKIP_DIRS = {
    "node_modules", ".venv", "venv", "env", "dist", "build", ".git", "__pycache__",
    ".next", ".nuxt", "target", "vendor", ".cache", "coverage", ".pytest_cache",
    "site-packages", ".tox", ".mypy_cache", ".ruff_cache", "out", "bin", "obj",
}
MANIFESTS = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "Gemfile", "requirements.txt",
    "composer.json", "pubspec.yaml", "Makefile", "Dockerfile",
}
_README_RE = re.compile(r"^readme(\.[a-z]+)?$", re.IGNORECASE)
# lines whose content is secret-bearing — dropped before the slice is emitted
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|passwd|password|client[_-]?secret|"
    r"connection[_-]?string|bearer\s+[a-z0-9._-]+|aws_[a-z_]+|private[_-]?key|"
    r"-----BEGIN)"
)

MAX_FILES = 24
MAX_BYTES = 60_000
MAX_FILE_BYTES = 12_000


@dataclass
class CodebaseSlice:
    group: str
    path: str
    files: list[dict[str, str]] = field(default_factory=list)  # {name, text}
    tree: list[str] = field(default_factory=list)
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _scrub_secrets(text: str) -> str:
    return "\n".join(
        "[REDACTED-SECRET]" if _SECRET_RE.search(ln) else ln
        for ln in text.splitlines()
    )


def _redact(text: str, redactors: list[re.Pattern[str]] | None) -> str:
    text = _scrub_secrets(text)
    for rx in redactors or []:
        text = rx.sub("[REDACTED]", text)
    return text


def gather_slice(
    path: str | Path,
    redactors: list[re.Pattern[str]] | None = None,
    *,
    group: str = "",
    max_files: int = MAX_FILES,
    max_bytes: int = MAX_BYTES,
) -> CodebaseSlice | None:
    """Read a bounded, redacted slice of a repo. Returns None for a missing path
    (extractor contract: never invent)."""
    p = Path(path).expanduser()
    if not p.is_dir():
        return None

    sl = CodebaseSlice(group=group, path=str(p))
    # top-level tree (skip vendored/build/hidden noise)
    try:
        entries = sorted(c.name + ("/" if c.is_dir() else "") for c in p.iterdir()
                         if c.name not in SKIP_DIRS and not c.name.startswith("."))
    except OSError:
        return None
    sl.tree = entries[:60]

    # collect README(s) + manifests, bounded by file count + total bytes
    candidates: list[Path] = []
    try:
        for c in sorted(p.iterdir()):
            if c.is_file() and (_README_RE.match(c.name) or c.name in MANIFESTS):
                candidates.append(c)
    except OSError:
        return None
    # one level down for nested manifests (e.g. src/pyproject, packages/*/package.json)
    for c in list(p.iterdir()) if p.is_dir() else []:
        if c.is_dir() and c.name not in SKIP_DIRS and not c.name.startswith("."):
            try:
                for f in sorted(c.iterdir()):
                    if f.is_file() and f.name in MANIFESTS:
                        candidates.append(f)
            except OSError:
                continue

    total = 0
    for f in candidates:
        if len(sl.files) >= max_files or total >= max_bytes:
            sl.truncated = True
            break
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
        except OSError:
            continue
        clean = _redact(raw, redactors)
        sl.files.append({"name": f.name, "text": clean})
        total += len(clean)
    return sl


SCAN_PROMPT = """# Codebase scan — ground the résumé in what this project actually is

Read the bounded slice below (README, manifests, top-level structure) for the
project **{group}** and summarize ONLY what the code demonstrably shows. Do not
infer or embellish features the repo doesn't evidence — "couldn't determine" is a
valid, honest answer for any field.

Top-level structure:
{tree}

<files>
{files}
</files>

Output strict YAML (no prose, no fences):

purpose: "<one sentence: what this project is / does, grounded in the files>"
concrete_features:
  - "<a feature the code actually implements>"
confirmed_tech:
  - "<language/framework/lib actually present in manifests or imports>"
entrypoints:
  - "<CLI command / route / main module the code defines>"

Rules: only what the slice shows; omit a list (leave `[]`) rather than guess;
never output secrets, connection strings, or PII.
"""


def render_scan_prompt(sl: CodebaseSlice) -> str:
    files_block = "\n\n".join(f"## {f['name']}\n{f['text']}" for f in sl.files) or "(no readable manifests/README)"
    return SCAN_PROMPT.format(group=sl.group, tree="\n".join(sl.tree) or "(empty)", files=files_block)


@dataclass
class CodebaseGrounding:
    group: str
    purpose: str = ""
    concrete_features: list[str] = field(default_factory=list)
    confirmed_tech: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def coerce_grounding(group: str, data: dict[str, Any]) -> CodebaseGrounding:
    def _list(k: str) -> list[str]:
        v = data.get(k)
        return [str(x) for x in v if x] if isinstance(v, list) else []
    return CodebaseGrounding(
        group=group,
        purpose=str(data.get("purpose") or ""),
        concrete_features=_list("concrete_features"),
        confirmed_tech=_list("confirmed_tech"),
        entrypoints=_list("entrypoints"),
    )


def save_scan(groundings: dict[str, CodebaseGrounding], path: Path = SCAN_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(
        {k: g.as_dict() for k, g in groundings.items()}, option=orjson.OPT_INDENT_2
    ))


def load_scan(path: Path = SCAN_CACHE) -> dict[str, CodebaseGrounding]:
    if not path.exists():
        return {}
    try:
        data = orjson.loads(path.read_bytes())
    except (OSError, ValueError):
        return {}
    return {k: coerce_grounding(k, v) for k, v in data.items() if isinstance(v, dict)}


_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(name: str) -> str:
    return (_SLUG_RE.sub("-", name)[:60].strip("-")) or "group"


def emit_scan_jobs(groups, out_dir: Path, redactors=None) -> tuple[Path, int, int]:
    """Write one scan prompt per group that has a resolvable local path.
    Returns (jobs_dir, emitted, skipped). Groups without a path are skipped
    silently (extractor contract: never invent)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    emitted = skipped = 0
    for i, g in enumerate(groups, 1):
        if not getattr(g, "path", None):
            skipped += 1
            continue
        sl = gather_slice(g.path, redactors, group=g.name)
        if sl is None:
            skipped += 1
            continue
        slug = f"{i:03d}_{_slug(g.name)}"
        (out_dir / f"{slug}.scan.prompt.md").write_text(render_scan_prompt(sl), encoding="utf-8")
        manifest[slug] = g.name
        emitted += 1
    (out_dir / "scan_manifest.json").write_bytes(orjson.dumps(manifest, option=orjson.OPT_INDENT_2))
    return out_dir, emitted, skipped


def ingest_scan(jobs_dir: Path) -> tuple[int, list[str]]:
    """Read <slug>.scan.yaml results next to the prompts, coerce, and persist to
    the grounding cache. Missing/malformed results become warnings (never abort)."""
    import yaml as _yaml

    mf = jobs_dir / "scan_manifest.json"
    if not mf.exists():
        return 0, [f"no scan_manifest.json in {jobs_dir} — run `vibe-resume scan` first"]
    manifest = orjson.loads(mf.read_bytes())
    groundings: dict[str, CodebaseGrounding] = {}
    warnings: list[str] = []
    for slug, group in manifest.items():
        yp = jobs_dir / f"{slug}.scan.yaml"
        if not yp.exists():
            warnings.append(f"{slug}: missing {yp.name}")
            continue
        body = yp.read_text(encoding="utf-8").strip()
        if body.startswith("```"):
            body = "\n".join(body.splitlines()[1:])
        if body.endswith("```"):
            body = "\n".join(body.splitlines()[:-1])
        try:
            data = _yaml.safe_load(body)
        except _yaml.YAMLError as e:
            warnings.append(f"{slug}: yaml error — {e}")
            continue
        if isinstance(data, dict):
            groundings[group] = coerce_grounding(group, data)
        else:
            warnings.append(f"{slug}: result is not a mapping")
    if groundings:
        save_scan(groundings)
    return len(groundings), warnings
