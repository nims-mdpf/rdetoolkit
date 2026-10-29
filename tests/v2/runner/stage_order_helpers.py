"""Shared plan builder for artifact-stage-order tests (Session I-REVIEW-A)."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.api.request import FlowTarget
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan
from rdetoolkit.types import RdeConfig


def make_plan(mode: ModeKind, root: Path) -> ExecutionPlan:
    """Build a minimal plan whose only meaningful field is its mode.

    Args:
        mode: Mode whose handler capabilities are under test.
        root: Directory used as both the run root and the data root.

    Returns:
        A plan with no tiles, which is all ``artifact_stage_order`` needs.
    """
    return ExecutionPlan(
        run_id="stage-order",
        target=FlowTarget(function=lambda: None),
        mode=mode,
        config=RdeConfig(),
        root=root,
        error_policy="continue",
        tiles=(),
        data_root=root,
        invoice_source=root / "invoice" / "invoice.json",
    )
