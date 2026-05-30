"""Ledger forking for Gate-mode branch exploration (#77).

Interactive Gate Mode's ledger (``data/run_ledger.json``) is linear — one
decision per gate. To explore "what if I'd decided differently" without losing
the original, this module forks the ledger to a NAMED branch file, applies an
alternative decision at one gate, and leaves the original intact. The ``run``
command then recomputes only that gate's invalidation suffix (reusing
``resume_plan``) and auto review-diffs the branch's résumé against the original.

Pure + clock-free: every nondeterministic input (the timestamp) is a parameter,
and branch ids are a deterministic slug of the gate + decision — so the same
fork always lands in the same file (no RNG, replay-safe like the rest of the
gate core).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from vibe_resume.core.gates import Gate, GateLedger

#: Branch ledgers live beside the main one as ``run_ledger.branch-<id>.json`` so
#: ``list_branch_ids`` can glob them without ever matching ``run_ledger.json``.
_BRANCH_PREFIX = "run_ledger.branch-"
_BRANCH_SUFFIX = ".json"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", str(text).lower()).strip("-")


def branch_id_for(gate: Gate, decision: dict[str, Any]) -> str:
    """Deterministic branch id from a gate + its alternative decision (#77).

    Slug shape: ``<gate>-<choice>[-<param><value>…]`` over the decision's scalar
    params (sorted, ``choice`` first) so two branches that differ only in e.g.
    ``top_n`` get distinct ids while the same fork is always reproducible."""
    choice = decision.get("choice", "")
    parts = [gate.value, str(choice)]
    for k in sorted(decision):
        if k == "choice":
            continue
        v = decision[k]
        if isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}{v}")
    return _slug("-".join(p for p in parts if p))


def branch_ledger_path(data_dir: Path, branch_id: str) -> Path:
    """Path for a branch ledger: ``<data_dir>/run_ledger.branch-<id>.json``."""
    return data_dir / f"{_BRANCH_PREFIX}{branch_id}{_BRANCH_SUFFIX}"


def list_branch_ids(data_dir: Path) -> list[str]:
    """All branch ids present under ``data_dir`` (sorted; excludes the main ledger)."""
    if not data_dir.exists():
        return []
    out: list[str] = []
    for p in data_dir.glob(f"{_BRANCH_PREFIX}*{_BRANCH_SUFFIX}"):
        out.append(p.name[len(_BRANCH_PREFIX):-len(_BRANCH_SUFFIX)])
    return sorted(out)


def fork_ledger(
    base: GateLedger, gate: Gate, decision: dict[str, Any], timestamp: str
) -> GateLedger:
    """Copy ``base`` and apply ``decision`` at ``gate`` — the base is NOT mutated.

    Upstream decisions are preserved; only the forked gate's row changes (its
    downstream suffix is what ``resume_plan`` will recompute)."""
    forked = GateLedger.from_dict(base.as_dict())  # deep copy via round-trip
    forked.record(gate, dict(decision), timestamp)
    return forked


def adopt_branch(data_dir: Path, branch_id: str, *, main_path: Path) -> Path:
    """Promote a branch ledger to be the main ledger (#77 ``run --adopt``).

    Raises :class:`FileNotFoundError` if the branch does not exist."""
    src = branch_ledger_path(data_dir, branch_id)
    if not src.exists():
        raise FileNotFoundError(f"no such branch: {branch_id} ({src})")
    main_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, main_path)
    return main_path
