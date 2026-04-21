"""Guardrails for the tunable-heuristic constants in core/aggregator.

The values here were chosen empirically and live in named constants so they
can be found, commented, and adjusted deliberately. Removing one silently
would turn magic numbers back into scattered literals — these tests fail
loudly if that happens, not to pin specific numbers.
"""
from __future__ import annotations

from core import aggregator


def test_tunable_constants_are_present_and_sane() -> None:
    # Names the code path in aggregator.py actively references. If you rename
    # one, update both the module and this list; if you delete one, be sure
    # you've collapsed its usage upstream first.
    required = {
        "NAME_MAX_LEN",
        "NAME_TRUNCATED_LEN",
        "SUMMARY_PREVIEW_LEN",
        "RAW_PREFIX_FALLBACK_LEN",
        "MIN_SESSIONS_DEFAULT",
        "MIN_SESSIONS_HASH_ID",
        "MIN_SESSIONS_NO_TECH",
        "HEADLINE_CATEGORY_PCT",
    }
    missing = required - set(dir(aggregator))
    assert not missing, f"missing tunable constants: {sorted(missing)}"

    # Truncation targets must leave room for the ellipsis suffix.
    assert aggregator.NAME_TRUNCATED_LEN < aggregator.NAME_MAX_LEN
    # Session thresholds must be positive ints — a zero would disable the filter.
    assert aggregator.MIN_SESSIONS_DEFAULT >= 1
    assert aggregator.MIN_SESSIONS_HASH_ID >= 1
    assert aggregator.MIN_SESSIONS_NO_TECH >= 1
    # Category percentage is a whole-number percent, not a 0..1 ratio — the
    # codepath multiplies by 100 before comparing, so a value <=1 would let
    # nearly everything through.
    assert 1 <= aggregator.HEADLINE_CATEGORY_PCT <= 100
