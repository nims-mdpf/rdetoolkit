"""GA569 EP/BV: expose the planner's invoice source to v2 flows in every mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.types import InputPaths, OutputContext
from tests.v2.contract.fixtures import _generate


@pytest.mark.parametrize("mode", ["invoice", "excelinvoice", "multidatatile", "smarttable", "rdeformat"])
def test_flow_receives_run_level_invoice_source__ga569_ep_1_2_bv_1_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    """GA569: the source is shared across tiles and distinct from tile outputs."""
    # Given: real mode fixtures, including multi-row Excel invoices
    _generate.materialize_sut_case(mode, tmp_path)
    monkeypatch.chdir(tmp_path)
    if mode == "invoice":
        backup = tmp_path / "data" / "temp" / "invoice_org.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text('{"stale": true}', encoding="utf-8")
    seen: list[tuple[Path, Path]] = []

    @flow
    def pipeline(paths: InputPaths, out: OutputContext) -> None:
        assert paths.invoice_org is not None
        seen.append((paths.invoice_org, out.invoice / "invoice.json"))
        source = json.loads(paths.invoice_org.read_text(encoding="utf-8"))
        assert "basic" in source

    # When: invoking the v2 public entry with the fixture's configured mode
    configured = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode, "")
    report = workflows.run(flow=pipeline, config={"system": {"extended_mode": configured, "save_thumbnail_image": False}})
    # Then: every tile receives the same mode-selected source, not another tile
    assert report.status == "success", report.error
    relative = "temp/invoice_org.json" if mode in {"excelinvoice", "multidatatile", "rdeformat"} else "invoice/invoice.json"
    expected = tmp_path / "data" / relative
    assert seen
    assert all(source.resolve() == expected for source, _ in seen)
    if mode == "excelinvoice":
        assert len(seen) >= 2
        assert len({destination for _, destination in seen}) == len(seen)
        assert all(source.resolve() != destination.resolve() for source, destination in seen)
