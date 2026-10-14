"""Compare ``SmartTableInvoiceBuilder`` with the frozen v1 initializer (Session K2-0).

The observation itself is ``_freeze.observe_case`` -- the function the freezer
ran on v1 -- so the only thing that differs between a frozen value and the
observation made here is the step runner: :func:`v2_step_runner` drives the v2
builder exactly as one run's ``InvoiceService`` does (one builder per run, one
``build`` per row).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths
from tests.v2.contract.frozen import require_builder_snapshot
from tests.v2.modes.fixtures.smarttable_builder import _freeze


def v2_step_runner() -> _freeze.StepRunner:
    """Return a step runner over one run-scoped v2 builder.

    A step without any row CSV reference cannot reach the builder at all
    (``build`` requires one); the run reaches it through
    ``InvoiceService.prepare_tile``, which is where the v1 "No SmartTable row
    CSV file found" contract lives in v2.
    """
    builder = SmartTableInvoiceBuilder()

    def _run(paths: _freeze.StepPaths) -> dict[str, Any] | None:
        if paths.rowfile is None:
            InvoiceService().prepare_tile(
                ModeKind.smarttable,
                paths=InputPaths(
                    inputdata=paths.root / "temp",
                    invoice=paths.invoice_org.parent,
                    tasksupport=paths.schema_path.parent,
                    rawfiles=(),
                ),
                invoice_dir=paths.dist_path.parent,
                iteration_index=0,
                invariant_invoice=None,
                invoice_source=paths.invoice_org,
            )
            return None
        return builder.build(
            rowfile=paths.rowfile,
            invoice_org=paths.invoice_org,
            invoice_schema_path=paths.schema_path,
            dist_path=paths.dist_path,
            metadata_def_path=paths.metadata_def_path,
            metadata_path=paths.metadata_path,
        )

    return _run


def _canonical(value: Any) -> str:
    # ``3 == 3.0`` in Python; the int-before-float rule (TC-I6-C-BV-040) is only
    # observable in the serialized form, so equality is asserted on both.
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def observe_v2(tmp_path: Path, case_id: str) -> dict[str, Any]:
    """Observe the v2 builder on a registered case (no frozen value involved).

    Args:
        tmp_path: Per-test directory; the case root is created below it.
        case_id: ``<family>/<stem>`` of a registered builder case.

    Returns:
        The normalized observation, shaped like the frozen ``observed`` block.
    """
    root = tmp_path / "v2"
    root.mkdir()
    return _freeze.observe_case(_freeze.builder_case(case_id), root, v2_step_runner())


def assert_matches_frozen(case_id: str, observed: dict[str, Any]) -> None:
    """Assert a v2 observation equals the frozen v1 one (skips while pending)."""
    frozen: dict[str, Any] = require_builder_snapshot(case_id)["observed"]
    assert observed == frozen
    assert _canonical(observed) == _canonical(frozen)


def compare_with_frozen(tmp_path: Path, case_id: str) -> dict[str, Any]:
    """Observe the v2 builder on a registered case and assert it equals the frozen v1 value.

    The v2 observation runs first, so a not-yet-frozen case still executes the
    builder before it skips as pending.
    """
    observed = observe_v2(tmp_path, case_id)
    assert_matches_frozen(case_id, observed)
    return observed


def success_step(observed: dict[str, Any]) -> dict[str, Any]:
    """Assert no step failed and return the last step's observation."""
    assert all("error" not in step for step in observed["steps"])
    step: dict[str, Any] = observed["steps"][-1]
    return step


def failure_error(observed: dict[str, Any]) -> dict[str, Any]:
    """Assert the last step failed with a StructuredError and return the error record."""
    error: dict[str, Any] = observed["steps"][-1]["error"]
    assert error["type"] == "StructuredError"
    return error
