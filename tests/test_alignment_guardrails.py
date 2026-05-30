"""Cross-cutting P1 alignment guardrail tests (docs/PRINCIPLES.md, #70).

The score is a proxy; no gate may enable fabrication. The G5 metrics gate must
surface ONLY ``safe_to_surface`` real metrics from the #62-#69 evidence
disclosure layer — never an invented or unsafe (UI-threshold / css / model-spec /
url-fragment) value. This exercises the seam to ``core/evidence.py`` by building
the gate context out of a real :class:`GroupEvidence.as_dict()`.
"""
from __future__ import annotations

import json

import pytest

from vibe_resume.core.evidence import GroupEvidence, MetricCandidate
from vibe_resume.core.gates import (
    Gate,
    emit_gate,
    g5_safe_metric_values,
    gate_file_path,
)


def _evidence_with(*metrics: MetricCandidate) -> GroupEvidence:
    return GroupEvidence(
        group="auth-service",
        activity_count=len(metrics),
        candidate_metrics=list(metrics),
    )


def test_g5_emit_refuses_unsafe_metric_from_real_evidence(tmp_path):
    """P1 invariant: an evidence-shaped context carrying a non-safe metric (e.g.
    a CSS value misclassified as impact-shaped) cannot reach the G5 gate file."""
    ev = _evidence_with(
        MetricCandidate(value="40%", source_ref="commit:abc", context="reduced latency 40%",
                        kind="real_metric", confidence="high", safe_to_surface=True),
        MetricCandidate(value="600px", source_ref="ui", context="max-width: 600px",
                        kind="css_value", confidence="low", safe_to_surface=False),
    )
    context = {"groups": [ev.as_dict()]}
    with pytest.raises(ValueError, match="non-safe_to_surface"):
        emit_gate(Gate.G5_METRICS, tmp_path, context=context)
    assert not gate_file_path(tmp_path, Gate.G5_METRICS).exists()


def test_g5_emit_only_lists_safe_to_surface_metrics(tmp_path):
    """When every disclosed metric is safe, G5 emits and offers exactly those
    values — never originating a number absent from the evidence."""
    ev = _evidence_with(
        MetricCandidate(value="40%", source_ref="commit:abc", context="cut build 40%",
                        kind="real_metric", confidence="high", safe_to_surface=True),
        MetricCandidate(value="3x", source_ref="commit:def", context="3x throughput",
                        kind="real_metric", confidence="medium", safe_to_surface=True),
    )
    context = {"groups": [ev.as_dict()]}
    p = emit_gate(Gate.G5_METRICS, tmp_path, context=context)
    data = json.loads(p.read_text())
    assert data["gate"] == "G5"
    # the gate context surfaces only the disclosed safe values, nothing invented
    assert g5_safe_metric_values(data["context"]) == {"40%", "3x"}
