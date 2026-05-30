"""Ledger forking for Gate-mode branch exploration (#77).

Pure-core tests: forking copies the base ledger and applies an alternative
decision at one gate WITHOUT mutating the original; branch ids are
deterministic (no clock/RNG); branch files are discoverable and adoptable.
"""
from __future__ import annotations

import json

from vibe_resume.core.gates import Gate, GateLedger
from vibe_resume.core.run_branch import (
    adopt_branch,
    branch_id_for,
    branch_ledger_path,
    fork_ledger,
    list_branch_ids,
)


def _base_ledger() -> GateLedger:
    led = GateLedger()
    led.record(Gate.G1_FRESHNESS, {"choice": "reextract"}, "T1")
    led.record(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 6}, "T2")
    return led


def test_branch_id_deterministic_and_discriminates():
    a = branch_id_for(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8})
    b = branch_id_for(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8})
    c = branch_id_for(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 6})
    assert a == b               # deterministic
    assert a != c               # discriminates on the param value
    assert a.startswith("g2-")  # gate-prefixed slug
    assert " " not in a and "{" not in a


def test_fork_applies_decision_without_mutating_base():
    base = _base_ledger()
    forked = fork_ledger(base, Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8}, "T9")
    # base untouched
    assert base.get(Gate.G2_GROUPING).decision == {"choice": "top_n", "top_n": 6}
    # fork carries the alternative + keeps the upstream G1 decision
    assert forked.get(Gate.G2_GROUPING).decision == {"choice": "top_n", "top_n": 8}
    assert forked.get(Gate.G1_FRESHNESS).decision == {"choice": "reextract"}
    assert forked.get(Gate.G2_GROUPING).timestamp == "T9"


def test_branch_path_and_listing(tmp_path):
    data_dir = tmp_path / "data"
    bid = branch_id_for(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8})
    p = branch_ledger_path(data_dir, bid)
    assert p.name.startswith("run_ledger.branch-")
    assert p.name.endswith(".json")
    fork_ledger(_base_ledger(), Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8}, "T9").save(p)
    fork_ledger(_base_ledger(), Gate.G2_GROUPING, {"choice": "top_n", "top_n": 4}, "T9").save(
        branch_ledger_path(data_dir, branch_id_for(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 4}))
    )
    ids = list_branch_ids(data_dir)
    assert bid in ids and len(ids) == 2
    # the main ledger must NOT be picked up as a branch
    GateLedger().save(data_dir / "run_ledger.json")
    assert "run_ledger" not in list_branch_ids(data_dir)


def test_adopt_promotes_branch_over_main(tmp_path):
    data_dir = tmp_path / "data"
    main = data_dir / "run_ledger.json"
    _base_ledger().save(main)
    bid = branch_id_for(Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8})
    fork_ledger(_base_ledger(), Gate.G2_GROUPING, {"choice": "top_n", "top_n": 8}, "T9").save(
        branch_ledger_path(data_dir, bid)
    )
    adopt_branch(data_dir, bid, main_path=main)
    promoted = GateLedger.load(main)
    assert promoted.get(Gate.G2_GROUPING).decision == {"choice": "top_n", "top_n": 8}
    # adopting an unknown branch raises
    try:
        adopt_branch(data_dir, "g2-nope", main_path=main)
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_branch_file_is_valid_json(tmp_path):
    data_dir = tmp_path / "data"
    bid = branch_id_for(Gate.G7_VARIANTS, {"choice": "top_n", "top_n": 8})
    p = fork_ledger(_base_ledger(), Gate.G7_VARIANTS, {"choice": "select", "variant": "ats"}, "T9").save(
        branch_ledger_path(data_dir, bid)
    )
    data = json.loads(p.read_text())
    assert data["version"] == 1 and isinstance(data["decisions"], list)
