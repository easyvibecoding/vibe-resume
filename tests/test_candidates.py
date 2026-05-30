"""Angle-biased candidate bullet-sets per group (#75).

Pure-core tests: the three angle biases are prompt PREFIXES only (the
anti-fabrication + human-gate rules are untouched), candidate prompts are the
base prompt + exactly one angle block, and per-group selection picks the chosen
candidate while defaulting conservatively.
"""
from __future__ import annotations

import pytest

from vibe_resume.core.candidates import (
    CANDIDATE_ANGLES,
    angle_block,
    build_candidate_prompts,
    compare_rows,
    select_candidates,
)


def test_three_angles_registered():
    assert set(CANDIDATE_ANGLES) == {"impact_first", "breadth_first", "depth_first"}
    for key in CANDIDATE_ANGLES:
        blk = angle_block(key)
        # the bias is framed as conditional on the activity — never fabricate
        assert "never" in blk.lower() or "支援" in blk or "support" in blk.lower()


def test_unknown_angle_raises():
    with pytest.raises(KeyError):
        angle_block("nonsense")


def test_build_candidate_prompts_appends_one_block_each():
    base = "BASE PROMPT BODY"
    prompts = build_candidate_prompts(base, ["impact_first", "depth_first"])
    assert list(prompts) == ["impact_first", "depth_first"]
    for key, body in prompts.items():
        assert body.startswith(base)                 # base preserved verbatim
        assert angle_block(key) in body              # exactly its own angle appended
        # not contaminated by the other angle
        other = "depth_first" if key == "impact_first" else "impact_first"
        assert angle_block(other) not in body


def test_build_candidate_prompts_default_is_all_three():
    prompts = build_candidate_prompts("X")
    assert set(prompts) == set(CANDIDATE_ANGLES)


def test_select_candidates_picks_per_group():
    by_group = {
        "CRM": ["impact bullets", "breadth bullets", "depth bullets"],
        "RAG": ["impact bullets", "breadth bullets", "depth bullets"],
    }
    # pick index 2 (depth) for CRM, default (0) for RAG
    chosen = select_candidates({"CRM": 2}, by_group)
    assert chosen["CRM"] == "depth bullets"
    assert chosen["RAG"] == "impact bullets"   # conservative default = first candidate


def test_select_candidates_out_of_range_falls_back_to_first():
    by_group = {"CRM": ["a", "b"]}
    assert select_candidates({"CRM": 9}, by_group)["CRM"] == "a"
    assert select_candidates({"CRM": -1}, by_group)["CRM"] == "a"


def test_compare_rows_aligns_by_group_and_limits():
    by_group = {
        "CRM": [{"angle": "impact_first", "bullets": ["lead with metric"]},
                {"angle": "depth_first", "bullets": ["lead with system"]}],
        "RAG": [{"angle": "impact_first", "bullets": ["x"]}],
    }
    rows = compare_rows(by_group, limit=1)
    assert len(rows) == 1
    assert rows[0].name == "CRM"
    assert [c["angle"] for c in rows[0].candidates] == ["impact_first", "depth_first"]
