"""GA574 EP/BV: the injected invoice mode follows the resolved iteration mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.types import InvoiceData, IterationInfo
from tests.v2.contract.fixtures import _generate


@pytest.mark.parametrize("mode", ["invoice", "excelinvoice", "multidatatile", "smarttable", "rdeformat"])
def test_invoice_mode_matches_every_tile__ga574_ep_1_bv_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    """GA574-EP-1/BV-1: no non-invoice tile silently reports invoice mode."""
    # Given: a real dataset for a resolved processing mode
    _generate.materialize_sut_case(mode, tmp_path)
    monkeypatch.chdir(tmp_path)
    seen: list[tuple[str, str]] = []

    @flow
    def pipeline(invoice: InvoiceData, iteration: IterationInfo) -> None:
        seen.append((invoice.mode, iteration.mode))

    # When: running the actual v2 public entry
    configured = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode, "")
    report = workflows.run(flow=pipeline, config={"system": {"extended_mode": configured, "save_thumbnail_image": False}})
    # Then: each injected invoice agrees with the Runner's mode
    assert report.status == "success", report.error
    assert seen
    assert all(invoice_mode == iteration_mode == mode for invoice_mode, iteration_mode in seen)
    if mode in {"excelinvoice", "multidatatile"}:
        assert len(seen) >= 2
